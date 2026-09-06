# M03 数据库迁移

本目录是仓库唯一 canonical Alembic 迁移目录（MODULE_SPEC §3、SPEC §2）。

## 事实源与存储边界

- PostgreSQL 是业务事实源：用户、权限、文档/版本/Chunk、会话/Run、Claim/Citation、任务、审计和成本元数据均持久化在此。
- MinIO 保存原始文件、中间物（按策略）和导出物；数据库只保存 storage key/metadata，不保存内部 endpoint 或 secret。
- Qdrant 是可重建的检索副本；payload 必须包含 `version_id` 与 `chunk_id`，可依据 PostgreSQL + MinIO 重建。
- Redis 仅用于队列、短期缓存和限流计数；丢失不能导致业务事实不可恢复。

## 运行

```bash
alembic -c migrations/alembic.ini upgrade head
alembic -c migrations/alembic.ini downgrade base
```

`DATABASE_URL` 由运行环境注入；未设置时 `env.py` 使用 SQLite 内存库仅用于迁移结构烟测。生产环境必须显式配置 PostgreSQL URL，不得把 SQLite 当生产事实源。

## SQLite 与 PostgreSQL 差异

- `document_versions` 的单 current 约束通过 PostgreSQL partial unique index（`current = true`）实现；SQLite 迁移也声明等价的 `current = 1` partial index，实际生产语义仍以 PostgreSQL 验证为准。
- 数据库角色权限、审计表的数据库级不可更新/不可删除权限和生产触发器属于 PostgreSQL 部署加固项，SQLite 不能等价验证；应用层 `AuditEventRepository` 不暴露 update/delete。
- `DateTime(timezone=True)` 在 SQLite 中以无时区文本/值存储，测试边界由应用 UTC helper 保证；PostgreSQL 生产使用带时区语义。
- 本轮不冻结保留期限、分页、资源限制、RPO/RTO 或检索阈值等 `TBD-P0`。
