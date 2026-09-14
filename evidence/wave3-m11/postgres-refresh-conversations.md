# Wave 3 M01/M05 会话与 refresh 跨进程切片限制

环境：`SqlAlchemyRefreshTokenStore` + `SqlAlchemyConversationStore`；CI 用 sqlite 测试 URL 与 `PIVOT_DB_CREATE_SCHEMA=1`。不启动 Compose；不把 sqlite 标成生产 PostgreSQL。

- `PIVOT_STORAGE=postgres` 时 refresh 与会话与用户目录共用同一 session factory。
- refresh 只持久化 SHA-256 `token_hash`；明文不入库；不把 Redis 当会话事实源。
- 会话只持久化 SPEC §2.2 Conversation 字段；不新增 hidden/deleted_at 列；SQL 隐藏删除映射为删行。
- Run/EventLog/Claim/Citation 仍为内存；消息跨装配为空。
- access/refresh TTL 仍为 `TBD-P0`。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | sqlite 会话/refresh 适配不是真实 PG 一致性、多实例登录态与索引原子发布已通过 |
| GATE-P0-005 | unverified | 跨装配 refresh Cookie 夹具不是上线传输/HTTPS 拓扑验证 |

`implemented`（SQLAlchemy refresh/会话端口）≠ `verified`。
