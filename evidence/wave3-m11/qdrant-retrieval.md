# Wave 3 M04 检索接 Qdrant 限制

环境：`PIVOT_VECTOR_STORE=qdrant` 时 dense 路消费注入的 `QdrantVectorStore`；query embedder 为 `HashingQueryEmbedder`（注入维数）。CI 用内存 client 子集。不启动 Compose/uvicorn。

- dense `VectorStoreRetriever` 把查询向量化和 `limit=k` 交给向量端口；k 来自注入的 `PIVOT_RETRIEVAL_K` / `RetrievalPolicy`，不写死 50。
- 距离函数/维数仍为测试夹具注入，不冻结 TBD-P0。
- BM25 仍为 Fake `KeywordRetriever`（空 corpus）；无真实 Embedding 供应商、无 rerank、无 ingest→Qdrant 发布。
- payload 缺 `ready/current/allowed` 时不当成可召回；服务端过滤仍在 `RetrievalService`。
- Golden Set 仍走 Fake KeywordRetriever；本切片不是 `GATE-P0-002` 闭环。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-002 | unverified | Fake query embedder + 内存 Qdrant client，不是 dense+BM25 真实供应商闭环 |
| GATE-P0-003 | unverified | 检索消费向量端口不等于索引原子发布与完整存储一致性已通过 |

`implemented`（VectorStore dense retriever）≠ `verified`。
