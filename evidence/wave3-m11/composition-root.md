# Wave 3 M11 composition root 限制

环境：FastAPI TestClient 调用 `assemble_runtime_app`；不启动 Compose/uvicorn；默认存储为进程内 memory 适配；`PIVOT_STORAGE=postgres` 可装配用户目录。

- composition root 可在不由测试逐个注入领域服务的情况下挂载 `/api/v1` 并提供 `/healthz`。
- 默认 `create_app()` 仍不挂 `/api/v1`。
- `/readyz` 在未注入 postgres/minio/qdrant/redis 探测时失败闭环。
- 密码哈希为 Argon2id；TTL/检索 k 为注入值，不是冻结的 TBD-P0。
- PG 仅用户目录；文档对象可接 MinIO 适配（CI 用内存 client）；无 Qdrant/Redis 客户端，无 Dockerfile / Compose api 服务，无固定版本发布或回滚演练。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-008 | unverified | composition root 可启动进程内装配；不等于固定版本发布、健康门禁和回滚已通过 |

`implemented`（composition root）≠ `verified`。
