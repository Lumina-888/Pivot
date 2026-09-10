# Wave 3 M04 HTTP Embedding / bge-reranker 限制

环境：`PIVOT_EMBEDDING=http` 时 query embedder 为注入 endpoint/model/key 的 `HttpQueryEmbedder`；`PIVOT_RERANK=bge` 时 rerank 为 `HttpBgeReranker`。CI 用 `ScriptedJsonHttpClient`，无真实供应商、无密钥入库。不启动 Compose/uvicorn。M07 ingest 仍 Fake Embedding。

- 默认 `PIVOT_EMBEDDING=hash` 仍为 `HashingQueryEmbedder`。
- HTTP 适配器不写死供应商 URL、模型名、维数、超时或 rerank 阈值；这些仍为 `TBD-P0`。
- Fake HTTP 闭环 ≠ 生产 Embedding/rerank 冒烟。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-002 | unverified | HTTP 适配器 + Fake transport，不是 live bge-m3 / bge-reranker 供应商闭环；Golden Set 仍 Fake Keyword；未达 100~150 |

`implemented`（可注入 HTTP 适配器）≠ `verified`。
