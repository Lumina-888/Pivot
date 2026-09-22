# Wave 2/3 M11 限制与 GATE 状态

环境：本机/CI Python 3.12；不连接真实 PG/MinIO/Qdrant/Redis；CI 不启动 FastAPI/Celery/Compose。  
Wave 3 夹具收口见 `evidence/wave3-m11/wave3-closeout.md`。`wave-3-integrated` **不等于** P0 通过。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-001 | unverified | 无真实企业文档准入/外发审批；dev-staging 仅低敏规章制度，不把 staging 当合规通过 |
| GATE-P0-002 | unverified | dense 可消费 VectorStore；worker 可写入同一端口（CI Fake Qdrant + Hashing embedder）；可注入 HTTP Embedding/bge rerank（CI Fake transport，非 live 供应商）；stdlib BM25 可注入；Golden Set v0.2 为 120 条合成 Fake Keyword；v0.3-enterprise 为空 schema（awaiting_annotation），非企业标注完成；NFR-QUAL 仍 TBD-P0 |
| GATE-P0-003 | unverified | PG/MinIO（含导出字节）/Qdrant/Redis 已接线；导出任务、hashed refresh、Conversation 与 Run/EventLog 可走 SQLAlchemy（CI sqlite，非生产 PG）；Claim/Citation 仍不入库；HTTP 上传默认可进程内 ingest；`PIVOT_INGEST=celery` 为 eager + 注入 memory broker；Compose api 注入 celery ingest 变量（CI 不 up）；api/worker 注入同一套 Qdrant/Redis（CI 不 up）；worker 可装配共享 MinIO/PG 与 Qdrant IndexPublisher（CI sqlite + Fake MinIO/Qdrant）；可注入 MinerU 云解析器（CI Fake HTTP，非 live）；`PIVOT_PARSER=native` 可装配 PyMuPDF/docx/pptx/xlsx extra（CI 微型夹具，缺省仍启发式/stdlib）；无真实 Redis/Celery worker 与 Qdrant 原子发布环境 |
| GATE-P0-004 | unverified | Run/SSE HTTP 与 Fake 拒答已有；Run/EventLog 可走 SQLAlchemy（CI sqlite）；SSE 长连接为 TestClient/opt-in uvicorn 夹具（非生产评测）；可注入 HTTP Draft Writer（CI Fake transport，非 live DeepSeek/小米）；Verifier 阈值未冻；无盲评；无企业 Golden Set；只能内部实验 |
| GATE-P0-005 | unverified | opt-in Playwright 十页；CI 不启动 uvicorn；Compose 可注入登录限流阈值（fixture，非冻结 TBD-P0）；跨装配 refresh Cookie 为 sqlite 夹具，无上线传输验证 |
| GATE-P0-006 | unverified | 进程内事实 roundtrip 已有；无加密 OSS / 新 ECS 演练；RPO/RTO 仍 TBD-P0 |
| GATE-P0-007 | unverified | 5 路 Fake 检索 + opt-in 100k 夹具；CI 不跑 100k；staging 8GiB limits 为 fixture，非 ECS 峰值；P95 仍 TBD-P0 |
| GATE-P0-008 | unverified | Dockerfile/Compose api+web+worker 为 opt-in profile `app`（api 与 worker 注入共享 PG/MinIO/Qdrant/Redis；api 注入 celery ingest；worker 为注入 broker 的 Celery fixture，CI 不启动）；staging overlay/runbook 已入库但未 SSH、未改安全组、无固定版本发布与回滚演练 |

`implemented`（若有 Fake 链路测试）≠ `verified`。
