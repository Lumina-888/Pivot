# AGENT-PERSISTENCE Contract v0.1.0

| 项目 | 内容 |
|---|---|
| 契约 ID | AGENT-PERSISTENCE |
| 版本 | 0.1.0 |
| 发布日期 | 2026-10-12 |
| 状态 | **released** |
| 基础提案 | AGENT-PERSISTENCE-0.1-draft.1 |
| 签认文档 | [20261012-04-a-approved.md](../approvals/20261012-04-a-approved.md) |
| 适用范围 | Agent checkpoint/租约/事实/outbox 内部契约 |

## 1. 发布摘要

本契约定义 Agent 持久化的内部机制，支持崩溃恢复、租约管理和事件一致性。这是**内部契约**，不改变公开 API (contract-v0.2)。

**核心能力**:
- PostgreSQL Checkpointer 支持崩溃恢复
- 租约与 Fencing 防止并发冲突
- 结果事务保证原子提交
- Outbox 模式保证事件一致性
- 预算账本支持恢复对账

**关键约束**:
- 租约时长 10 分钟，续期间隔 30 秒
- Checkpoint 保留 30 天，已终态 7 天
- OpenBao 或 AWS KMS 加密（生产必需）
- 固定版本恢复，不静默升级

## 2. DR-011 架构决策

**决策**: 采用 PostgreSQL + Fenced Saver 作为 Agent 持久化方案

**理由**:
- PostgreSQL 提供 ACID 事务保证
- Fencing 机制防止多进程并发冲突
- Outbox 模式保证事件最终一致性
- 成熟的备份和恢复工具

**批准**: Owner (2026-10-12)

## 3. 数据库对象

### 3.1 核心表

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

-- 租约与 Fencing
CREATE TABLE execution_lease (
    run_id VARCHAR(128) PRIMARY KEY REFERENCES run_execution(run_id),
    executor_id VARCHAR(128) NOT NULL,
    fencing_token INTEGER NOT NULL DEFAULT 1,
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT token_positive CHECK (fencing_token > 0)
);
CREATE INDEX idx_lease_expires ON execution_lease(expires_at) 
    WHERE expires_at > NOW();

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
) PARTITION BY RANGE (EXTRACT(EPOCH FROM NOW()));
CREATE INDEX idx_outbox_undispatched ON public_event_outbox(run_id, seq) 
    WHERE dispatched_at IS NULL;

-- 恢复受理（扩展 03-A）
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
    action VARCHAR(32) NOT NULL,
    intent_data JSONB NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    claimed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_intent_pending ON execution_intent(status, created_at) 
    WHERE status = 'pending';

-- 供应商尝试
CREATE TABLE provider_attempt (
    attempt_id VARCHAR(128) PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL REFERENCES run_execution(run_id),
    action_id VARCHAR(128) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    reservation_microunits INTEGER NOT NULL,
    reported_input_tokens INTEGER,
    reported_output_tokens INTEGER,
    reported_cost_microunits INTEGER,
    dispatched_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE (run_id, action_id, attempt_id)
);
```

### 3.2 数据库角色

```sql
-- 迁移角色（仅建表）
CREATE ROLE pivot_migration;
GRANT CREATE ON DATABASE pivot TO pivot_migration;

-- Runner 角色（读写执行表）
CREATE ROLE pivot_runner;
GRANT SELECT, INSERT, UPDATE ON TABLE 
    run_execution, execution_lease, checkpoint_binding,
    execution_intent, provider_attempt TO pivot_runner;

-- Dispatcher 角色（只读 outbox）
CREATE ROLE pivot_dispatcher;
GRANT SELECT, UPDATE (dispatched_at) ON TABLE public_event_outbox TO pivot_dispatcher;

-- 审计角色（只读）
CREATE ROLE pivot_audit;
GRANT SELECT ON ALL TABLES TO pivot_audit;
```

## 4. Fencing 机制

### 4.1 租约生命周期

```python
# 认领租约
async def claim_lease(run_id: str, executor_id: str) -> LeaseToken:
    async with db.transaction():
        run = await db.select_for_update("run_execution", run_id=run_id)
        lease = await db.select_for_update("execution_lease", run_id=run_id)
        
        # 检查可认领性
        if lease and lease.expires_at > now():
            raise LeaseConflict("Already held")
        
        # 递增 token
        new_token = (lease.fencing_token + 1) if lease else 1
        new_expires = now() + timedelta(minutes=10)
        
        await db.upsert("execution_lease", {
            "run_id": run_id,
            "executor_id": executor_id,
            "fencing_token": new_token,
            "expires_at": new_expires
        })
        
        return LeaseToken(run_id, new_token, new_expires)

# 续期
async def renew_lease(token: LeaseToken) -> LeaseToken:
    async with db.transaction():
        lease = await db.select_for_update("execution_lease", run_id=token.run_id)
        
        if lease.fencing_token != token.token:
            raise FencingError("Stale token")
        if lease.expires_at < now():
            raise FencingError("Expired")
        
        new_expires = now() + timedelta(minutes=10)
        await db.update("execution_lease", 
            run_id=token.run_id,
            expires_at=new_expires
        )
        
        return LeaseToken(token.run_id, token.token, new_expires)
```

### 4.2 Fenced Saver

```python
class FencedPostgresSaver(PostgresSaver):
    async def put(self, config, checkpoint, metadata):
        token = config["lease_token"]
        expected_version = config["expected_version"]
        
        async with self.db.transaction():
            # Fencing 检查
            lease = await self.db.select_for_update(
                "execution_lease", run_id=token.run_id
            )
            if lease.fencing_token != token.token:
                raise FencingError("Stale executor")
            if lease.expires_at < now():
                raise FencingError("Lease expired")
            
            # 版本检查
            run = await self.db.select("run_execution", run_id=token.run_id)
            if run.state_version != expected_version:
                raise VersionMismatch()
            
            # 加密并保存
            encrypted = await self.encrypt(checkpoint, run.key_ref)
            checkpoint_id = await self.store_checkpoint(encrypted)
            
            # 更新绑定
            await self.db.upsert("checkpoint_binding", {
                "run_id": token.run_id,
                "checkpoint_id": checkpoint_id,
                "state_version": expected_version,
                "fencing_token": token.token
            })
```

## 5. 结果事务

```python
async def commit_result(
    token: LeaseToken,
    expected_version: int,
    result: VerifiedCandidate
) -> ResultReceipt:
    async with db.transaction():
        # 1. Fencing
        await check_lease_and_version(token, expected_version)
        
        # 2. 重新鉴权
        await recheck_authorization(token.run_id, result.evidence_ids)
        
        # 3. 幂等检查
        if existing := await db.select("result_commit", run_id=token.run_id):
            if same_result(existing, result):
                return existing.receipt
            raise ConflictError("Different result")
        
        # 4. 原子写入
        await db.insert_many("claims", result.claims)
        await db.insert_many("citations", result.citations)
        await db.update("messages", message_id=result.message_id, content=result.content)
        await db.update("runs", run_id=token.run_id, status=result.terminal_state)
        await db.insert("result_commit", {
            "run_id": token.run_id,
            "result_id": result.result_id,
            "message_id": result.message_id,
            "terminal_state": result.terminal_state
        })
        
        # 5. Outbox 事件
        events = [
            ("token", seq=1, payload={"text": chunk1}),
            ("citation", seq=2, payload={"citation_id": "..."}),
            ("completed", seq=3, payload={})
        ]
        await db.insert_many("public_event_outbox", [
            {
                "event_id": f"{token.run_id}_{seq}",
                "run_id": token.run_id,
                "seq": seq,
                "event_name": name,
                "payload": payload,
                "publication_key": f"{name}_{seq}"
            }
            for name, seq, payload in events
        ])
        
        # 6. 递增版本
        await db.execute(
            "UPDATE run_execution SET state_version = state_version + 1 WHERE run_id = $1",
            token.run_id
        )
        
        return ResultReceipt(token.run_id, result.result_id, result.message_id)
```

## 6. 生产配置

### 6.1 环境变量

```bash
# PostgreSQL
PIVOT_DB_HOST=localhost
PIVOT_DB_PORT=5432
PIVOT_DB_NAME=pivot
PIVOT_DB_USER=pivot_runner
PIVOT_DB_PASSWORD=${DB_PASSWORD}

# OpenBao（生产必需）
PIVOT_ENCRYPTION=openbao
OPENBAO_ADDR=https://vault.local:8200
OPENBAO_TOKEN=${OPENBAO_TOKEN}
OPENBAO_KEY_PATH=secret/pivot/checkpoint-key

# 租约策略
PIVOT_LEASE_DURATION_SECONDS=600        # 10 分钟
PIVOT_LEASE_RENEW_INTERVAL_SECONDS=30   # 30 秒
PIVOT_CHECKPOINT_RETENTION_DAYS=30      # 30 天
PIVOT_TERMINAL_RETENTION_DAYS=7         # 7 天
PIVOT_TOMBSTONE_RETENTION_DAYS=90       # 90 天
```

### 6.2 OpenBao 配置

```yaml
# docker-compose.yml
services:
  openbao:
    image: openbao/openbao:latest
    ports:
      - "8200:8200"
    environment:
      OPENBAO_DEV_ROOT_TOKEN_ID: dev-token
    cap_add:
      - IPC_LOCK
    volumes:
      - openbao-data:/openbao/file
```

```bash
# 初始化
openbao secrets enable -path=secret kv-v2
openbao kv put secret/pivot/checkpoint-key key=$(openssl rand -base64 32)
openbao policy write pivot-runner - <<EOF
path "secret/data/pivot/*" {
  capabilities = ["read"]
}
EOF
```

## 7. 迁移策略

### 7.1 Expand-Migrate-Contract

```
Phase 1: Expand
- 新增所有表和索引
- 不影响现有代码

Phase 2: Migrate
- 迁移旧 Run 的兼容数据（只读）
- 标记旧 Run 为 legacy

Phase 3: Contract（可选）
- 清理旧表（仅测试环境）
- 生产环境保留

Phase 4: Opt-in
- 新 Agent Run 使用新表
- 旧 Run 不可恢复（明确标注）
```

### 7.2 回滚方案

```
1. 关闭新 Agent 受理
2. Fence 活跃租约
3. 排空执行队列
4. 保留数据不删除
5. 切换回内存模式（如可用）
```

## 8. 测试要求

### 8.1 故障矩阵（04-F）

- ✅ 租约到期接管（A 暂停，B 接管，A 写入被拒）
- ✅ 并发认领竞争（只有一个获得有效 token）
- ✅ Checkpoint 崩溃恢复（从已确认版本恢复）
- ✅ 事务回滚（任一写入失败，零公开正文）
- ✅ Outbox 重放（崩溃后稳定 seq）
- ✅ 取消与提交竞争（只有一个终态）
- ✅ 版本不匹配（fail closed）

### 8.2 测试环境

- Docker PostgreSQL 12+
- 多进程并发执行
- 网络延迟模拟

## 9. 实施计划

| 工单 | 工作 | 责任 | 工作量 | 状态 |
|------|------|------|--------|------|
| 04-B | Claims/Citation/Message 事务与 Outbox | M03 | 2-3天 | ⏳ blocked |
| 04-C | PostgreSQL Checkpointer 与 OpenBao | M03 | 3-4天 | ⏳ blocked |
| 04-D | 租约/fencing 与执行入口 | M03 | 2-3天 | ⏳ blocked |
| 04-E | ProviderAttempt 预算账本 | M06 | 2天 | ⏳ blocked |
| 04-F | 故障矩阵测试 | M11 | 3-4天 | ⏳ blocked |

**预计完成**: 2026-11-02（3 周）

## 10. 风险与缓解

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| LangGraph 写入路径遗漏 | 中 | 源码审计 + 完整测试 |
| OpenBao 配置复杂 | 低 | Docker Compose 示例 |
| 数据迁移失败 | 中 | 渐进式 + 备份 |
| 租约死锁 | 低 | 固定锁顺序 |
| 性能下降 | 低 | 索引 + 分区 |
| 密钥泄露 | 高 | 访问控制 + 审计 |

---

**发布批准**: Owner (2026-10-12)  
**下一步**: 开始 04-B 实施
