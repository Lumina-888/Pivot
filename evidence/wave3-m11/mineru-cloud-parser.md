# MinerU 云解析器（ND-STG-03）

环境：`PIVOT_PARSER=mineru` 时 `assemble_runtime` 与 `assemble_ingest_runtime` 装配注入 endpoint/token 的 `MinerUCloudParser`（timeout/poll/model 可选）。CI 用 `ScriptedMinerUHttpClient`，无真实供应商、无 token 入库。不启动 Compose/uvicorn。

- 默认 `PIVOT_PARSER=local` 仍为启发式 PDF + stdlib OOXML。
- 扫描件走云 OCR；加密/损坏仍本地拦截，不外发。
- Compose api/worker 注入同一套 `PIVOT_PARSER*`；example 占位 `local`，不是冻结的 `TBD-P0`。
- Fake HTTP 不是 live MinerU。SPEC 仍将 MinerU 标为 V2，不是 MVP 唯一解析器。
- **GATE-P0-003 unverified**。本切片不得标 verified。
