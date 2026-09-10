# Wave 3 M07 worker 共享 MinIO/PG ingest 切片限制

环境：`assemble_ingest_runtime` 为 worker 装配 `DocumentIngestRunner`（PostgreSQL 文档事实 + MinIO ObjectStore）。CI 用 sqlite 测试 URL 与注入的 Fake MinIO client，不启动 Postgres/MinIO/Celery 容器。

- worker 拒绝 `PIVOT_STORAGE=memory` 与 `PIVOT_OBJECT_STORE=memory`；跨进程不得把内存对象当事实。
- `python -m pivot_worker` 在 Celery 监听前装配 runner；Compose 注入存储变量，yml 不写死 URL。
- HTTP 缺省仍为进程内 ingest；本切片不把 worker 必选接到 Qdrant；无真实 MinIO 冒烟。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | sqlite + Fake MinIO client 覆盖跨装配读取对象字节，不是真实 PostgreSQL/MinIO/Celery worker 一致性环境 |

`implemented`（worker 共享存储装配）≠ `verified`。
