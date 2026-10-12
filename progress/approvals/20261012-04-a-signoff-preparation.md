# 04-A checkpoint/租约/事实/outbox 契约签认确认文档

> **日期**: 2026-10-12  
> **契约版本**: AGENT-PERSISTENCE-0.1-draft.1  
> **签认人**: Owner (个人项目)  
> **状态**: 进行中  
> **前置条件**: ✅ 03-A 已发布 (contract-v0.2)

---

## 签认概述

04-A 定义了 Agent 持久化的核心机制，包括：
- **Checkpoint**: 可恢复的执行状态
- **租约与 Fencing**: 防止多进程并发冲突
- **结果事务**: 原子提交答案、Claims、Citation
- **Outbox 模式**: 保证事件发布的一致性
- **预算账本**: 崩溃后可恢复的用量追踪

**关键决策**: 这是 **DR-011** 的设计候选，需要 Owner 最终批准

---

## 签认项 1/7: M00 / 规格治理

**责任**: 确认内部版本、发布边界与 ADR 审批

### 确认要点:

#### 1.1 内部版本与 03-A 对接
- ✅ **确认**: ResumeAdmission 表与 03-A 受理记录一致
- ✅ **确认**: ExecutionIntent 承接 03-A 的执行意图持久化
- ✅ **确认**: 幂等命名空间独立但兼容

**我的建议**: ✅ 接受
- 03-A 的 BackgroundTasks 升级为 04-A 的 ExecutionIntent 表
- 保持幂等键的语义一致性

#### 1.2 发布边界
- ✅ **确认**: 这是**内部契约**，不改变公开 API (contract-v0.2)
- ✅ **确认**: 不新增公开路由、字段或错误码
- ✅ **确认**: 客户端无感知，完全向后兼容

**我的建议**: ✅ 接受
- 持久化是内部实现细节，不影响客户端

#### 1.3 错误映射
现有错误码足够，新增内部失败场景：
- **Fencing 失败**: 内部重试，不暴露给用户
- **Checkpoint 写入失败**: 503 PROVIDER_TEMPORARY_ERROR
- **事务回滚**: 不返回成功，客户端重试

**我的建议**: ✅ 接受
- 错误映射合理，保持客户端简单

#### 1.4 ADR 决策记录
- ✅ **确认**: 需要正式登记 **DR-011** 决策
- ✅ **确认**: 决策内容包括:
  - 采用 PostgreSQL Saver + fencing
  - 租约时长与续期策略
  - Checkpoint 保留期与加密
  - Outbox 事件发布机制

**我的建议**: ✅ 接受，但需要明确：
- ⚠️ **待定生产数值** (TBD-P0):
  - 租约时长: 建议 **5 分钟**
  - 续期间隔: 建议 **30 秒**
  - Checkpoint 保留期: 建议 **30 天**
  - 已清理 Run 保留: 建议 **90 天**

**你是否同意这些数值？需要调整吗？**

---

## 签认项 2/7: M03 / 数据库与事务

**责任**: 确认 Saver fencing、DDL、锁顺序、迁移

### 确认要点:

#### 2.1 Saver 写入 Fencing 能力

**关键问题**: LangGraph 的 BaseSaver 本身**不提供 fencing**

**提案方案**:
```python
class FencedPostgresSaver(PostgresSaver):
    def put(self, config, checkpoint, metadata):
        # 在 PG 事务中:
        # 1. 锁定 RunExecution + ExecutionLease
        # 2. 检查当前 token + state_version
        # 3. 只有匹配才写入 checkpoint
        # 4. 更新 CheckpointBinding
        ...
    
    def put_writes(self, config, writes, task_id):
        # 同样需要 fencing 保护
        ...
```

**关键约束**:
- ✅ **必须**: 每次框架写操作都检查租约
- ✅ **必须**: 旧 executor 的 checkpoint 写入被拒绝
- ✅ **必须**: 框架表与业务表在同一 PG 实例

**我的建议**: ✅ 接受，但需要确认：
- ⚠️ **技术风险**: LangGraph 可能有其他写入路径（如 `alist_writes`, `asearch`）
- ⚠️ **建议**: 04-C 实施前需要完整审计 LangGraph 源码，确保所有写入路径都被覆盖

**你是否接受这个技术风险？是否需要提前审计 LangGraph 源码？**

#### 2.2 DDL 设计

**拟议表结构** (逻辑设计，物理表名由 04-B 确定):

```sql
-- 执行元数据
CREATE TABLE run_execution (
    run_id VARCHAR(128) PRIMARY KEY,
    thread_id VARCHAR(128) UNIQUE NOT NULL,
    state_version INTEGER NOT NULL DEFAULT 0,
    graph_version VARCHAR(64) NOT NULL,
    budget_policy_version VARCHAR(64) NOT NULL,
    deadline_at TIMESTAMPTZ NOT NULL,
    checkpoint_id VARCHAR(128),
    ledger_cursor INTEGER
);

-- 租约
CREATE TABLE execution_lease (
    run_id VARCHAR(128) PRIMARY KEY REFERENCES run_execution(run_id),
    executor_id VARCHAR(128) NOT NULL,
    fencing_token INTEGER NOT NULL DEFAULT 1,
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT token_positive CHECK (fencing_token > 0)
);

-- Checkpoint 绑定
CREATE TABLE checkpoint_binding (
    run_id VARCHAR(128) PRIMARY KEY REFERENCES run_execution(run_id),
    checkpoint_id VARCHAR(128) NOT NULL,
    thread_id VARCHAR(128) NOT NULL,
    state_version INTEGER NOT NULL,
    fencing_token INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

-- 结果提交
CREATE TABLE result_commit (
    run_id VARCHAR(128) PRIMARY KEY REFERENCES run_execution(run_id),
    result_id VARCHAR(128) UNIQUE NOT NULL,
    message_id VARCHAR(128) NOT NULL,
    terminal_state VARCHAR(32) NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL
);

-- 事件 Outbox
CREATE TABLE public_event_outbox (
    event_id VARCHAR(128) PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL REFERENCES run_execution(run_id),
    seq INTEGER NOT NULL,
    event_name VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    publication_key VARCHAR(128) NOT NULL,
    dispatched_at TIMESTAMPTZ,
    UNIQUE (run_id, seq),
    UNIQUE (run_id, publication_key)
);

-- 恢复受理 (扩展 03-A)
CREATE TABLE resume_admission (
    admission_id VARCHAR(128) PRIMARY KEY,
    principal_id VARCHAR(128) NOT NULL,
    run_id VARCHAR(128) NOT NULL REFERENCES run_execution(run_id),
    operation VARCHAR(32) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    clarification_id VARCHAR(128) NOT NULL,
    answer_hash BYTEA NOT NULL,
    answer_encrypted BYTEA NOT NULL,
    receipt JSONB NOT NULL,
    admitted_at TIMESTAMPTZ NOT NULL,
    UNIQUE (principal_id, run_id, operation, idempotency_key),
    UNIQUE (run_id, clarification_id)
);

-- 执行意图
CREATE TABLE execution_intent (
    intent_id VARCHAR(128) PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL REFERENCES run_execution(run_id),
    action VARCHAR(32) NOT NULL, -- 'create' | 'resume'
    intent_data JSONB NOT NULL,
    status VARCHAR(32) NOT NULL, -- 'pending' | 'claimed' | 'completed'
    created_at TIMESTAMPTZ NOT NULL,
    claimed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- 供应商尝试
CREATE TABLE provider_attempt (
    attempt_id VARCHAR(128) PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL REFERENCES run_execution(run_id),
    action_id VARCHAR(128) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL, -- 'reserved' | 'dispatching' | 'completed' | 'unreconciled'
    reservation_microunits INTEGER NOT NULL,
    reported_input_tokens INTEGER,
    reported_output_tokens INTEGER,
    reported_cost_microunits INTEGER,
    dispatched_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE (run_id, action_id, attempt_id)
);
```

**我的建议**: ✅ 基本接受，但有优化建议：
1. ⚠️ **索引建议**:
   ```sql
   CREATE INDEX idx_lease_expires ON execution_lease(expires_at) WHERE expires_at > NOW();
   CREATE INDEX idx_intent_pending ON execution_intent(status, created_at) WHERE status = 'pending';
   CREATE INDEX idx_outbox_undispatched ON public_event_outbox(run_id, seq) WHERE dispatched_at IS NULL;
   ```
2. ⚠️ **分区建议**: `public_event_outbox` 按时间分区（月度），防止单表过大
3. ⚠️ **加密字段**: `answer_encrypted` 需要明确密钥管理方案

**你是否接受这些建议？**

#### 2.3 锁顺序

**拟议锁顺序** (防止死锁):
```
1. run_execution (SELECT ... FOR UPDATE)
2. execution_lease (SELECT ... FOR UPDATE)
3. checkpoint_binding (如需更新)
4. result_commit / outbox (插入)
```

**我的建议**: ✅ 接受
- 固定锁顺序可以防止死锁
- 所有写操作必须遵循此顺序

**你是否同意这个锁顺序？**

#### 2.4 UoW (Unit of Work)

**提案**: 结果提交的原子事务
```python
async def commit_result(
    token: LeaseToken,
    expected_version: int,
    result: VerifiedCandidate
) -> ResultReceipt:
    async with transaction():
        # 1. 锁定并验证 fencing
        lease = await check_lease_and_version(token, expected_version)
        
        # 2. 重新验证资源授权
        await recheck_authorization(run)
        
        # 3. 原子写入
        await insert_claims(result.claims)
        await insert_citations(result.citations)
        await update_message(result.content)
        await update_run_terminal_state(result.state)
        await insert_result_commit(result_id)
        await insert_outbox_events(events)
        
        # 任何失败都回滚全部
```

**我的建议**: ✅ 接受
- 原子性保证了数据一致性
- 失败时零公开正文

**你是否同意这个 UoW 设计？**

#### 2.5 迁移与回滚

**迁移策略**:
1. **Expand**: 新增表和索引（不影响旧代码）
2. **Migrate**: 迁移旧 Run 的兼容数据（只读）
3. **Contract**: 标记旧 Run 为 legacy（不可恢复）
4. **Opt-in**: 新 Agent Run 使用新表

**回滚策略**:
- ✅ **安全回滚**: 关闭新受理，fence 活跃租约，保留数据
- ⚠️ **破坏性回滚**: 只在测试环境，生产禁止 DROP

**我的建议**: ✅ 接受
- 渐进式迁移风险可控
- 生产环境不允许破坏性回滚

**你是否同意这个迁移策略？**

---

## 签认项 3/7: M01 / 安全

**责任**: 确认鉴权重检、加密、角色权限

### 确认要点:

#### 3.1 恢复时资源重检
- ✅ **确认**: 恢复前重新验证 active/owner/scope
- ✅ **确认**: 文档删除/版本切换/外发撤销阻止恢复
- ✅ **确认**: 不信任 checkpoint 中的权限快照

**我的建议**: ✅ 接受
- 安全优先，不能用旧快照绕过当前权限

#### 3.2 AgentState 白名单
基于 02-A AGENT-INTERNAL 的白名单：
```python
# 允许
- messages: List[BaseMessage]
- evidence_registry: Dict[str, EvidenceMetadata]
- retrieval_context: List[str]

# 禁止
- credentials / api_keys
- reasoning (LLM 内部思考)
- tool 私有参数
- 依赖句柄 (如 DB connections)
```

**我的建议**: ✅ 接受
- 白名单机制防止敏感信息泄露

#### 3.3 Checkpoint 加密

**提案**:
```python
# 加密前
state = {"messages": [...], "evidence": {...}}

# 白名单过滤
filtered = apply_whitelist(state)

# 加密
encrypted = encrypt_with_kms(
    plaintext=json.dumps(filtered),
    key_ref="agent-checkpoint-key-v1"
)

# 存储
await saver.put(config, checkpoint, metadata={
    "encrypted": True,
    "key_ref": "agent-checkpoint-key-v1",
    "version": 1
})
```

**密钥管理方案** (TBD-P0):
- 选项 A: AWS KMS (云端)
- 选项 B: HashiCorp Vault (自托管)
- 选项 C: 本地文件加密 (仅开发)

**我的建议**: ✅ 接受加密设计，但需要决定：
- ⚠️ **问题**: 你希望使用哪种密钥管理方案？
- 个人项目推荐：**选项 C + 明确标注仅开发用**，生产环境强制 fail closed

**你的选择是？**

#### 3.4 数据库角色权限

**拟议角色**:
```sql
-- 迁移角色 (仅建表)
CREATE ROLE pivot_migration;
GRANT CREATE ON DATABASE pivot TO pivot_migration;

-- 应用角色 (读写业务表)
CREATE ROLE pivot_app;
GRANT SELECT, INSERT, UPDATE ON TABLE runs, messages TO pivot_app;

-- Runner 角色 (读写执行表)
CREATE ROLE pivot_runner;
GRANT SELECT, INSERT, UPDATE ON TABLE run_execution, execution_lease TO pivot_runner;
GRANT SELECT ON TABLE checkpoint_binding TO pivot_runner;

-- Dispatcher 角色 (只读 outbox)
CREATE ROLE pivot_dispatcher;
GRANT SELECT, UPDATE (dispatched_at) ON TABLE public_event_outbox TO pivot_dispatcher;

-- 审计角色 (只读)
CREATE ROLE pivot_audit;
GRANT SELECT ON ALL TABLES TO pivot_audit;
```

**我的建议**: ✅ 接受
- 最小权限原则
- Runner 不能读取审计表，Dispatcher 不能修改业务数据

**你是否同意这个角色设计？**

#### 3.5 删除与清理策略

**用户会话隐藏**:
1. 禁止新执行/恢复
2. 撤销租约，终止活跃 Run
3. 清理 checkpoint (按保留期)
4. 清理 ResumeAdmission 敏感输入
5. 保留 fencing tombstone (防止复活)

**Checkpoint 保留期** (TBD-P0):
- 建议: **30 天**
- 已终态 Run 的 checkpoint 可提前清理 (7 天后)
- 清理后仍保留 ExecutionIntent/租约 tombstone

**我的建议**: ✅ 接受保留期，但需要确认：
- ⚠️ **问题**: 30 天保留期是否合适？是否需要更长/更短？

**你的决定是？**

---

## 签认项 4/7: M05 / 状态与预算

**责任**: 确认固定版本、epoch、预算恢复

### 确认要点:

#### 4.1 固定版本恢复
- ✅ **确认**: graph/state/prompt/tools/model 版本不匹配 → fail closed
- ✅ **确认**: 不静默升级或 fallback 线性 RAG
- ✅ **确认**: 版本随 RunExecution 持久化

**我的建议**: ✅ 接受
- 版本固定保证可复现性

#### 4.2 Execution Epoch
```python
# 每次新执行前递增
execution_epoch += 1

# 稳定 action 映射
action_id = f"{run_id}_{epoch}_{node_name}"

# Interrupt 前缀可重跑，不重复计费
if is_before_last_checkpoint():
    skip_provider_call()
```

**我的建议**: ✅ 接受
- Epoch 机制避免重复副作用

#### 4.3 预算恢复对账
```python
# 恢复时
persisted_ledger = load_budget_ledger(run_id)
checkpoint_budget = extract_from_checkpoint()

# 保守对账
if persisted_ledger.total > checkpoint_budget.total:
    # 使用更大的消耗值（保守）
    budget.consumed = persisted_ledger.total
else:
    budget.consumed = checkpoint_budget.total

# 继续执行
remaining = budget.limit - budget.consumed
```

**我的建议**: ✅ 接受
- 保守对账防止预算绕过

#### 4.4 等待与取消
- ✅ **确认**: waiting_for_user 释放租约，保留预算
- ✅ **确认**: resume 重新认领更高 token
- ✅ **确认**: 取消递增 state_version，使晚到提交失效

**我的建议**: ✅ 接受
- 逻辑一致，保护状态完整性

**你是否同意以上 4 项？**

---

## 签认项 5/7: M06 / 预算账本

**责任**: 确认 action/attempt、预扣/结算、unknown 处理

### 确认要点:

#### 5.1 Action 与 Attempt 稳定关联
```python
# 稳定 action (跨恢复不变)
action_id = f"{run_id}_{epoch}_{node}_{model}"

# 每次真实派发的新 attempt
attempt_id = f"{action_id}_{uuid()}"

# 主备分别预扣
action_primary = f"{action_id}_primary"
action_fallback = f"{action_id}_fallback"
```

**我的建议**: ✅ 接受
- 清晰区分逻辑动作与物理尝试

#### 5.2 预扣与结算幂等
```python
# 派发前预扣
await reserve_budget(
    action_id=action_id,
    attempt_id=attempt_id,
    reservation_microunits=estimated_cost
)

# 返回后结算
await settle_budget(
    attempt_id=attempt_id,
    reported_input_tokens=100,
    reported_output_tokens=50,
    reported_cost_microunits=actual_cost
)
```

**关键约束**:
- ✅ 预扣失败 → 不派发
- ✅ 结算幂等 → 重复调用不重复扣费
- ✅ 零用量 → 必须有 reported 依据

**我的建议**: ✅ 接受
- 幂等机制保证预算准确性

#### 5.3 Unknown 用量处理
```python
# dispatching 后崩溃
if status == 'dispatching':
    status = 'unreconciled'
    # 保守保留预扣
    ledger.unknown += reservation

# 晚到响应
if late_response and has_valid_attempt_id:
    # 只补用量，不改终态
    await reconcile_usage(attempt_id, actual_usage)
```

**我的建议**: ✅ 接受
- Unknown 保守处理防止预算泄漏

#### 5.4 晚到对账入口
```python
# 独立对账接口 (M06 权限)
POST /internal/provider-attempts/{attempt_id}/reconcile
{
  "reported_tokens": 100,
  "reported_cost_microunits": 50,
  "evidence": "provider_response_id"
}
```

**约束**:
- ✅ 只更新用量，不改 Run 终态
- ✅ 需要原 attempt_id 身份验证
- ✅ 不接受任意客户端用量

**我的建议**: ✅ 接受
- 对账入口有助于审计和成本优化

**你是否同意以上 4 项？**

---

## 签认项 6/7: M11 / 测试与验收

**责任**: 确认故障矩阵、权限验证、备份演练

### 确认要点:

#### 6.1 真实 PG 故障矩阵

**计划测试** (04-F):
```
1. 租约到期接管 - A 暂停，B 接管，A 的写入被拒绝
2. 并发认领竞争 - 只有一个获得有效 token
3. Checkpoint 崩溃恢复 - 从已确认版本恢复，孤儿不授权
4. 事务回滚 - 任一写入失败，零公开正文
5. Outbox 重放 - 崩溃后稳定 seq，重连不重复消息
6. 取消与提交竞争 - 只有一个终态
7. 版本不匹配 - fail closed，不静默升级
```

**环境要求**:
- 真实 PostgreSQL 12+
- 多进程并发执行
- 网络延迟模拟

**我的建议**: ✅ 接受测试计划，但注意：
- ⚠️ **当前限制**: 需要真实 PG 环境（本地 Docker 可以）
- ⚠️ **时间估算**: 完整故障矩阵约需 2-3 天编写和验证

**你是否接受这个测试计划？是否先用 Docker PG 验证？**

#### 6.2 权限验证
- ✅ Runner 不能读取审计表
- ✅ Dispatcher 不能修改业务数据
- ✅ 应用角色不能直接写 checkpoint

**我的建议**: ✅ 接受
- 需要在真实 PG 上执行负向测试

#### 6.3 备份与恢复演练
```bash
# 备份
pg_dump -F c -f pivot_backup.dump pivot

# 加密
gpg --encrypt --recipient agent-key pivot_backup.dump

# 恢复到新环境
gpg --decrypt pivot_backup.dump.gpg | pg_restore -d pivot_new

# 验证
- 终态 Run 可回放事件
- 非终态 Run 不自动恢复（需要手动决策）
- Unknown 尝试不自动重发
```

**我的建议**: ✅ 接受
- 定期演练（建议季度一次）

**你是否同意备份策略？**

#### 6.4 证据归档
- ✅ `evidence/agent-m03/` (M03 负责的实现)
- ✅ 每个子票独立证据文档
- ✅ 包含测试输出、命令、截图

**我的建议**: ✅ 接受

---

## 签认项 7/7: Owner / 业务运维安全

**责任**: 最终批准 DR-011 决策

### 关键决策点:

#### 7.1 DR-011 正式决策

**决策内容**:
> 采用 PostgreSQL + Fenced Saver 作为 Agent 持久化方案，支持崩溃恢复、租约管理和事件一致性。

**理由**:
- PostgreSQL 提供事务保证
- Fencing 机制防止并发冲突
- Outbox 模式保证事件发布
- 成熟的备份和恢复工具

**替代方案及拒绝理由**:
- Redis: 无事务保证，内存限制
- MongoDB: 弱一致性，复杂的事务语义
- 文件系统: 无并发控制，难以查询

**我的建议**: ✅ 批准 DR-011
- PostgreSQL 是成熟稳定的选择
- 社区支持好，工具丰富

**你是否批准 DR-011？**

#### 7.2 生产数值批准

| 策略 | 推荐值 | 理由 |
|------|--------|------|
| 租约时长 | 5 分钟 | 足够完成一轮模型调用 |
| 续期间隔 | 30 秒 | 10次续期机会，容错充分 |
| Checkpoint 保留期 | 30 天 | 覆盖一个月的调试需求 |
| 已终态保留 | 7 天 | 提前清理节省存储 |
| 幂等记录保留 | 7 天 | 与 03-A 一致 |
| 已清理 Run tombstone | 90 天 | 防止旧任务复活 |

**我的建议**: ✅ 采纳以上推荐值
- 数值经过工程经验验证
- 可根据实际运行调整

**你是否批准这些生产数值？需要调整吗？**

#### 7.3 密钥管理方案

**选项**:
- A. AWS KMS (生产推荐，但需要 AWS 账户)
- B. HashiCorp Vault (自托管，适合私有部署)
- C. 文件加密 (仅开发，生产禁用)

**我的建议**:
- 当前阶段: **选项 C** (明确标注 dev-only)
- 生产环境: 强制 fail closed，要求配置 KMS 或 Vault

**你选择哪个方案？**

#### 7.4 运行范围

**Agent 持久化模式启用条件**:
- ✅ PostgreSQL 已配置且连接正常
- ✅ 密钥服务可用
- ✅ 租约/保留策略已配置
- ✅ 数据库角色权限已设置

**Fail Closed 策略**:
- 缺少任一必需配置 → Agent 模式不可用
- 降级为线性 RAG 或明确错误

**我的建议**: ✅ 接受
- 安全优先，不允许部分配置

**你是否同意？**

#### 7.5 上线与回滚批准

**上线门槛** (全部满足):
- ✅ 04-A/B/C/D/E 全部完成
- ✅ 故障矩阵测试通过
- ✅ 备份演练成功
- ✅ 监控和告警就绪

**回滚方案**:
1. 关闭新 Agent 受理
2. Fence 活跃租约
3. 排空执行队列
4. 切换回内存模式（如仍可用）
5. 保留数据不删除

**我的建议**: ✅ 接受
- 渐进式上线，风险可控

**你是否批准上线计划？**

---

## 签认决策总结

### 需要你立即决策的问题 (7个)

1. **生产数值**: 租约5分钟/续期30秒/保留30天 - 是否批准？
2. **Saver fencing**: 接受技术风险，需审计 LangGraph 源码 - 是否同意？
3. **DDL 优化**: 索引/分区/加密建议 - 是否采纳？
4. **密钥方案**: KMS/Vault/文件加密 - 选哪个？
5. **Checkpoint 保留期**: 30天是否合适？
6. **测试环境**: Docker PG 是否足够？
7. **DR-011**: 是否正式批准 PostgreSQL 持久化方案？

### 我的总体建议

✅ **批准 04-A 契约**，条件是：
1. 采纳 DDL 优化建议（索引/分区）
2. 明确密钥方案（建议当前用文件，生产要求 KMS）
3. 完成 LangGraph 源码审计（04-C 实施前）
4. 先在 Docker PG 上验证，再上生产

**风险评估**: 中等
- ✅ PostgreSQL 技术成熟
- ⚠️ Fencing 实现复杂，需要仔细测试
- ⚠️ 数据迁移需要谨慎规划

---

## 下一步行动

如果你批准 04-A:
1. 立即: 正式签认 04-A，发布 AGENT-PERSISTENCE 0.1.0
2. 本周: 开始 04-B (结果事务实现)
3. 下周: 开始 04-C (PostgreSQL Checkpointer 实现)
4. 2周后: 04-D (租约与 fencing 实现)

**请告诉我你对以上 7 个问题的决定，我会完成 04-A 的正式签认。**
