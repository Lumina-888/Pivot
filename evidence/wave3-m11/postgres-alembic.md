# Wave 3 M11 Postgres Alembic 冒烟限制

环境：仅当本地 Compose postgres 在 `127.0.0.1:5432` 可连，且安装了 `api[postgres]` extra 时执行。CI 默认不启动 Compose，也不安装该 extra 作为必选项。

- 冒烟只做 `alembic upgrade head`，检查 `users` / `document_versions` / `audit_events` 与 partial unique index `uq_document_versions_one_current`。
- 不执行删除下线、索引原子发布、真实 MinIO/Qdrant 写入。
- 不冻结保留期限、分页或 RPO/RTO。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | Alembic 冒烟不等于状态一致性、幂等、删除与索引原子发布已通过 |

`implemented`（opt-in smoke）≠ `verified`。
