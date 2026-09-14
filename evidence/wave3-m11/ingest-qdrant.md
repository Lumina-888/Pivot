# Wave 3 M07 ingest→Qdrant 限制

环境：`PIVOT_VECTOR_STORE=qdrant` 时 `IndexPublisher` 在 `publish` 前对注入的 `QdrantVectorStore` 做 `upsert`；ingest embedding 复用 query embedder。CI 用内存 client 子集。不启动 Compose/uvicorn/Celery。

- payload 含 `version_id + chunk_id` 以及检索水合字段（`document_id`/`text`/`ready`/`current`/`allowed`/`index_generation`）。
- 缺 `document_id` 或 upsert 失败则代次不 `published`，不回调 `IngestSink.on_publish`。
- 默认 Embedding 仍为注入 Fake（`HashingQueryEmbedder`）；`PIVOT_EMBEDDING=http` 见 `ingest-http-embedding.md`。不是 live 供应商。
- HTTP 上传路径不自动跑 Worker；无 Compose worker。
- 维数/距离仍为测试夹具注入，不冻结 TBD-P0。
- 本切片不是 `GATE-P0-002` / `GATE-P0-003` 闭环。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-002 | unverified | Fake embedder + 内存 Qdrant client，不是 dense+BM25 真实供应商闭环 |
| GATE-P0-003 | unverified | Fake upsert 不是真实 Qdrant 原子发布与完整存储一致性环境 |

`implemented`（ingest 写入注入 VectorStore）≠ `verified`。
