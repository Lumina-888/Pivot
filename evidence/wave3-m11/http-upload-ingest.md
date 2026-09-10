# Wave 3 HTTP 上传自动 ingest 限制

环境：`assemble_runtime` 把 `DocumentIngestRunner` 注入文档 HTTP；`POST /api/v1/documents` 信封仍为 `uploaded`，随后进程内跑既有 `IngestWorker`。无 Celery、无 Compose worker。不启动 uvicorn。

- 未注入 ingest 的 `create_app(auth, documents)` 行为不变。
- 已 `ready` 的重复 SHA 不重入 ingest。
- `PIVOT_VECTOR_STORE=qdrant` 时写入注入 VectorStore（CI 内存 client + Fake embedder）。
- API 镜像仍不包含独立 worker 进程；缺 `pivot_worker` 时 runner 为 None。
- 本切片不是 `GATE-P0-003` 闭环。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | 进程内 Fake ingest，不是 Celery 任务与真实 Qdrant 原子发布 |

`implemented`（HTTP 上传后进程内 ingest）≠ `verified`。
