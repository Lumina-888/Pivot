# Wave 3 M05 Run / EventLog 跨进程切片限制

环境：`SqlAlchemyRunStore`；CI 用 sqlite 测试 URL 与 `PIVOT_DB_CREATE_SCHEMA=1`。不启动 Compose；不把 sqlite 标成生产 PostgreSQL。

- `PIVOT_STORAGE=postgres` 时 Run / AgentEvent / Message 与用户目录、Conversation 共用同一 session factory。
- Run 只持久化 SPEC §2.2 字段；`fingerprint` 由 question/scope 重算；`owner_id` 从 Conversation 读取；`answer_markdown` 经 Message（assistant content）往返。
- AgentEvent.summary 保存公开 SSE 事件名与 payload 的轻量 JSON 摘要；不新增 payload 列；不含思考链/系统 Prompt。
- 不把 Redis 当 Run/EventLog 事实源。
- Claim/Citation 本切片不入库（Citation 依赖已发布 Chunk FK）。
- HTTP 仍为同步编排后 EventLog 补发，不是 uvicorn 长连接（ND-W3-08）。
- SSE 预算/超时仍为 `TBD-P0`。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | sqlite Run/EventLog 适配不是真实 PG 一致性、多实例问答与索引原子发布已通过 |
| GATE-P0-004 | unverified | 跨装配 SSE 补发夹具不是 Verifier 阈值/盲评/企业 Golden Set 已通过 |

`implemented`（SQLAlchemy Run/EventLog 端口）≠ `verified`。
