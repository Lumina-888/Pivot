# spec/contracts/ — 机器可读契约（contract-v0.1）

**当前发布基线：contract-v0.1（manifest 0.1.0），兼容结构保持不变。**
该契约最初从 SPEC-1.0 生成；当前目标规范为 [`SPEC-1.1`](../../SPEC.md) 和 [AGENT_SPEC](../AGENT_SPEC.md)。变更记录见 [`CHANGELOG.md`](CHANGELOG.md)。

> 新 ReAct 能力、状态循环和答案发布门禁不是 v0.1 已实现事实。恢复 endpoint/字段、协议非法/预算的错误映射及新增 payload 在后续 M00 Contract 冻结；本次不增加路由/schema 字段，不伪称机器契约已覆盖澄清恢复。旧主图阶段名称仅作兼容公开投影，不代表固定执行顺序。

## 待审核内部提案

[AGENT-INTERNAL-0.1-draft.1](../../progress/changes/20261002-M05-agent-internal-contract.md) 定义拟议模型/工具/State/EvidenceRegistry Interface 与 Fake/Red 设计。状态 proposed，ND-AGENT-02-A review 待消费者/Owner 签认；不属于本目录已发布机器契约、不加入 manifest、不生成生产客户端。[AGENT-BUDGET-0.1-draft.1](../../progress/changes/20261002-M05-agent-budget-contract.md) 定义拟议累计预算/预扣结算、未知用量、期限/恢复、观察/上下文/并发规则、有限 Fixture 与 Red 设计。状态 proposed，ND-AGENT-02-B review 待签认，同样不属于已发布契约。02-A/B、DR-010 与 02-C 锁依赖尚未批准，不能据内嵌 schema 或 Fixture 算术检查解锁业务实现；默认下一刀 02-C 依赖验证/锁定申请。

## 契约文件与来源映射

| 文件 | 来源章节 | 覆盖内容 |
|---|---|---|
| `openapi.yaml` | SPEC §5.1~5.5、§2.2、附录 B/C | 通用 HTTP 规则、统一错误包与错误码枚举、认证/文档/搜索/会话/Run/导出/后台全部路由、Scope 语义、不透明 ID 与 ISO 8601 UTC |
| `sse.schema.json` | SPEC §3.3、§5.6、附录 B.2 | SSE data 负载信封（run_id/message_id/seq/timestamp/stage/payload）、事件类型与终态集合（x-* 扩展）、Last-Event-ID 补发语义 |
| `worker.schema.json` | SPEC §5.7、附录 B.1 | 内部 Worker 输出契约：ok / insufficient / failed 三分支必填差异、trace、error_code 与 confidence 约束 |

## 消费入口

- **HTTP API**：以 `openapi.yaml` 为唯一来源生成客户端与路由表；`/api/v1` 前缀 + `bearerAuth`（JWT access token，短时）；refresh token 仅经 HttpOnly/Secure/SameSite Cookie（FR-AUTH-001）。
- **SSE**：`/runs/{id}/events` 返回 `text/event-stream`；每条 `data:` 的 JSON 必须通过 `sse.schema.json`；事件名走 SSE `event:` 行（不在 JSON 内）；断线重连用 `Last-Event-ID`（= 已收最大 `seq`）补发，见 SPEC §3.3。
- **Worker**：解析/问答节点输出必须通过 `worker.schema.json`；失败必须给非空 `error_code`（SPEC 附录 B.1 枚举）。
- **契约测试**：`tests/contract/`（M00 所有权，见 `progress/changes/20260906-M00-contract-test-path.md`）校验上述文件与 SPEC 的一致性。

## 版本与变更纪律

- 语义化版本（SPEC §0.6、MODULE_SPEC §10）：兼容字段增加提升 minor；破坏性变更提升 major，并提供兼容窗口或 `/api/v1` 版本升级；
- 改变状态机、权限、引用/删除语义、模型或检索配置时，必须先行 ADR（SPEC 附录 E）；
- 需求 ID、状态枚举、公开 API 字段与事件名一经发布不得随意复用（SPEC §0.6）；
- 跨模块字段/调用方向/错误语义变更：先提交 `progress/changes/YYYYMMDD-Mxx-*.md` 变更申请，获批前消费者继续使用旧契约；
- `TBD-P0` 项（分页、initial_state、AdminMetrics、有效期、阈值等）仅以 `x-tbd-p0` 注解与说明出现，**禁止在契约中静默填默认值**；冻结后须更新本目录、`SPEC.md` 与测试夹具。
