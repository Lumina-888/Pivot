# AGENT-BUDGET-0.1.0 — DR-010 预算策略与累计用量契约

**契约 ID**: AGENT-BUDGET  
**版本**: 0.1.0  
**发布日期**: 2026-10-12  
**状态**: released  

## 签认记录

| 角色 | 签认人 | 日期 | 记录 ID |
|---|---|---|---|
| Owner | lumina888 | 2026-10-06 | OWNER-02-B-20261006 |
| 消费者 (M00/M05/M06/M11) | lumina888 | 2026-10-11 | CONSUMER-02-B-20261011 |

- **输入 commit**: `e06fb6f08b3f1a88a8ea9b6ca80a19e6e3e49e8e`
- **技术验证**: Phase 3 预算门禁测试通过
- **提案版本**: AGENT-BUDGET-0.1-draft.3
- **工单**: ND-AGENT-02-B

## 适用范围

本契约定义：
- DR-010 预算策略与执行前门禁
- 累计用量账本与预扣结算
- 调用/图分工与熔断机制
- 重写、重试、主备、恢复的预算共享

关联 DR-010，但生产数值仍 TBD-P0，不批准运行。

## 预算维度

| 维度 | 单位 | 硬限制 | 辅助限制 |
|---|---|---|---|
| 模型调用次数 | 次 | ✅ 执行前门禁 | |
| 工具调用次数 | 次 | ✅ 执行前门禁 | |
| 总 token 数 | token | ✅ 执行前门禁 | |
| 总费用 | USD | ✅ 执行前门禁 | |
| 单步时长 | 秒 | ✅ 执行前门禁 | |
| 总时长 | 秒 | ✅ 执行前门禁 | |
| 观察长度 | token | ✅ 执行前截断 | |
| 并发请求 | 个 | ✅ 排队/拒绝 | |
| recursion_limit | super-step | | ⚠️ 辅助熔断 |

## 核心原则

### 1. 执行前预算门禁（硬约束）
```
每次真实调用前：
  IF 剩余预算 < 本次预估成本:
    拒绝执行，返回预算耗尽错误
  ELSE:
    预扣预算 → 执行 → 结算实际用量
```

### 2. 独立累计账本
- 每个 Run 维护一个累计账本
- 重写、重试、主备切换共享同一账本
- 恢复时从 checkpoint 加载累计值
- **不清零、不豁免、不绕过**

### 3. 调用/图分工
- **调用层（M05/M06）**: 实际 API 调用硬门禁、用量登记、单步超时
- **图层（LangGraph）**: recursion_limit 辅助防循环、熔断
- **分离原因**: recursion_limit 恢复行为为 limit+2，不可作为精确累计

### 4. Unknown 用量处理
- 供应商未返回用量时标记 `usage_mode=explicit_unknown`
- Unknown 不记零，不作为免费通行证
- 批准前 unknown 策略 pending，不启用调用

## 预算策略结构

```json
{
  "max_model_calls": 10,
  "max_tool_calls": 20,
  "max_total_tokens": 50000,
  "max_cost_usd": 1.0,
  "max_step_duration_seconds": 30,
  "max_total_duration_seconds": 300,
  "max_observation_tokens": 4000,
  "max_concurrent_runs": 5,
  "recursion_limit": 15
}
```

**注意**: 以上为示例值，生产数值 TBD-P0。

## 预算账本结构

```json
{
  "consumed": {
    "model_calls": 3,
    "tool_calls": 5,
    "total_tokens": 12000,
    "cost_usd": 0.24,
    "duration_seconds": 45
  },
  "unknown_usage_count": 0,
  "last_checkpoint_at": "2026-10-12T10:30:00Z"
}
```

## 重写与查询改写分离

| 类型 | 限制 | 计入预算 |
|---|---|---|
| **输入重写** (PR-01) | 独立追踪 | ✅ 模型调用计数 |
| **查询改写** (query rewrite) | 最多 2 次 | ✅ 模型调用计数 |
| **澄清** (clarify) | 最多 1 轮 | ✅ 模型调用计数 |

三者独立计数，不相互清零或绕过。

## 故障/重试策略

### 可重试错误
- 超时（504）
- 速率限制（429）
- 临时 5xx（500、502、503）
- 网络错误

### 不可重试错误
- 非法格式（400）
- 权限拒绝（403）
- 外发禁止（内部策略）
- 预算耗尽（内部策略）

### 重试约束
- 每次重试消耗预算（包括失败尝试）
- 主备切换共享预算
- 恢复后继续使用原累计账本

## 恢复与预算

1. **恢复时加载**: 从 AgentState 恢复累计账本
2. **不重置**: 恢复不清零预算，继续累计
3. **版本固定**: 策略版本与 Run 绑定，恢复时校验
4. **预扣幂等**: 相同 action 重放按原身份对账，不重复预扣

## recursion_limit 说明

**技术发现**: 
- `invoke(config, limit=3)` → 执行 3 个 tick
- `invoke(None, config)` 恢复 → 又执行 5 个 tick (limit+2)
- 累计不是 5，而是 8

**因此**:
- ❌ 不能作为精确累计硬限制
- ✅ 仅作为辅助熔断机制
- ✅ 硬限制由调用层独立维护

## 观察截断

- 检索结果按 `max_observation_tokens` 截断
- 截断后设置 `truncated=true`
- 不影响预算计算（按实际用量）
- 历史消息按上下文窗口策略保留

## 未批准事项

本契约已签认，但以下待确认：
- 生产环境具体数值（TBD-P0）
- Unknown 用量的具体策略
- 并发控制的排队/拒绝逻辑
- 观察截断的具体算法
- 期限策略（Run 最长生命周期）

因此不批准生产启用或调用真实付费 API。

## 后续依赖

- **内部接口**: AGENT-INTERNAL-0.1.0
- **依赖锁定**: AGENT-DEPENDENCIES-0.1.0
- **恢复实现**: ND-AGENT-03-D（需 AGENT-RESUME）
- **持久化对账**: ND-AGENT-04-E（需 AGENT-PERSISTENCE）

## 参考文档

- [提案详情](../changes/20261002-M05-agent-budget-contract.md)
- [Owner 确认（严格费用方向）](../approvals/20261006-02-b-strict-cost-direction.md)
- [Owner 确认（调用/图分工）](../approvals/20261006-02-b-call-graph-separation.md)
- [消费者签认](../approvals/20261011-02-b-consumer-signoff.md)
- [技术证据](../../evidence/agent-m05/nd-agent-02-b.md)
