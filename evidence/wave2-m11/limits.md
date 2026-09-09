# Wave 2 M11 限制与 GATE 状态

环境：本机/CI Python 3.12；不连接真实 PG/MinIO/Qdrant/Redis；不启动 FastAPI/Celery/Compose。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-001 | unverified | 无真实企业文档准入流程 |
| GATE-P0-002 | unverified | dense/BM25 为 Fake KeywordRetriever |
| GATE-P0-003 | unverified | 无真实存储与索引原子发布环境 |
| GATE-P0-004 | unverified | 仅 Fake 领域编排，无 HTTP/SSE |
| GATE-P0-005 | unverified | Next rewrite 可同源转发；无 Playwright/上线传输验证 |
| GATE-P0-006 | unverified | 备份恢复未在新 ECS 演练 |
| GATE-P0-007 | unverified | 5 并发 / 100k Chunk 未测；阈值仍 TBD-P0 |
| GATE-P0-008 | unverified | composition root 可启动；无固定版本发布与回滚演练 |

`implemented`（若有 Fake 链路测试）≠ `verified`。
