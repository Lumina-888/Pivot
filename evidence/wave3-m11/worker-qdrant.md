# Wave 3 M07 worker 装配 Qdrant IndexPublisher 切片限制

环境：`assemble_ingest_runtime` 在 `PIVOT_VECTOR_STORE=qdrant` 时装配 `IndexPublisher` + 注入维数的 `HashingQueryEmbedder`，写入与 API 检索相同的 VectorStore 端口。CI 用 sqlite 测试 URL、Fake MinIO client 与 Fake Qdrant client，不启动 Postgres/MinIO/Qdrant/Celery 容器。

- worker 缺 `PIVOT_QDRANT_ENDPOINT` / `PIVOT_QDRANT_COLLECTION` / `PIVOT_QDRANT_VECTOR_SIZE` 失败闭环；不写死维数/距离/供应商 URL。
- Compose worker 注入 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*`（`${}`）；example 占位不是冻结的 `TBD-P0`。
- 默认 Embedding 仍为注入 Fake（`HashingQueryEmbedder`）；`PIVOT_EMBEDDING=http` 见 `ingest-http-embedding.md`。不是 live 供应商。HTTP 缺省仍为进程内 ingest。
- 本切片不是 `GATE-P0-002` / `GATE-P0-003` 闭环。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-002 | unverified | Fake embedder + 内存 Qdrant client，不是 dense+BM25 真实供应商闭环 |
| GATE-P0-003 | unverified | Fake upsert 不是真实 Qdrant 原子发布与完整存储一致性环境 |

`implemented`（worker 可写入注入 VectorStore）≠ `verified`。
