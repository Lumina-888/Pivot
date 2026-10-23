# 机器可读契约

当前发布基线是 contract-v0.2，OpenAPI 版本是 0.2.0。contract-v0.1 的信封保持兼容。

契约最初从 SPEC-1.0 生成。当前目标规范是 [SPEC-1.1](../../SPEC.md) 和 [AGENT_SPEC](../AGENT_SPEC.md)。变更记录见 [CHANGELOG.md](CHANGELOG.md)。

v0.2 增加了 `POST /runs/{id}/resume`、澄清字段和恢复错误码。协议非法和预算耗尽的其余错误映射，尚未全部冻结。恢复路由已经发布。这不代表跨进程恢复已经验收。旧主图阶段名称只作兼容公开投影，不代表固定执行顺序。

## 已发布范围

2026-10-12，02-A、02-B 和 02-C 的内部契约发布到 [progress/contracts/](../../progress/contracts/README.md)。版本是 AGENT-INTERNAL、BUDGET 和 DEPENDENCIES 的 0.1.0。

这三份契约不加入本目录的公开 manifest，也不生成公开客户端。期限、正式角色锁、遥测、许可证、原生组件和运行许可仍然 pending。它们不关闭 DR-010，也不关闭任何 GATE。

03-A 已发布为 contract-v0.2。机器文件是本目录的 `openapi.yaml`，说明见 [CHANGELOG.md](CHANGELOG.md)。`proposals/` 里的恢复草案只保留提案历史。形状检查不能证明运行时的 owner、幂等、取消和跨进程恢复。

04-A 已发布为 [AGENT-PERSISTENCE 0.1.0](../../progress/contracts/AGENT-PERSISTENCE-0.1.0.md)。它不是 contract-v0.1 或 v0.2 的公开 HTTP 契约。04-B 至 04-F 已完成（PR #5 至 #9），真实 PostgreSQL 恢复已经故障矩阵覆盖。GATE-P0 仍为 unverified。证据见 [nd-agent-04-a.md](../../evidence/agent-m03/nd-agent-04-a.md)。

被取代的提案正文保留在 `progress/changes/`。那些正文不再表示 02-A、02-B、02-C、03-A 或 04-A 仍待签认。

## 文件与来源

| 文件 | 来源 | 覆盖内容 |
|---|---|---|
| `openapi.yaml` | SPEC 第 5.1 至 5.5 节、第 2.2 节、附录 B 和附录 C | HTTP 规则、错误包、路由、Scope、不透明 ID 和 UTC 时间 |
| `sse.schema.json` | SPEC 第 3.3 节、第 5.6 节、附录 B.2 | SSE 信封、事件类型、终态和 Last-Event-ID 补发 |
| `worker.schema.json` | SPEC 第 5.7 节、附录 B.1 | Worker 的 ok、insufficient 和 failed 三分支 |

## 消费入口

**HTTP API。** 以 `openapi.yaml` 生成客户端和路由表。前缀是 `/api/v1`。除登录和刷新外，请求使用 `bearerAuth`。refresh token 只经 HttpOnly、Secure 和 SameSite Cookie，依据是 FR-AUTH-001。

**SSE。** `/runs/{id}/events` 返回 `text/event-stream`。每条 `data:` 的 JSON 必须通过 `sse.schema.json`。事件名写在 SSE 的 `event:` 行，不写进 JSON。断线重连使用 `Last-Event-ID`，它等于已收最大 `seq`。规则见 SPEC 第 3.3 节。

**Worker。** 解析节点和问答节点的输出必须通过 `worker.schema.json`。失败必须给出非空 `error_code`。枚举见 SPEC 附录 B.1。

**契约测试。** `tests/contract/` 由 M00 维护。变更说明见 `progress/changes/20260906-M00-contract-test-path.md`。测试校验上述文件和 SPEC 是否一致。

## 版本与变更

- 版本规则见 SPEC 第 0.6 节和 MODULE_SPEC 第 10 节。兼容字段增加时提升 minor。破坏性变更提升 major，并提供兼容窗口或 API 版本升级。
- 状态机、权限、引用、删除语义、模型或检索配置发生变化时，先登记 ADR。依据是 SPEC 附录 E。
- 已发布的需求 ID、状态枚举、公开 API 字段和事件名不得复用。依据是 SPEC 第 0.6 节。
- 跨模块字段、调用方向或错误语义发生变化时，先提交 `progress/changes/YYYYMMDD-Mxx-*.md`。获批前，消费者继续使用旧契约。
- `TBD-P0` 只以 `x-tbd-p0` 注解出现。契约中不得静默填写默认值。冻结后更新本目录、`SPEC.md` 和测试夹具。
