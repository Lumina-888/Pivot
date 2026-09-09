# Wave 3 M04 stdlib BM25 / 可注入 rerank 限制

环境：stdlib BM25 + `SimpleLexTokenizer`（CJK 单字，非 jieba）；rerank 为 `OverlapReranker` 或 `Bm25Reranker`。无 bge 模型、无供应商 URL。不启动 Compose/uvicorn。

- `Bm25Retriever` 的 k1/b 与 search k 均注入；未设 `PIVOT_BM25_K1`/`PIVOT_BM25_B` 时 runtime 仍为 Keyword。
- `PIVOT_RERANK=none|overlap|bm25`；`bm25` 不是 `bge-reranker-v2-m3`。
- 分词、RRF、rerank 阈值、top-50 仍为 `TBD-P0`。
- Golden Set 仍走 Fake KeywordRetriever。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-002 | unverified | stdlib BM25 + Fake embedder/rerank，不是 dense+BM25+bge 真实供应商闭环 |

`implemented`（stdlib BM25）≠ `verified`。
