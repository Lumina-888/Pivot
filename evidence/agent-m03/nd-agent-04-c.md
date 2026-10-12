# ND-AGENT-04-C PostgreSQL Checkpointer 与版本固定恢复实施

| 项目 | 内容 |
|---|---|
| 工单 ID | ND-AGENT-04-C |
| 日期 | 2026-10-12 |
| 状态 | in_progress |
| Accountable | M03 |
| Contributors | M05, M01, M11 |
| 前置 | 04-A 已批准，04-B 完成 |

## 1. 范围与目标

根据 [04-A 持久化契约 §4](../../progress/changes/20261003-M03-agent-persistence-contract.md#4-租约checkpoint-与重放协议)，实现：

1. **CheckpointBinding 表**：绑定 Run 到已确认的 checkpoint
2. **RunExecution 表**：执行元数据（thread、版本、预算游标）
3. **受 fencing 保护的 PostgreSQL Saver**：拦截所有框架写操作
4. **版本固定恢复**：重建可信上下文、验证版本兼容性
5. **State 白名单与加密**：移除敏感数据

## 2. 数据库模型设计

### 2.1 新增表

#### RunExecution
```sql
CREATE TABLE run_executions (
    run_id VARCHAR(128) PRIMARY KEY REFERENCES runs(id),
    thread_id VARCHAR(255) NOT NULL UNIQUE,
    graph_version VARCHAR(64) NOT NULL,
    state_schema_version VARCHAR(64) NOT NULL,
    prompt_version VARCHAR(64) NOT NULL,
    tools_version VARCHAR(64) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    dependencies_lock_version VARCHAR(64) NOT NULL,
    budget_policy_version VARCHAR(64) NOT NULL,
    state_version INTEGER NOT NULL DEFAULT 0,
    execution_epoch INTEGER NOT NULL DEFAULT 0,
    current_checkpoint_id VARCHAR(255),
    budget_ledger_cursor VARCHAR(255),
    original_deadline_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

#### CheckpointBinding
```sql
CREATE TABLE checkpoint_bindings (
    id VARCHAR(128) PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL REFERENCES runs(id),
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    state_version INTEGER NOT NULL,
    execution_epoch INTEGER NOT NULL,
    fencing_token INTEGER NOT NULL,
    graph_version VARCHAR(64) NOT NULL,
    state_schema_version VARCHAR(64) NOT NULL,
    budget_ledger_version VARCHAR(64),
    is_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE (run_id, state_version)
);

CREATE INDEX idx_checkpoint_bindings_run ON checkpoint_bindings(run_id);
CREATE INDEX idx_checkpoint_bindings_confirmed ON checkpoint_bindings(run_id, is_confirmed) 
    WHERE is_confirmed = TRUE;
```

## 3. 实施步骤

### Phase 1: 数据库模型与迁移 ✅ DONE
- [x] 创建 RunExecution 模型
- [x] 创建 CheckpointBinding 模型
- [x] 生成 Alembic 迁移文件
- [x] 迁移测试

### Phase 2: Fenced PostgreSQL Saver ✅ DONE
- [x] FencedCheckpointWriter 适配器
- [x] 拦截写操作并验证 fencing
- [x] 租约和 state_version 检查（租约占位符待 04-D）
- [x] CheckpointBinding 创建和确认
- [x] StateWhitelist 白名单过滤

### Phase 3: 恢复逻辑
- [ ] 读取终态或最新 checkpoint
- [ ] 版本兼容性检查
- [ ] 重建可信上下文
- [ ] 预算对账

### Phase 4: State 安全处理
- [ ] 白名单字段过滤
- [ ] 移除敏感数据（凭证、reasoning）
- [ ] 加密支持（占位符）

### Phase 5: 测试
- [ ] checkpoint 写入与绑定测试
- [ ] 版本不匹配拒绝测试
- [ ] 恢复重建上下文测试
- [ ] fencing 保护测试

## 4. 核心约束

根据 04-A 契约：

1. **Fencing 保护**：所有框架写操作必须检查租约
2. **版本固定**：恢复时验证所有版本兼容
3. **State 安全**：checkpoint 不含凭证、连接对象、reasoning
4. **绑定确认**：只有确认的 checkpoint 可恢复
5. **Fail closed**：版本不匹配时拒绝，不静默切换

## 5. 技术挑战

1. **框架集成**：需要理解 LangGraph Checkpointer 接口
2. **事务协调**：框架表和业务表在不同事务中
3. **异步支持**：需要支持同步和异步 Saver 调用
4. **加密**：需要 OpenBao 集成（后续）

## 6. 待定事项

- [ ] LangGraph 1.2.14 Checkpointer 接口研究
- [ ] 框架表 schema（由 LangGraph 管理）
- [ ] 加密密钥管理策略
- [ ] 租约时长和续期间隔（TBD-P0）

## 7. 当前进度

### 2026-10-12 Phase 1-2 完成

基线：`e3c094e` (main)

**Phase 1 已完成** ✅

创建的文件：
- `api/src/pivot/db/models/execution.py`: RunExecution 和 CheckpointBinding 模型
- `migrations/versions/102d30d04451_add_run_execution_and_checkpoint_.py`: 迁移文件

修改的文件：
- `api/src/pivot/db/models/__init__.py`: 导出新模型
- `api/src/pivot/db/models/conversations.py`: Run 添加 execution 关系

迁移内容：
1. 创建 `run_executions` 表：版本锁定元数据（graph/state/prompt/tools/model/dependencies/budget versions）
2. 创建 `checkpoint_bindings` 表：Run 到 checkpoint 的确认绑定
3. 索引：thread_id, run_id, confirmed bindings (PG conditional)
4. 约束：(run_id, state_version) UNIQUE

迁移测试通过：
- ✅ alembic upgrade head
- ✅ SQLite 兼容性
- ✅ PostgreSQL 条件索引

**Phase 2 已完成** ✅

创建的文件：
- `api/src/pivot/agent/checkpoint.py`: FencedCheckpointWriter 实现

核心功能：
1. **FencedCheckpointWriter.write_checkpoint()**: 受 fencing 保护的 checkpoint 写入
   - SELECT FOR UPDATE 锁定 RunExecution
   - 验证 fencing_token（占位符，待 04-D 租约实现）
   - 验证 state_version
   - 创建未确认的 CheckpointBinding
   - 异常：LeaseViolationError, StateVersionMismatchError

2. **FencedCheckpointWriter.confirm_checkpoint()**: 确认 checkpoint
   - 标记 binding 为已确认
   - 更新 RunExecution.current_checkpoint_id

3. **FencedCheckpointWriter.get_latest_confirmed_binding()**: 获取恢复点
   - 只返回已确认的 binding
   - 按 state_version 降序

4. **StateWhitelist.sanitize()**: State 白名单过滤
   - 移除敏感字段（credentials, tokens, reasoning）
   - 只保留允许字段（messages, claims, citations, budget）

---

**状态**: Phase 1-2 完成 ✅, Phase 3 待开始  
**阻塞**: 需要与 LangGraph PostgresSaver 集成（实际 checkpoint 读写）
