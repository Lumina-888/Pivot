# Wave 3 M03 PostgreSQL 文档事实源切片限制

环境：`SqlAlchemyDocumentStore` / `VersionStore` / `ChunkStore` / `TaskStore`；CI 用 sqlite 测试 URL 与 `PIVOT_DB_CREATE_SCHEMA=1`。不启动 Compose；不把 sqlite 标成生产 PostgreSQL。

- `PIVOT_STORAGE=postgres` 时文档四端口与用户目录共用同一 session factory。
- 内容幂等仍走 `content_sha256`；本切片不新增 DocumentVersion.idempotency_key 列。
- HTTP 上传信封仍 `uploaded`，随后进程内 ingest；非 Celery。
- 对象字节仍为 memory 或 MinIO；第二装配若不共享 ObjectStore 则不能预览。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | sqlite 文档事实适配不是真实 PG 一致性、幂等与索引原子发布已通过 |

`implemented`（SQLAlchemy 文档端口）≠ `verified`。
