# Wave 3 夹具收口评审（ND-W3-13）

> **日期**：2026-09-10  
> **Owner**：M11（M00 回填矩阵）  
> **工单**：ND-W3-13  
> **性质**：工程夹具收口。**不是** GATE-P0 通过证据。  
> tag `wave-3-integrated` **不等于** P0 通过，**不得**宣称 production-ready，**不得**冻结 `TBD-P0`。

环境：本机/CI Python 3.12.10；pytest 9.1.1；ruff 0.16.6；celery 5.5.3。不连接真实 PG/MinIO/Qdrant/Redis；CI 不 `docker build` / `docker compose up`；不启动 FastAPI/Celery 生产拓扑。

## 1. 退出条件核对

| 条件 | 结果 |
|---|---|
| A1 ND-W3-01 worker 装配 Qdrant IndexPublisher | 完成（CI Fake client） |
| A1 ND-W3-02 Compose api 注入 `PIVOT_INGEST=celery` | 完成（yml 不写死 broker；CI 不 up） |
| A1 ND-W3-12 Compose api/worker 注入 Qdrant/Redis | 完成（store 不静默 memory；Redis 不是业务事实源） |
| 分组回归绿 | 见 §4；CI 不 up Compose |
| 矩阵回填 `implemented`，不标 `verified` | `spec/acceptance/matrix.md` Wave 3 夹具基线 |
| 八项 GATE-P0 仍 unverified | 本文件 §3 与 `evidence/wave2-m11/limits.md` |

A2 中 ND-W3-06（登录限流接到 Redis）已完成，**不**阻塞本 tag，也**不**冻结失败次数。

## 2. 夹具范围（本 tag 包含）

Compose profile `app` 上可本机 opt-in 接线：

- 上传信封仍 `uploaded`；`PIVOT_INGEST=celery` 时入队 parse；worker 只听 parse；
- api 与 worker 共享 PG/MinIO/Qdrant/Redis 注入（不写死 URL）；
- worker 可从 MinIO 读对象、向 Qdrant 发布（CI Fake）；
- 登录失败计数可写 Redis CacheStore；Compose api 注入阈值/窗口（不写死次数）；
- HTTP / composition root / Next `/api/v1` rewrite / opt-in Playwright 登录；
- Golden Set v0.2-synthetic 120 条（合成 Fake Keyword，非企业标注）；
- 5 并发与进程内备份夹具；100k Chunk opt-in Fake retrieve。

进程外 `assemble_runtime` 缺省仍 memory 存储 + 进程内 ingest；未开 `app` profile 时依赖 fixture 不变。

## 3. GATE-P0（全部 unverified）

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-001 | unverified | 无真实企业文档准入/外发审批；dev-staging 仅低敏规章制度，不把 staging 当合规通过 |
| GATE-P0-002 | unverified | dense 可消费 VectorStore；worker 可写入同一端口（CI Fake Qdrant + Hashing embedder）；可注入 HTTP Embedding/bge rerank（CI Fake transport，非 live 供应商）；stdlib BM25 可注入；Golden Set v0.2 为 120 条合成 Fake Keyword，非企业标注；NFR-QUAL 仍 TBD-P0 |
| GATE-P0-003 | unverified | PG/MinIO（含导出字节）/Qdrant/Redis 已接线；HTTP 上传默认可进程内 ingest；`PIVOT_INGEST=celery` 为 eager + 注入 memory broker；Compose api 注入 celery ingest 变量（CI 不 up）；api/worker 注入同一套 Qdrant/Redis（CI 不 up）；worker 可装配共享 MinIO/PG 与 Qdrant IndexPublisher（CI sqlite + Fake MinIO/Qdrant）；无真实 Redis/Celery worker 与 Qdrant 原子发布环境 |
| GATE-P0-004 | unverified | Run/SSE HTTP 与 Fake 拒答已有；Verifier 阈值未冻；无盲评；无企业 Golden Set；只能内部实验 |
| GATE-P0-005 | unverified | opt-in Playwright 登录；CI 不启动 uvicorn；Compose 可注入登录限流阈值（fixture，非冻结 TBD-P0）；无上线传输/Cookie 验证 |
| GATE-P0-006 | unverified | 进程内事实 roundtrip 已有；无加密 OSS / 新 ECS 演练；RPO/RTO 仍 TBD-P0 |
| GATE-P0-007 | unverified | 5 路 Fake 检索 + opt-in 100k 夹具；CI 不跑 100k；非 ECS 峰值；P95 仍 TBD-P0 |
| GATE-P0-008 | unverified | Dockerfile/Compose api+web+worker 为 opt-in profile `app`（api 与 worker 注入共享 PG/MinIO/Qdrant/Redis；api 注入 celery ingest；worker 为注入 broker 的 Celery fixture，CI 不启动）；无固定版本发布与回滚演练 |

`implemented`（夹具/Fake/Compose 注入）≠ `verified`。`wave-3-integrated` 不等于 P0 通过。

## 4. 验证

- 命令：`python ops/run_grouped_tests.py --skip-web`
- 环境：Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3
- 结果：领域 167 + Wave 0/M03 87 + pipeline 202 + ops 2 + perf 11 = **469 passed, 12 skipped**；ruff / compileall 通过。
- 本文件不把命令输出解释为 GATE verified。

## 5. 不在本 tag 内（剩余）

- **A2**：ND-W3-04 导出任务 PostgreSQL；ND-W3-05 会话/refresh 跨进程；ND-W3-07 PATCH 角色 / 重置密码 HTTP；ND-W3-11 `version.idempotency_key` 入库（blocked）。
- **A3**：ND-W3-03 真实解析库；ND-W3-08 SSE 长连接；ND-W3-09 LangGraph extra（blocked）；ND-W3-10 Playwright 十页。
- **P0 / staging**：企业 Golden Set、live Embedding/rerank、Verifier 盲评、新 ECS 备份恢复、100k 索引峰值、固定发布回滚；ND-STG-01~04。

HTTP 缺省仍请求内同步 ingest。导出任务仍内存。PATCH `/admin/users/{id}` 只改 status。
