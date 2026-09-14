# Wave 3 / staging M07 ingest 与检索共用 HTTP Embedding 限制

环境：`PIVOT_EMBEDDING=http` 时 `assemble_runtime` 与 `assemble_ingest_runtime` 装配同一形状的注入 `HttpQueryEmbedder`（endpoint/model/api_key/timeout；维数来自 `PIVOT_QDRANT_VECTOR_SIZE`）。CI 用 `ScriptedJsonHttpClient`，无真实供应商、无密钥入库。不启动 Compose/uvicorn。

- 默认 `PIVOT_EMBEDDING=hash` 仍为 `HashingQueryEmbedder`。
- HTTP Embedding 失败不 `published`，错误码走既有 `PROVIDER_TEMPORARY_ERROR` / `RESOURCE_LIMIT`。
- Compose api/worker 注入同一套 `PIVOT_EMBEDDING*`；example 占位 `hash`，不是冻结的 `TBD-P0`。
- 适配器不写死供应商 URL、模型名、维数或超时；硅基 `BAAI/bge-m3` 仅 staging env 注入。
- Fake HTTP 闭环 ≠ 生产 Embedding 冒烟。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-002 | unverified | Fake HTTP transport + 内存 Qdrant client，不是 live bge-m3 / 企业 Golden Set 闭环 |

`implemented`（ingest 与检索可共用注入 HTTP Embedding）≠ `verified`。
