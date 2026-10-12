# 02-B 消费者签认记录

| 字段 | 记录 |
|---|---|
| 记录 ID | CONSUMER-02-B-20261011 |
| 签认人 / 角色 | lumina888 / 项目 Owner 兼任全部消费者角色（M00/M01/M03/M05/M06/M11） |
| 可追溯确认 | 用户明确回复"同意" |
| 记录时间 | 2026-10-12T10:28:00+0800 |
| 审批对象 | AGENT-BUDGET-0.1-draft.3（实际调用硬门禁与图循环熔断分工） |
| 输入 commit | `e06fb6f08b3f1a88a8ea9b6ca80a19e6e3e49e8e` |
| 前置依据 | Owner 严格费用方向（2026-10-06）；Owner 调用/图分工（2026-10-06）；Phase 3 预算耗尽测试通过（eef40df） |
| 结论 / 生效范围 | 同意；消费者签认完成，可进入契约发布准备；生产数值仍为 TBD-P0，需实测后单独批准 |

## 签认内容

### M05/M11（前置接缝）
- ✅ BudgetGate Interface 可实现：reserve/mark_dispatched/settle/snapshot/restore
- ✅ 执行前门禁：每次模型/工具调用前检查并原子预留
- ✅ Phase 3 验证：`test_budget_exhaustion_stops_before_another_model_call` 通过（4 model calls 上限，第 5 次被阻断）
- ✅ 调用/图分工：实际调用负责硬预算，recursion_limit 仅作防循环辅助
- ✅ 技术验证覆盖：单次 invoke、预算耗尽优雅停止、返回特殊状态（不是异常）

### M00（兼容/治理）
- ✅ 策略版本化：schema_version "budget-policy-0.1-draft.3"，policy_id/approval_ref 必填
- ✅ 不进入 contract-v0.1 manifest（仅适用于新 Agent）
- ✅ 不修改现有 api/、worker/、web/、公开 schema/错误码
- ✅ 策略语义校验：拒绝 step_timeout_ms > run_timeout_ms、principal_active_runs_max > active_runs_max

### M06（账本/审计）
- ✅ attempt 级别追踪：(run_id, action_id, attempt_id) 稳定身份
- ✅ 用量分量明确：settled + unreconciled + reserved = 总占用
- ✅ 用量结算形状：usage_status ∈ {reported, unreconciled}；reported 必须完整非负，unreconciled 保留预留上界
- ✅ 幂等结算：同一 attempt 重复结算幂等，矛盾用量则 consistency_invalid
- ✅ 晚到用量对账：按同一 attempt 更新，不覆盖 cancelled/终态

### M03（持久化基础）
- ✅ BudgetSnapshot 结构合理：policy/pricing/token-counter 版本引用、run 绑定、账本 revision、固定 deadline、model/tool 消费、tokens/费用的 settled+unreconciled+reserved 分量、query/rewrite/clarification 游标、稳定 attempt/结算状态
- ✅ 恢复对账：较旧快照不覆盖新消费，无法一致则停止
- ✅ 持久协议待 04-A/E（本次不批准持久化实现）

### M01（授权）
- ✅ 每次调用检查：可信身份/owner/scope 与取消检查 → 最新文档和外发策略检查 → 预算预检/尝试登记 → 实际调用
- ✅ 槽位控制：ExecutionAdmission.acquire/release，部署及 principal 槽位同时原子申请
- ✅ 不绕过身份检查：图/工具代码不得直接调用未经过边界的主备 Adapter
- ✅ 生产并发/租约/fencing 待 04-A/D（本次不批准多进程实现）

### M00/M06/M03/M01（严格费用控制）
- ✅ 执行前预留：输入上界 + 输出上限预扣，超过剩余额度则不派发
- ✅ unknown 用量保留预留：不记零，只有上界仍可信且余量足够才可继续
- ✅ 实际超过预扣或总预算：记录完整超额（不裁成上限），停止新行动，不发布未验证答案
- ✅ fail-closed：缺必需策略、计量能力或用量上界时拒绝，不回退线性 RAG
- ✅ 不退款已派发消费：无法证明未派发的窗口保留次数和预留

### Owner（许可及成本/期限）
- ✅ 接受执行前门禁和 fail-closed 原则
- ✅ deadline 固定、不可续期：由服务端首次受理时固定总期限，排队、等待、恢复均不重置
- ✅ 等待澄清消耗总时长：waiting_for_user 不暂停 deadline
- ✅ 生产数值待实测：tokens_max/cost_microunits_max/observation_chars_max/history_messages_max/context_tokens_max/active_runs_max/retry_max_attempts 仍为 TBD-P0，需实测后单独批准

### 业务/运维（期限语义）
- ✅ 时限机制：使用 monotonic 计时并与可信 UTC deadline 取更小余量，恢复重建计时而不延长 deadline
- ✅ 时钟倒退/期限无法验证 fail closed
- ✅ 生产可信时间/持久期限待 04-A/D

## 已实现的技术验证（Phase 3）

测试用例（commit eef40df）：
- ✅ `test_single_search_structured_answer`：单次搜索 + 结构化答案
- ✅ `test_multiple_retrieval_rounds`：多轮检索（2 次 search + 1 次 read）
- ✅ `test_structured_answer_with_evidence`：结构化答案包含证据引用
- ✅ **`test_budget_exhaustion_stops_before_another_model_call`**：预算耗尽（max_model_calls=4）优雅停止，返回特殊状态 "budget_exhausted"

测试配置（tests/e2e/conftest.py）：
```python
budget_policy = BudgetPolicy(
    max_model_calls=4,
    max_tool_calls=4,
    max_rewrite_count=1,
    timeout_seconds=30
)
```

## 未批准及待完成事项

本次签认完成消费者审核，但以下事项仍 pending：
- 02-C DEPENDENCIES draft.1 签认
- 生产数值确定与单独批准（TBD-P0）
- 02-F/G 实施准入验证（所有路径无绕过、无收费循环有时限/取消/熔断）
- 新增计划 Red 实现（FR_AGENT_004_* 系列 5 个测试）
- 契约发布（M00）
- 03-A 恢复、04-A/D/E 持久化/并发/对账签认
- staging/生产启用
- GATE 放行

因此 02-B 状态更新为 **approved**（Owner + 消费者签认完成），但全局仍需推进 02-C 及后续工单。

## 依据

- [批准版本对应的 02-B 提案](../changes/20261002-M05-agent-budget-contract.md)
- [Owner 严格费用方向确认](20261006-02-b-strict-cost-direction.md)
- [Owner 调用/图分工确认](20261006-02-b-call-graph-separation.md)
- [Phase 3 预算测试](../../tests/e2e/test_agent_complete_flow.py)（commit eef40df）
- [技术证据与审批入口](../../evidence/agent-m03/nd-agent-02-abc-review.md)
