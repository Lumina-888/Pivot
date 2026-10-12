# 04-B~F 持久化实施下一步任务清单

## 当前状态 (2026-10-12)

- ✅ **04-B**: Phase 1-4 完成，Phase 5 部分完成
- 🔄 **04-C**: Phase 1-2 完成，Phase 3-5 待实施
- ⏳ **04-D**: 未开始
- ⏳ **04-E**: 未开始
- ⏳ **04-F**: 未开始

**最新提交**: `bfe07da` - feat(agent): implement 04-B result commit UoW and 04-C checkpoint framework

---

## 优先级 1: 04-B 测试修复与验证

### 任务 1.1: 修复测试 fixture
**优先级**: P0  
**预计时间**: 30 分钟

**问题**:
- 测试中 `new_id()` 调用缺少 `kind` 参数
- 需要正确传入 "run", "conversation", "event" 等

**文件**:
- `tests/integration/db/test_outbox_repository.py`
- `tests/integration/db/test_result_commits_repository.py`
- `tests/integration/test_result_commitment.py`

**操作**:
```bash
cd Projects/Pivot
# 全局替换测试中的 new_id() 调用
# conversation: new_id("conversation")
# run: new_id("run")
# event: new_id("event")
# checkpoint: new_id("checkpoint")
```

### 任务 1.2: 运行完整测试套件
**优先级**: P0  
**预计时间**: 15 分钟

**操作**:
```bash
cd Projects/Pivot
source .venv/bin/activate
python -m pytest tests/integration/db/test_outbox_repository.py -v
python -m pytest tests/integration/db/test_result_commits_repository.py -v
python -m pytest tests/integration/test_result_commitment.py -v
```

**验收标准**:
- 所有测试通过
- 无跳过或失败的测试

### 任务 1.3: 添加故障测试
**优先级**: P1  
**预计时间**: 1 小时

**测试场景**:
1. **提交前崩溃**: 事务回滚，无数据泄露
2. **提交后崩溃**: 结果已持久化，可重入
3. **并发提交**: 幂等性检查生效
4. **FK 约束失败**: 完整回滚

**新增文件**:
- `tests/integration/test_result_commit_failures.py`

---

## 优先级 2: 04-C 恢复逻辑实现

### 任务 2.1: 版本兼容性检查器
**优先级**: P0  
**预计时间**: 1 小时

**功能**:
- 读取 RunExecution 版本锁定
- 验证当前环境版本匹配
- Fail closed：版本不匹配拒绝恢复

**新增文件**:
- `api/src/pivot/agent/version_check.py`

**接口**:
```python
class VersionChecker:
    def verify_compatibility(
        self, 
        execution: RunExecution,
        current_versions: dict[str, str]
    ) -> VersionCheckResult:
        """Verify all versions match. Fail closed on mismatch."""
```

### 任务 2.2: 恢复上下文重建
**优先级**: P0  
**预计时间**: 2 小时

**功能**:
- 读取最新确认的 checkpoint
- 重建 active/owner/scope/文档资格
- 恢复累计 ledger 和预算
- execution_epoch 递增

**新增文件**:
- `api/src/pivot/agent/recovery.py`

**接口**:
```python
class RecoveryManager:
    def recover_from_checkpoint(
        self,
        run_id: str,
        lease_token: int
    ) -> RecoveredContext:
        """Recover Run from latest confirmed checkpoint."""
```

### 任务 2.3: State 加密集成 (占位符)
**优先级**: P2  
**预计时间**: 2 小时

**功能**:
- 集成 OpenBao 密钥管理
- 加密敏感 State 字段
- 解密恢复时读取

**依赖**:
- OpenBao 配置就绪 (已完成)
- 密钥管理策略确定 (TBD)

**操作**:
- 先实现占位符，暂不真实加密
- 04-D 或后续补充完整实现

### 任务 2.4: 测试套件
**优先级**: P1  
**预计时间**: 2 小时

**测试场景**:
1. **checkpoint 写入与绑定**
2. **版本不匹配拒绝**
3. **恢复重建上下文**
4. **fencing 保护**（待 04-D lease 实现）

**新增文件**:
- `tests/integration/test_checkpoint_writer.py`
- `tests/integration/test_recovery.py`

---

## 优先级 3: 04-D 数据库租约与 fencing

### 任务 3.1: Lease 表与模型
**优先级**: P0  
**预计时间**: 1 小时

**数据库模型**:
```sql
CREATE TABLE run_leases (
    run_id VARCHAR(128) PRIMARY KEY REFERENCES runs(id),
    executor_id VARCHAR(255) NOT NULL,
    fencing_token INTEGER NOT NULL,
    acquired_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    renewed_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (run_id, fencing_token)
);
```

**功能**:
- 租约获取 (claim)
- 租约续期 (renew)
- 租约释放 (release)
- 过期检查

### 任务 3.2: 租约管理器
**优先级**: P0  
**预计时间**: 2 小时

**新增文件**:
- `api/src/pivot/agent/lease.py`

**接口**:
```python
class LeaseManager:
    def claim_lease(self, run_id: str, executor_id: str, duration: timedelta) -> LeaseToken
    def renew_lease(self, run_id: str, token: int) -> bool
    def release_lease(self, run_id: str, token: int) -> None
    def verify_lease(self, run_id: str, token: int) -> bool
```

### 任务 3.3: 集成 FencedCheckpointWriter
**优先级**: P0  
**预计时间**: 1 小时

**操作**:
- 将 04-C 的 fencing_token 占位符替换为真实租约检查
- 调用 LeaseManager.verify_lease()
- 租约过期抛出 LeaseViolationError

### 任务 3.4: 测试套件
**优先级**: P1  
**预计时间**: 2 小时

**测试场景**:
1. **租约获取与续期**
2. **租约过期拒绝写入**
3. **并发租约冲突**
4. **fencing token 递增**

---

## 优先级 4: 04-E ProviderCall 尝试与用量对账

### 任务 4.1: ProviderAttempt 模型
**优先级**: P0  
**预计时间**: 1 小时

**数据库模型**:
```sql
CREATE TABLE provider_attempts (
    id VARCHAR(128) PRIMARY KEY,
    provider_call_id VARCHAR(128) NOT NULL REFERENCES provider_calls(id),
    attempt_number INTEGER NOT NULL,
    action VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL,
    dispatched_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost_microunits INTEGER,
    UNIQUE (provider_call_id, attempt_number)
);
```

### 任务 4.2: 预扣与结算逻辑
**优先级**: P0  
**预计时间**: 2 小时

**功能**:
- 派发前预扣 reservation
- 返回后幂等结算
- unknown 尝试保守处理

**新增文件**:
- `api/src/pivot/agent/budget_ledger.py`

### 任务 4.3: 对账入口
**优先级**: P1  
**预计时间**: 1 小时

**功能**:
- 晚到响应补用量
- 验证 attempt 身份
- 不续租、不改终态

### 任务 4.4: 测试套件
**优先级**: P1  
**预计时间**: 2 小时

---

## 优先级 5: 04-F 真实 PG 故障测试矩阵

### 任务 5.1: PostgreSQL 测试环境
**优先级**: P0  
**预计时间**: 1 小时

**操作**:
- 配置真实 PostgreSQL 数据库
- 运行所有迁移
- 验证约束和索引

### 任务 5.2: 并发竞争测试
**优先级**: P0  
**预计时间**: 2 小时

**测试场景**:
1. **多进程同时认领租约**
2. **并发提交结果**
3. **租约过期与新认领竞争**

### 任务 5.3: 崩溃恢复测试
**优先级**: P1  
**预计时间**: 2 小时

**测试场景**:
1. **checkpoint 写入中崩溃**
2. **结果提交中崩溃**
3. **租约续期中崩溃**

---

## 时间估算

| 工单 | 剩余任务 | 预计时间 |
|------|---------|---------|
| 04-B | 测试修复与验证 | 2 小时 |
| 04-C | 恢复逻辑实现 | 8 小时 |
| 04-D | 租约与 fencing | 6 小时 |
| 04-E | 预算对账 | 6 小时 |
| 04-F | 故障测试 | 5 小时 |
| **总计** | | **27 小时** (~3-4 天) |

---

## 依赖关系

```
04-B (测试修复) → 可独立完成
    ↓
04-C (恢复逻辑) → 依赖 04-B 完成
    ↓
04-D (租约) → 依赖 04-C，补充 fencing
    ↓
04-E (预算) → 依赖 04-D，使用租约
    ↓
04-F (故障测试) → 依赖全部，集成验证
```

---

## 下一次会话建议

**立即执行**:
1. 修复 04-B 测试 fixture (30 分钟)
2. 运行完整测试套件 (15 分钟)
3. 开始 04-C 恢复逻辑 (2 小时)

**本周目标**:
- 完成 04-B 测试
- 完成 04-C Phase 3-5
- 开始 04-D 租约实现

**下周目标**:
- 完成 04-D/E
- 开始 04-F 故障测试

---

**更新时间**: 2026-10-12  
**负责**: M03  
**基线**: `bfe07da`
