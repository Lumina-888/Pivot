# Wave 3 M11 Compose api 共享 PG/MinIO 切片限制

环境：Compose `api` 与 `worker` 注入同一套 `PIVOT_STORAGE` / `PIVOT_DATABASE_URL` / `PIVOT_OBJECT_STORE` / MinIO 变量；CI 不 `docker build` / `docker compose up`。HTTP/worker 共享对象字节用 sqlite 测试 URL 与 Fake MinIO client。

- Compose yml 不写死 `postgresql://` 或 `minio:9000`；不静默 `:-memory`。
- HTTP 缺省仍为进程内 ingest；本切片不把 api 必选接到 Qdrant。
- fixture 占位不是冻结的 TBD-P0；无固定生产发布；无回滚演练。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-008 | unverified | Compose api 共享存储为 opt-in fixture 注入，不是固定版本发布、健康门禁和回滚演练；CI 不启动 Postgres/MinIO |

`implemented`（Compose api 共享存储注入）≠ `verified`。
