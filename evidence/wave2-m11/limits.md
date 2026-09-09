# Wave 2 M11 限制与 GATE 状态

环境：本机/CI Python 3.12；不连接真实 PG/MinIO/Qdrant/Redis；不启动 FastAPI/Celery/Compose。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-001 | unverified | 无真实企业文档准入流程 |
| GATE-P0-002 | unverified | dense 可消费 VectorStore（Fake embedder）；Golden Set 仍 Fake Keyword；未达 100~150；NFR-QUAL 仍 TBD-P0 |
| GATE-P0-003 | unverified | PG/MinIO（含导出字节）/Qdrant/Redis 已接线；无索引原子发布与完整存储一致性环境 |
| GATE-P0-004 | unverified | 仅 Fake 领域编排，无 HTTP/SSE |
| GATE-P0-005 | unverified | opt-in Playwright 登录；CI 不启动 uvicorn；无上线传输验证 |
| GATE-P0-006 | unverified | 进程内事实 roundtrip 已有；无加密 OSS / 新 ECS 演练；RPO/RTO 仍 TBD-P0 |
| GATE-P0-007 | unverified | 进程内 5 路 Fake 检索完成；无 100k Chunk 峰值；P95 仍 TBD-P0 |
| GATE-P0-008 | unverified | composition root 可启动；无固定版本发布与回滚演练 |

`implemented`（若有 Fake 链路测试）≠ `verified`。
