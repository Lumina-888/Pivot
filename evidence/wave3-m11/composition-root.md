# Wave 3 M11 composition root 限制

环境：FastAPI TestClient 调用 `assemble_runtime_app`；不启动 Compose/uvicorn；默认存储为进程内 memory 适配；`PIVOT_STORAGE=postgres` 可装配用户目录。

- composition root 可在不由测试逐个注入领域服务的情况下挂载 `/api/v1` 并提供 `/healthz`。
- 默认 `create_app()` 仍不挂 `/api/v1`。
- `/readyz` 在未注入 postgres/minio/qdrant/redis 探测时失败闭环。
- 密码哈希为 Argon2id；TTL/检索 k 为注入值，不是冻结的 TBD-P0。
- PG 仅用户目录；文档与导出对象可接 MinIO 适配（CI 用内存 client；公开导出 URL 仍为 signer）；向量可接 Qdrant 适配（CI 用内存 client）；dense 检索可消费该端口（Fake query embedder）；缓存/队列可接 Redis 适配（CI 用内存 client）；BM25 仍 Fake；登录限流仍为内存 Attempts；无 Celery；Dockerfile / Compose api 为后续 opt-in profile，不等于固定版本发布或回滚演练。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-008 | unverified | composition root 可启动进程内装配；不等于固定版本发布、健康门禁和回滚已通过 |

`implemented`（composition root）≠ `verified`。
