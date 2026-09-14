# 真实解析库 extra（ND-W3-03）

环境：`PIVOT_PARSER=native` 时 `assemble_runtime` 与 `assemble_ingest_runtime` 装配 `worker[parse]` 的 PyMuPDF / python-docx / python-pptx / openpyxl 注册表。CI 用库生成的微型 PDF/OOXML 夹具，无企业文档。不启动 Compose/uvicorn。

- 默认 `PIVOT_PARSER=local` 仍为启发式 PDF + stdlib OOXML。
- 未装 `worker[parse]` 时选 `native` 失败闭环，不静默回退启发式。
- 扫描件仍本地 `UNSUPPORTED_SCAN_PDF`（OCR 属 P2；MinerU 云路径不变）。
- 页数/大小/Sheet/解压比仍为 `TBD-P0`，本切片不冻结。
- Dockerfile / CI 安装 `worker[celery,parse]`；Compose example 仍占位 `local`。
- **GATE-P0-003 unverified**。本切片不得标 verified。
