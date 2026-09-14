# Wave 3 M06 PostgreSQL 导出任务切片限制

环境：`SqlAlchemyExportRepository`；CI 用 sqlite 测试 URL 与 `PIVOT_DB_CREATE_SCHEMA=1`。不启动 Compose；不把 sqlite 标成生产 PostgreSQL。

- `PIVOT_STORAGE=postgres` 时导出任务与用户目录/文档事实共用同一 session factory。
- 只持久化 SPEC §2.2 ExportTask 字段；不新增 filename/error_code/run_id/content_type 列。
- 公开 `download_url` 仍为 `PublicDownloadSigner`；响应不含 `storage_key` / MinIO endpoint。
- 无对象字节下载 HTTP；导出 TTL 仍为 `TBD-P0`。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | sqlite 导出任务适配不是真实 PG 一致性、幂等与索引原子发布已通过 |

`implemented`（SQLAlchemy 导出任务端口）≠ `verified`。
