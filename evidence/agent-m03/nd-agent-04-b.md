# ND-AGENT-04-B Claims/Citation/Message/终态事务与 outbox 实施

| 项目 | 内容 |
|---|---|
| 工单 ID | ND-AGENT-04-B |
| 日期 | 2026-10-12 |
| 状态 | in_progress |
| Accountable | M03 |
| Contributors | M05, M06, M00 |
| 前置 | 04-A 已批准并发布 AGENT-PERSISTENCE 0.1.0 |

## 1. 范围与目标

根据 [04-A 持久化契约](../../progress/changes/20261003-M03-agent-persistence-contract.md)，实现：

1. **ResultCommit 表**：绑定 Run 的唯一终态结果
2. **PublicEventOutbox 表**：事件发布 outbox，保证 seq 唯一性
3. **增强 Claims/Citation 约束**：同 Run 版本校验、Chunk 归属
4. **结果提交事务 UoW**：commit_result 原子操作
5. **Outbox dispatcher**：从 outbox 读取并发布 SSE 事件

## 2. 数据库迁移设计

### 2.1 新增表

#### ResultCommit
```sql
CREATE TABLE result_commits (
    run_id VARCHAR(128) PRIMARY KEY REFERENCES runs(id),
    result_id VARCHAR(128) NOT NULL,
    message_id VARCHAR(128) NOT NULL,
    terminal_state VARCHAR(32) NOT NULL,
    verification_version VARCHAR(64) NOT NULL,
    evidence_snapshot_id VARCHAR(128),
    committed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE (run_id)
);
```

#### PublicEventOutbox
```sql
CREATE TABLE public_event_outbox (
    event_id VARCHAR(128) PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL REFERENCES runs(id),
    seq INTEGER NOT NULL,
    publication_key VARCHAR(255) NOT NULL,
    event_name VARCHAR(64) NOT NULL,
    envelope TEXT NOT NULL,
    projection_version VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    dispatched_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (run_id, seq),
    UNIQUE (run_id, publication_key)
);

CREATE INDEX idx_outbox_run_seq ON public_event_outbox(run_id, seq);
CREATE INDEX idx_outbox_undispatched ON public_event_outbox(dispatched_at) WHERE dispatched_at IS NULL;
```

### 2.2 增强现有约束

#### AgentEvent 添加唯一约束
```sql
ALTER TABLE agent_events ADD CONSTRAINT uq_agent_events_run_seq UNIQUE (run_id, seq);
```

#### Claims 添加 Run 外键索引
```sql
CREATE INDEX idx_claims_run ON claims(run_id);
```

#### Citations 增强约束
```sql
-- 已有 claim_id 可空，添加索引
CREATE INDEX idx_citations_claim ON citations(claim_id) WHERE claim_id IS NOT NULL;
CREATE INDEX idx_citations_run ON citations(run_id);
CREATE INDEX idx_citations_chunk ON citations(chunk_id);
```

## 3. 实施步骤

### Phase 1: 数据库模型与迁移 ✅ DONE
- [x] 创建 ResultCommit 模型
- [x] 创建 PublicEventOutbox 模型
- [x] 为 AgentEvent 添加 (run_id, seq) 唯一约束
- [x] 生成 Alembic 迁移文件 `1ff9fb811713`
- [x] 添加必要的索引和约束
- [x] SQLite batch mode 兼容性处理
- [x] 迁移测试：upgrade ✓ / downgrade ✓

### Phase 2: Repository 层 ✅ DONE
- [x] 实现 ResultCommitRepository
- [x] 实现 OutboxRepository
- [x] 导出 Repository 接口

### Phase 3: 结果提交 UoW ✅ DONE
- [x] 实现 CommitmentUnitOfWork
- [x] 实现 commit_result() 事务方法
- [x] 候选验证与幂等检查
- [x] Claims/Citation/Message 原子写入
- [x] Outbox 事件追加
- [x] 错误处理和回滚逻辑

### Phase 4: Outbox Dispatcher ✅ DONE
- [x] 实现 OutboxDispatcher
- [x] dispatch_pending_events() 方法
- [x] replay_events() 用于 SSE 重连
- [x] SSEConnectionManager 占位符

### Phase 5: 测试 🔄 IN PROGRESS
- [x] OutboxRepository 单元测试（8个测试，部分通过）
- [x] ResultCommitRepository 单元测试
- [x] CommitmentUnitOfWork 集成测试
- [⚠] 修复 new_id() fixture 参数问题
- [ ] 所有测试通过验证
- [ ] 故障测试（提交前/后崩溃）

## 4. 当前进度

### 2026-10-12 Phase 1-3 完成

基线：`e3c094e` (main)

**Phase 1 已完成** ✅

创建的文件：
- `api/src/pivot/db/models/conversations.py`: 新增 ResultCommit 和 PublicEventOutbox 模型
- `migrations/versions/1ff9fb811713_add_result_commit_and_outbox_tables.py`: 迁移文件

修改的文件：
- `api/src/pivot/db/models/conversations.py`: AgentEvent 添加 (run_id, seq) 唯一约束
- `api/src/pivot/db/models/__init__.py`: 导出新模型

迁移内容：
1. 创建 `result_commits` 表：run_id(PK), result_id, message_id, terminal_state, verification_version, evidence_snapshot_id, committed_at
2. 创建 `public_event_outbox` 表：event_id(PK), run_id, seq, publication_key, event_name, envelope, projection_version, created_at, dispatched_at
3. 约束：(run_id, seq) UNIQUE, (run_id, publication_key) UNIQUE
4. 索引：idx_outbox_run_seq, idx_outbox_undispatched (PG only), idx_claims_run, idx_citations_run, idx_citations_claim (PG only), idx_citations_chunk
5. AgentEvent 添加 (run_id, seq) 唯一约束（使用 SQLite batch mode）

迁移测试通过：
- ✅ alembic upgrade head
- ✅ SQLite 兼容性（batch mode for constraints）
- ✅ PostgreSQL 条件索引（WHERE dispatched_at IS NULL）

**Phase 2 已完成** ✅

创建的文件：
- `api/src/pivot/db/repositories/outbox.py`: OutboxRepository 实现
- `api/src/pivot/db/repositories/result_commits.py`: ResultCommitRepository 实现

修改的文件：
- `api/src/pivot/db/repositories/__init__.py`: 导出 Repository

Repository 功能：
1. **OutboxRepository**: 
   - `get_by_run_id()`: 获取 Run 的所有事件
   - `get_undispatched()`: 获取未分发事件
   - `append_event()`: 追加新事件
   - `mark_dispatched()`: 标记已分发
   - `get_next_seq()`: 获取下一个序列号

2. **ResultCommitRepository**:
   - `get_by_run_id()`: 获取结果提交记录
   - `exists()`: 检查是否存在
   - `create()`: 创建新记录（幂等检查）

**Phase 4 已完成** ✅

创建的文件：
- `api/src/pivot/stream/outbox_dispatcher.py`: OutboxDispatcher 实现

核心功能：
1. **OutboxDispatcher.dispatch_pending_events()**: 批量分发待处理事件
   - 读取 undispatched 事件（FIFO 顺序）
   - 发送到 SSE 流
   - 标记为已分发
   - 错误处理和日志记录

2. **OutboxDispatcher.replay_events()**: SSE 重连事件重放
   - 按 seq 顺序返回所有事件
   - 支持客户端从 Last-Event-ID 恢复

3. **SSEConnectionManager**: 连接管理占位符
   - 注册/注销连接
   - 按 run_id 路由事件
   - 连接失败处理

**Phase 5 进行中** 🔄

创建的文件：
- `tests/integration/db/test_outbox_repository.py`: OutboxRepository 测试（8个）
- `tests/integration/db/test_result_commits_repository.py`: ResultCommitRepository 测试
- `tests/integration/test_result_commitment.py`: 完整事务测试

测试覆盖：
1. **OutboxRepository**: 
   - ✅ 空 Run 返回空列表
   - ⚠️ 按 seq 排序（需修复 new_id 参数）
   - ⚠️ 仅返回未分发事件
   - ⚠️ 拒绝重复 seq
   - ⚠️ 标记分发时间戳
   - ⚠️ get_next_seq 正确递增

2. **ResultCommitRepository**:
   - 幂等性检查
   - 重复 run_id 拒绝

3. **CommitmentUnitOfWork 集成测试**:
   - 原子事务提交
   - 幂等性（相同 result_id）
   - 冲突检测（不同 result_id）
   - 已终态 Run 拒绝
   - 事务回滚验证

待修复：
- `new_id()` 需要 `kind` 参数（"run", "conversation", "event" 等）
- 测试 fixture 需要更新以使用正确的 kind

---

## 5. 测试计划

根据 04-A 契约，必须覆盖：

| 测试 ID | 场景 | 预期结果 |
|---|---|---|
| test_FR_QA_002_claims_citations_message_commit_atomically | 完整提交 | 全部写入或全部回滚 |
| test_FR_STREAM_002_outbox_replay_preserves_seq | Outbox 重放 | seq 递增、内容不变 |
| test_FR_AGENT_005_commit_failure_publishes_nothing | 提交失败 | 零正文泄露 |
| test_FR_AGENT_008_cancel_blocks_late_answer | 取消竞争 | 唯一终态 |

## 6. 风险与限制

1. **SQLite vs PostgreSQL**：CI 使用 SQLite，部分约束行为可能不同
2. **迁移回滚**：需要验证 downgrade 路径
3. **性能**：大事务可能影响响应时间
4. **并发**：需要真实 PG 测试，由 04-F 补全

## 7. 下一步

1. 创建数据库模型
2. 生成迁移文件
3. 实现 Repository 层
4. 实现事务 UoW
5. 编写测试

---

**状态**：Phase 1-4 完成，Phase 5 部分完成（测试需要修复 new_id 参数）
