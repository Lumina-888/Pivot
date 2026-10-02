# ADR-009：LangGraph 受控 ReAct Agent 规格基线

- **日期 / 状态**：2026-10-02 / accepted（架构方向和安全不变量；未实现、未验收）。
- **触发**：Owner 明确目标为 ReAct AI Agent、LangGraph 框架，并要求生成正式规格和消除旧文档冲突。
- **Accountable**：M00 治理；Contributors：M01/M03/M04/M05/M06/M08/M09/M11。
- **规范**：[SPEC-1.1](../../SPEC.md)、[AGENT-SPEC-1.0](../../spec/AGENT_SPEC.md)。
- **取代**：SPEC-1.0 §4.5/§7 的固定线性主图；[旧 LangGraph 暂缓申请](20260906-M05-langgraph.md)；ND-W3-09“仅 extra、主图语义不变”的计划。

## 背景

现有实现是纯 Python 线性检索/草稿/校验流程，没有 LangGraph 运行时、模型 tool_calls 或 Observation 后再决策。旧测试通过不代表 ReAct 能力。

排查还复现了自由 Markdown 与证据生成 Claims 不一致却 answered 的问题。当前 Claim/Citation 尚未入库，Run/EventLog 存活不等于 Agent checkpoint 恢复。

## 决策

1. 使用 LangGraph StateGraph 实现原生 tool-calling ReAct 循环，不接受线性函数包装为图作为验收。
2. 首版仅 search_knowledge 与 read_evidence 两个只读工具，身份/scope/外发/预算由服务端决定。
3. 首先修复答案发布门禁：结构化 Claims → 支持校验 → 仅渲染通过事实 → 幂等事务落库 → 发布；首版任一事实未通过则不发布整个候选答案。
4. 保留公开 Run 状态枚举和 SSE 信封；批准 SPEC-1.1 的有限补证/澄清状态转移语义。具体状态机代码、恢复 API 与错误映射需后续 Contract 测试，不能静默新增接口。
5. 一 Run 一 checkpoint thread，PostgreSQL 为业务与持久执行事实基础；执行租约、fencing、事件一致性和副作用幂等必须有集成测试。
6. 公开轨迹只投影脱敏摘要，校验前不发布正式答案 token，不展示完整思考链或内部工具参数。
7. 旧模式只作短期回归/迁移，不静默 fallback；生产 Agent 缺模型能力/必要配置必须 fail closed。
8. 全部 GATE-P0 仍 unverified，架构 accepted 不等于框架已安装、模型已验证或切片全部满足 DoR。

## 未关闭决策

- **DR-010**：工具/模型调用、超时、token/费用、观察长度、recursion_limit、并发的数值；Owner M05/M11，经实测/ADR 冻结。保持 TBD-P0，阻断依赖生产预算的切片。
- **DR-011**：checkpoint 保留/加密/清理/备份、执行租约、迁移与一致性协议；Owner M03/M01/M11，阻断持久恢复验收。
- 框架/供应商适配锁版本、恢复 endpoint/字段、协议非法/预算耗尽的公开错误映射：在各自 Contract 切片冻结。
- 既有 DR-001/004/005/007/008 不因本 ADR 自动关闭。

## 文档处理规则

SPEC.md 保留根路径升级 1.1；Agent 细则放 spec/AGENT_SPEC.md 并由 SPEC §7 引用。更新 MODULE_SPEC、README、AGENTS、PROGRESS、HANDOFF、场景、验收矩阵和后续工单。旧暂缓申请标 superseded；旧技术方案明确降级历史参考，不删除历史证据。

用户未跟踪的 V2/部署说明/交接文件不删除或纳入本提交；V2 的历史地位在根 SPEC/README 明确登记。`.pi/` 讨论稿标已被专项规格取代，避免被当成另一份当前规范。

## 验证与限制

仅文档/场景规格变更，无业务源码、依赖安装、schema 结构、迁移或公开路由实现。本轮文档一致性/链接、契约与旧 QA 回归结果记录在 PROGRESS.md 和 M00/M05 进度。

旧成功测试不证明 FR-AGENT 已实现；新场景尚未接入执行器。本次不修复答案漏洞，它作为 ND-AGENT-01 的第一项 Red 回归。

## 后续顺序

ND-AGENT-01 → ND-AGENT-02 → ND-AGENT-03 → ND-AGENT-04 → ND-AGENT-05。云部署/live 检索旧票仍保留，但不再覆盖 Agent 关键路径。
