# spec/contracts/ — 机器可读契约（contract-v0.1）

**当前状态：Wave 0 冻结草案（契约版本 `contract-v0.1`，manifest 0.1.0）。**
契约以根目录 [`SPEC.md`](../../SPEC.md)（SPEC-1.0，规范源）生成；变更记录见 [`CHANGELOG.md`](CHANGELOG.md)。

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
