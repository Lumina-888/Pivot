# Wave 3 M03 PostgreSQL 用户事实源客户端限制

环境：SQLAlchemy `UserDirectory` 用 SQLite 文件/内存覆盖默认 CI；Compose Postgres 为 opt-in（`PIVOT_REQUIRE_COMPOSE=1` 且安装 `api[postgres]`）。不启动 uvicorn；不把 sqlite 标成生产事实源。

- `PIVOT_STORAGE=postgres` 将用户读写接到 `SqlAlchemyUserDirectory`；URL 必须注入，禁止写死生产地址。
- 文档对象、检索、导出、会话、refresh token 仍为 memory。
- `must_change_password` 不是 SPEC §2.2 User 字段，本切片不入库。
- `/readyz` 在仅接通 postgres 探测时仍因 minio/qdrant/redis 失败闭环。
- 无真实 MinIO/Qdrant/Redis 客户端，无删除下线与索引原子发布。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | 用户目录客户端不等于状态一致性、幂等、删除与索引原子发布已通过 |

`implemented`（user directory）≠ `verified`。
