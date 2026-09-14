# 问枢 Pivot 开发进度

> **进度文档不是需求源**：需求以 [`SPEC.md`](SPEC.md) 为准，模块边界以 [`MODULE_SPEC.md`](MODULE_SPEC.md) 为准。  
> **最后更新**：2026-09-14  
> **当前状态**：主线开发（MODULE-SPEC-1.1）；Wave 3 夹具已收口；ingest/检索可共用注入 HTTP Embedding；可注入 HTTP Draft Writer 与 MinerU 云解析器；dev-staging Compose overlay 已入库（ECS apply 待 Owner SSH/安全组/磁盘）；hashed refresh、Conversation 与 Run/EventLog 可跨装配。工作区仅为 `Pivot/` 的 `main`。波次基线 `wave-3-integrated`（**不等于** P0 通过）。
> **当前基线**：`wave-3-integrated`：HTTP + composition root + Next `/api/v1` 反代 + opt-in Playwright 登录 + PG/MinIO/Qdrant/Redis 客户端 + Golden Set v0.2-synthetic（120 条） + 导出对象 MinIO + 导出任务 SQLAlchemy（CI sqlite） + hashed refresh / Conversation / Run/EventLog SQLAlchemy（CI sqlite） + 检索 dense 消费 Qdrant + ingest→Qdrant + HTTP 上传进程内 ingest + 5 并发/进程内备份夹具 + stdlib BM25/可注入 rerank + Dockerfile/Compose api+web+worker profile `app` + 100k Chunk opt-in 夹具 + HTTP Embedding/bge-reranker 适配器 + ingest/检索共用注入 HTTP Embedding + Redis 登录限流计数 + PG 文档事实 + Celery ingest eager + Compose Celery worker + worker 共享 MinIO/PG ingest runner + Compose api 共享 PG/MinIO + worker 装配 Qdrant IndexPublisher + Compose api 注入 `PIVOT_INGEST=celery` + Compose api/worker 注入 Qdrant/Redis + Compose api 注入登录限流阈值/窗口 + Compose api/worker 注入 `PIVOT_EMBEDDING*` + 可注入 HTTP Draft Writer（Compose 仅 api 注入 `PIVOT_LLM*`） + 可注入 MinerU 云解析器（Compose api/worker 注入 `PIVOT_PARSER*`） + dev-staging Compose overlay（nginx loopback :80，8GiB limits fixture）。GATE-P0 全部 unverified。

## 1. 新会话恢复入口

1. 确认 cwd 为 `E:/AI Project/Pivot`，分支为 `main`；不要进入 `../Pivot-Mxx-*`；
2. 读取 `AGENTS.md`；
3. 读取 `MODULE_SPEC.md`；
4. 读取本文件和本切片涉及的 `progress/modules/Mxx.md`；
5. 用 `git log --oneline --decorate -20` 确认实际基线。
6. 后续开发计划与工单：[`progress/next-dev-spec.md`](progress/next-dev-spec.md)、[`progress/tickets.md`](progress/tickets.md)（不是需求源）。Owner 近期目标 `dev-staging`：[`progress/changes/20260910-M00-dev-staging-scope.md`](progress/changes/20260910-M00-dev-staging-scope.md)。

如果没有指定切片：默认下一刀 **ND-W3-08 SSE**，或 ND-W3-03 真实解析库，或 Owner 提供 SSH/安全组/磁盘后实施 ND-STG-04 ECS apply，或人工标注企业 Golden Set。Wave 3 夹具已收口（`wave-3-integrated` **不等于** P0 通过）。不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / Fake embedder / stdlib BM25 / 进程内压测/恢复 / Dockerfile fixture / opt-in 100k Fake retrieve / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / sqlite 导出任务 / sqlite refresh/会话 / sqlite Run/EventLog / eager Celery / Compose Celery fixture / Fake MinIO worker ingest / Compose api 共享存储注入 / Fake worker Qdrant upsert / Compose api celery 注入 / Compose Qdrant·Redis 注入 / Compose 登录限流注入 / Wave 3 夹具收口 / ingest 共用 HTTP Embedding / Fake HTTP Writer / Fake MinerU 解析器 / staging Compose overlay 标成 GATE verified。不要新建 worktree。

## 2. 当前波次与模块状态

状态枚举：`planned` → `claimed` → `in_progress` → `blocked` → `review` → `integrated`。主线会话可更新本表。

| 模块 | 状态 | 代码位置 | 基线契约 | 最近证据 | 下一步 |
|---|---|---|---|---|---|
| M00 契约治理 | integrated | `main` | `contract-v0.1` | `tests/contract`: 48 passed | 已完成契约、场景、矩阵 |
| M01 身份授权 | integrated | `main`（tag `M01-v0.6.0`） | `contract-v0.1` | 37 单元/安全 + 登录/改密/管理用户 HTTP + PATCH 角色/重置 + Compose 注入 Redis 限流 + refresh 跨装配 | ND-W3-08 SSE 或 ND-W3-03 |
| M02 文档接入 | integrated | `main`（tag 目标 `M02-v0.6.0`） | `contract-v0.1` | 27 单元 + 上传/列表/详情/重试/删除/预览/下载 HTTP；runtime 上传后进程内 ingest；`PIVOT_INGEST=celery` 可入队；Compose api 注入 celery ingest；publish 写回 chunk | HTTP 缺省仍 sync ingest |
| M03 数据基础 | integrated | `main`（tag 目标 `M03-v0.8.0`） | `contract-v0.1` | M03 文档/导出/refresh/会话/Run SQLAlchemy + M00 48 tests passed | 用户目录、文档事实、导出任务、refresh、Conversation 与 Run/EventLog 可走 SQLAlchemy |
| M04 检索 RAG | integrated | `main`（tag 目标 `M04-v0.5.0`） | `contract-v0.1` | 31 单元 + 搜索 HTTP + Qdrant dense + stdlib BM25 + ingest/检索共用注入 HTTP Embedding/bge + 合成 Golden Set 120 条 | live 供应商冒烟与企业标注 Golden Set 待后续 |
| M05 QA/Run/SSE | integrated | `main`（tag 目标 `M05-v0.5.0`） | `contract-v0.1` | 28 领域 + Run/SSE + 会话 CRUD HTTP + Conversation/Run SQL store + 可注入 HTTP Draft Writer | Claim/Citation 仍不入库；LangGraph extra 待后续 |
| M06 导出/审计 | integrated | `main`（tag 目标 `M06-v0.3.0`） | `contract-v0.1` | 26 单元 + 导出/审计 HTTP + PG 任务跨装配 | 对象字节下载 HTTP 仍不新增（契约仅短时 URL） |
| M07 Worker/解析/索引 | integrated | `main`（tag `M07-v0.9.0`） | `contract-v0.1` | 62 单元 + ingest→Qdrant + HTTP 进程内 runner + parse 队列消费 + Celery eager ingest + Compose Celery worker + 共享 MinIO/PG runner + worker Qdrant IndexPublisher + ingest HTTP Embedding + MinerU 云解析器 | 真实解析库 extra 仍待 |
| M08 Web 基础 | integrated | `main`（tag `M08-v0.2.0`） | `contract-v0.1` | M08 15 tests + typecheck/lint 通过 | SSE 缓冲仍待；Compose web 由 M11 装配 |
| M09 员工前台 | integrated | `main`（tag `M09-v0.1.0`） | `wave-1-integrated` | 12 Fake + opt-in Playwright 登录 | 完整十页 Playwright 待后续 |
| M10 管理后台 | integrated | `main`（tag `M10-v0.1.0`） | `wave-1-integrated` | 8 passed | Playwright 后台流程待后续 |
| M11 集成/质量/运维 | in_progress | `main`（tag `M11-v0.23.0` / `wave-3-integrated`） | `wave-3-integrated` | 分组回归见本切片日志 | GATE-P0 仍全部 unverified；A2 Run/EventLog 可走 SQLAlchemy；staging overlay 已入库，ECS apply 待 Owner |

模块详细状态由各自 `progress/modules/Mxx.md` 维护。历史 `../Pivot-Mxx-*` worktree 不再使用。

## 3. 需求追踪摘要

完整映射和 Accountable/Contributors 见 [`MODULE_SPEC.md §8`](MODULE_SPEC.md#8-需求-accountable-映射)。验收链必须遵循：需求 ID → 场景 ID → 契约/数据 → 测试 ID → 验收证据 → verified。

| 需求范围 | Accountable | 测试/场景入口 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| FR-AUTH-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/`、`tests/integration/pipeline/test_FR_AUTH_001_http_login.py`、`tests/integration/pipeline/test_FR_AUTH_004_http_admin_users.py`、`tests/integration/pipeline/test_FR_AUTH_002_http_login_rate.py`、`tests/integration/pipeline/test_FR_AUTH_001_http_postgres_sessions.py` | implemented | 37 项单元/安全 + 登录/刷新/退出/改密/管理用户 HTTP；PATCH 角色/重置；限流计数可注入 Redis CacheStore；Compose api 注入阈值/窗口（不写死次数；进程外缺省不锁定）；`PIVOT_STORAGE=postgres` 时 hashed refresh 跨装配存活（CI sqlite） |
| FR-RBAC-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/`、`spec/scenarios/auth.feature`、`tests/integration/pipeline/test_FR_RBAC_002_http_conversations.py`、`tests/integration/pipeline/test_FR_RBAC_003_http_preview.py`、`tests/integration/pipeline/test_FR_AUTH_001_http_postgres_sessions.py` | implemented | 资源四重授权与会话隔离；会话 CRUD HTTP 仅 owner 可见；`PIVOT_STORAGE=postgres` 时 Conversation 跨装配存活（CI sqlite）；预览/下载按详情同等可见性 |
| FR-DOC-001~008 | M02 | `tests/unit/documents/`、`tests/integration/pipeline/test_FR_DOC_001_http_upload.py`、`tests/integration/pipeline/test_FR_DOC_007_http_lifecycle.py`、`tests/integration/pipeline/test_FR_RBAC_003_http_preview.py`、`tests/unit/worker/test_FR_DOC_006_qdrant_index.py`、`tests/integration/pipeline/test_FR_DOC_006_ingest_qdrant.py`、`tests/integration/pipeline/test_FR_DOC_001_http_postgres_facts.py`、`tests/integration/pipeline/test_FR_DOC_005_celery_postgres.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_minio_ingest.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_qdrant_publish.py` | implemented | 28 项 M02 单元 + 文档上传/列表/详情/版本/重试/删除/预览/下载 HTTP；runtime 上传后进程内 ingest（信封仍 uploaded）；`PIVOT_INGEST=celery` 时可 eager 入队；Compose api 注入 celery ingest（yml 不写死 broker，CI 不 up）；`PIVOT_STORAGE=postgres` 时文档事实可跨装配存活（sqlite 测试 URL）；worker 可从共享 MinIO 读取对象字节（CI Fake client）；worker 可向注入 Qdrant 发布（CI Fake client） |
| FR-SEARCH-001~002 / FR-RAG-001~006 | M04 | `tests/unit/retrieval/`、`tests/security/retrieval/`、`tests/integration/pipeline/test_FR_SEARCH_001_http_search.py`、`tests/integration/pipeline/test_FR_SEARCH_001_qdrant_retrieval.py`、`tests/integration/pipeline/test_FR_RAG_001_bm25_runtime.py`、`tests/integration/pipeline/test_FR_RAG_001_http_embedding_bge.py`、`tests/integration/pipeline/test_FR_DOC_006_ingest_http_embedding.py`、`tests/integration/pipeline/test_NFR_QUAL_golden_set.py` | implemented | 31 项 M04 单元 + 搜索 HTTP + Qdrant dense + ingest 可写入同一端口 + stdlib BM25 + ingest/检索共用注入 HTTP Embedding/bge（CI Fake transport）+ 合成 Golden Set 120 条 |
| FR-QA-001~006 / FR-STREAM-001~005 | M05 | `tests/unit/qa/`、`tests/unit/runs/`、`tests/contract/stream/`、`tests/integration/pipeline/test_FR_STREAM_001_http_runs.py`、`tests/integration/pipeline/test_FR_STREAM_001_http_postgres_runs.py`、`tests/integration/pipeline/test_FR_RBAC_002_http_conversations.py`、`tests/integration/pipeline/test_FR_QA_001_http_writer.py` | implemented | 28 项 M05 领域 + Run/SSE + 会话 CRUD HTTP（消息由 Run 合成）；Conversation 与 Run/EventLog 可走 SQLAlchemy（CI sqlite）；Claim/Citation 仍不入库；`PIVOT_LLM=http` 可注入 Writer（CI Fake transport） |
| FR-EXPORT-001~003 / FR-AUDIT-001~003 | M06 | `tests/unit/exports/`、`tests/unit/audit/`、`tests/security/export/`、`tests/integration/pipeline/test_FR_EXPORT_001_http_exports.py`、`tests/integration/pipeline/test_FR_EXPORT_001_http_postgres_tasks.py` | implemented | 26 项 M06 单元 + 导出/审计 HTTP；运行时导出字节可接 MinIO，公开 URL 仍为 signer；`PIVOT_STORAGE=postgres` 时任务可跨装配存活（sqlite 测试 URL） |
| §2 存储不变量 | M03 | `tests/integration/db/`、`api/src/pivot/db/`、`migrations/` | implemented | M03 数据测试 + 48 项 M00 契约回归通过；用户目录、文档事实、导出任务、hashed refresh、Conversation 与 Run/EventLog 默认 SQLite 覆盖；MinIO/Qdrant/Redis 默认内存 client；Compose 为 opt-in skip |
| §6 解析/分块/索引执行 | M07 | `tests/unit/worker/`、`tests/integration/pipeline/test_FR_DOC_006_ingest_qdrant.py`、`tests/integration/pipeline/test_FR_DOC_001_http_runtime_ingest.py`、`tests/integration/pipeline/test_NFR_OBS_compose_worker.py`、`tests/integration/pipeline/test_NFR_OBS_compose_api.py`、`tests/integration/pipeline/test_FR_DOC_005_celery_postgres.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_minio_ingest.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_qdrant_publish.py`、`tests/integration/pipeline/test_FR_DOC_006_ingest_http_embedding.py` | implemented | 62 项 M07 测试通过；stdlib/Fake 或注入 HTTP Embedding；可注入 MinerU 云解析器（CI Fake HTTP）；IndexPublisher 可写入注入 VectorStore；HTTP 上传默认可进程内 ingest；`PIVOT_INGEST=celery` 为 eager 任务（可见 PG version/task）；Compose api 注入 celery ingest（Dockerfile 装 worker[celery]）；Compose worker 为注入 broker 的 Celery，只监听 parse 队列；worker 装配共享 MinIO/PG runner（CI sqlite + Fake MinIO）；`PIVOT_VECTOR_STORE=qdrant` 时 worker 装配 IndexPublisher（CI Fake client）；`PIVOT_EMBEDDING=http` 时 ingest 与检索共用注入 embedder（CI Fake HTTP）；`PIVOT_PARSER=mineru` 时装配云解析器（Compose api/worker 注入 `PIVOT_PARSER*`） |
| §1.5 / NFR-UX 设计系统与 client | M08 | `tests/e2e/fixtures/web/test-foundation.mjs` | implemented | M08 15 项基础测试通过（含 `/api/v1` rewrite）；产品页由 M09/M10 接管 |
| 前台 6 页 | M09 | `tests/e2e/user/test_user_web.mjs` | implemented | 12 项 Fake fetch + opt-in Playwright 登录；CI 默认 skip |
| 后台 4 页 | M10 | `tests/e2e/admin/test_admin_web.mjs` | implemented | 8 项 Fake fetch 测试通过；无 Playwright |
| NFR-CAP/PERF/OBS/DR、GATE-P0-001~008 | M11 | `tests/integration/pipeline/`、`tests/security/ops/`、`tests/performance/`、`evidence/wave2-m11/`、`evidence/wave3-m11/` | implemented（CI/Fake + HTTP + composition root + Next rewrite + opt-in Playwright + PG/MinIO/Qdrant/Redis + 合成 Golden Set + 导出 MinIO + 检索 dense 消费 Qdrant + ingest→Qdrant + 5 并发/进程内备份 + stdlib BM25 + Dockerfile/Compose api+web+worker + 100k opt-in + HTTP Embedding/bge Fake transport + ingest/检索共用 HTTP Embedding + Celery eager ingest + Compose Celery worker + worker 共享 MinIO/PG ingest + Compose api 共享 PG/MinIO + worker Qdrant IndexPublisher + Compose api celery ingest + Compose api/worker Qdrant/Redis + Compose api 登录限流注入 + Compose api/worker Embedding 注入 + 可注入 HTTP Draft Writer + 可注入 MinerU 云解析器）；GATE-P0 unverified | TestClient；CI 不 build/up Compose、不跑 100k、不打真实供应商；Playwright/Compose/100k 默认 skip |

## 4. 当前波次计划

### Wave 0 — 基线冻结（已完成）

- [x] M00：从 SPEC §5、附录 B/C 建立并集成 `contract-v0.1` 草案（48 项契约测试通过）；
- [x] M03：建立数据对象、Repository/UoW 和 PG/MinIO/Qdrant/Redis adapter 接口草案；12 项 M03 测试与 48 项 M00 回归通过；
- [x] M08：建立 Next.js/TypeScript 工程、S3 设计系统和 API/SSE client 边界（9 项基础测试通过）；
- [x] Wave 0 退出评审：契约、数据接口、Web client 输入已冻结；三项所有权变更申请已批准；标签 `wave-0-integrated`。

### Wave 1 — 核心能力（已完成）

- [x] M01：认证会话、RBAC、资源四重授权（27 项测试，`M01-v0.1.0`）；
- [x] M02：文档签名、状态机、幂等与 tombstone（15 项测试，`M02-v0.1.0`）；
- [x] M07：可插拔解析/分块/Fake Embedding/索引代次（7 项测试，`M07-v0.1.0`）；
- [x] M04：服务端过滤、scope、RRF 降级（10 项测试，`M04-v0.1.0`）；
- [x] M05：问答主图、Run 幂等、SSE 事件日志（12 项测试，`M05-v0.1.0`）；
- [x] M06：导出授权/内容边界/过期与脱敏审计（26 项测试，`M06-v0.1.0`）；
- [x] Wave 1 退出评审：模块 tag 齐全；矩阵回填为单元层 `implemented`；M11 可装配单元/契约 fixture；标签 `wave-1-integrated`。

### Wave 2 — 页面与联调（已完成）

- [x] M09：员工前台六页、搜索带原问题、文档 scope、证据抽屉、拒答与导出入口（12 项测试，`M09-v0.1.0`）；
- [x] M10：管理后台四页、403、重试/删除、停用用户、审计脱敏（8 项测试，`M10-v0.1.0`）；
- [x] M11：分组 CI、进程内 Fake 认证→导出链路、Compose 意图与 Runbook 草稿（`M11-v0.1.0`）；
- [x] Wave 2 退出评审：三模块非快进合入；装配页测试适配；页面 Fake E2E 接入分组 CI；标签 `wave-2-integrated`。

### Wave 3 — P0/P1 门禁（夹具已收口；GATE 仍 unverified）

- [x] 依赖 Compose fixture：postgres / minio / qdrant / redis（钉镜像 + healthcheck + localhost；`M11-v0.2.0`）
- [x] Compose Postgres 的 opt-in Alembic 冒烟（默认 skip；`M11-v0.2.1`）
- [x] 应用 `/healthz` `/readyz`（TestClient 薄装配，`M11-v0.2.2`）
- [x] `/api/v1/auth/login|refresh|logout`（`M01-v0.2.0`）
- [x] `GET/POST /api/v1/documents`（`M02-v0.2.0`）
- [x] 文档详情/版本/重试/删除 HTTP（`M02-v0.3.0`）
- [x] `GET /api/v1/search`（`M04-v0.2.0`）
- [x] Run/SSE HTTP（`M05-v0.2.0`；EventLog 补发）
- [x] 导出/审计 HTTP（`M06-v0.2.0`；短时 URL，非对象字节下载）
- [x] 改密与管理员用户 HTTP（`M01-v0.3.0`；PATCH 仅 status）
- [x] PATCH 角色 / 重置密码 HTTP（ND-W3-07；`role` / `reset_password`）
- [x] 会话 CRUD HTTP（`M05-v0.3.0`；删除为隐藏，消息由 Run 合成）
- [x] 预览/下载 HTTP（`GET /documents/{id}/preview|download`；内存 Fake 对象字节）
- [x] composition root（`assemble_runtime_app`、Argon2id、memory 端口、`uvicorn pivot.http.main:app --factory`）
- [x] Next 反代 `/api/v1`（`PIVOT_API_ORIGIN` 注入 rewrite；浏览器仍同源）
- [x] opt-in Playwright 浏览器登录（`PIVOT_REQUIRE_PLAYWRIGHT=1`；CI 默认 skip）
- [x] PostgreSQL 用户事实源客户端（`SqlAlchemyUserDirectory`；`PIVOT_STORAGE=postgres`；URL 注入）
- [x] MinIO 文档对象客户端（`MinioObjectStore`；`PIVOT_OBJECT_STORE=minio`；endpoint/bucket 注入）
- [x] 导出对象接到 MinIO（`ExportObjectAdapter`；公开 URL 仍 `PublicDownloadSigner`）
- [x] Qdrant 向量客户端（`QdrantVectorStore`；`PIVOT_VECTOR_STORE=qdrant`；endpoint/collection 注入）
- [x] Redis 缓存/队列客户端（`RedisCacheStore`/`RedisQueueStore`；`PIVOT_CACHE_STORE`/`PIVOT_QUEUE_STORE=redis`；endpoint 注入）
- [x] Golden Set v0.1-synthetic 检索夹具（10 条分层，Fake KeywordRetriever）
- [x] Golden Set v0.2-synthetic 检索夹具（120 条分层，Fake KeywordRetriever；非企业标注）
- [x] 检索 dense 路消费 Qdrant VectorStore（Fake query embedder；不冻结 k/距离）
- [x] 5 并发检索夹具与进程内事实备份/恢复（非 100k、非新 ECS）
- [x] stdlib BM25（注入 k1/b/分词）与可选 overlap/bm25 rerank（非 jieba/bge）
- [x] Dockerfile + Compose api（profile `app`；CI 不 build/up）
- [x] 100k Chunk opt-in 夹具（`PIVOT_REQUIRE_100K=1`；CI 默认 skip）
- [x] HTTP Embedding / bge-reranker 可注入适配器（CI Fake transport；非 live 供应商）
- [x] Dockerfile.web + Compose web（profile `app`；CI 不 build/up）
- [x] ingest `IndexPublisher` 写入注入 VectorStore（CI Fake client）
- [x] HTTP 上传后进程内自动 ingest（信封仍 `uploaded`；非 Celery）
- [x] Dockerfile.worker + Compose worker（profile `app`；CI 不 build/up）
- [x] 登录失败限流计数可注入 Redis CacheStore（缺省不锁定；不冻结 TBD-P0）
- [x] `PIVOT_STORAGE=postgres` 装配文档事实（Document/Version/Chunk/Task；sqlite 测试 URL）
- [x] `PIVOT_INGEST=celery` eager 任务可看见 PG version/task（CI memory broker）
- [x] Compose worker 为注入 Redis broker 的 Celery（只监听 parse；CI 不 build/up）
- [x] worker 装配共享 MinIO/PG ingest runner（CI sqlite + Fake MinIO；拒绝 memory 对象）
- [x] Compose api 注入共享 PG/MinIO（与 worker 同一套变量；不静默 memory）
- [x] worker 装配 Qdrant IndexPublisher（CI Fake client；Compose 注入 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*`）
- [x] Compose api 注入 `PIVOT_INGEST=celery`（队列/concurrency/broker `${:?}`；Dockerfile 装 worker[celery]；CI 不 build/up）
- [x] Compose api/worker 注入 Qdrant/Redis（`${}`，store 不静默 memory；example 占位 qdrant/redis；CI 不 build/up）
- [x] Compose api 注入登录限流阈值/窗口（`${:?}`，不写死次数；example fixture 占位；进程外缺省仍永不锁定；CI 不 build/up）
- [x] Wave 3 夹具收口评审（ND-W3-13；A1 完成 + 回归绿；tag `wave-3-integrated` ≠ P0 通过）
- [x] 导出任务 PostgreSQL 持久化（ND-W3-04；CI sqlite；公开 URL 仍 signer；无对象字节下载 HTTP）
- [x] PATCH 角色 / 重置密码 HTTP（ND-W3-07；`role` / `reset_password`；重置口令不进审计）
- [x] ingest 与检索共用注入 HTTP Embedding（ND-STG-01；CI Fake transport；Compose api/worker 注入 `PIVOT_EMBEDDING*`）
- [x] Deepseek-Flash Draft Writer（ND-STG-02；CI Fake transport；Compose 仅 api 注入 `PIVOT_LLM*`；缺省仍证据拼接）
- [x] MinerU 云解析器（ND-STG-03；CI Fake transport；Compose api/worker 注入 `PIVOT_PARSER*`；缺省仍启发式/stdlib）
- [x] dev-staging Compose overlay（ND-STG-04；nginx 默认 127.0.0.1:80；8GiB limits fixture；CI 不 up；ECS apply 待 Owner SSH/安全组/磁盘）
- [x] 会话/refresh 跨进程（ND-W3-05；hashed refresh 与 Conversation 走 SQLAlchemy；CI sqlite）
- [x] Run/EventLog 跨进程（ND-W3-14；CI sqlite；Claim/Citation 仍不入库；同步补发非长连接）
- [ ] 人工标注企业 Golden Set、Qdrant 100k 索引峰值、新 ECS 加密 OSS 备份恢复、live Embedding/rerank/MinerU 冒烟、staging ECS apply
- [ ] 任一 `GATE-P0-*` verified

## 5. 未完成项与已知差距

- [x] Wave 0 基础已存在：`api/` 数据端口、`web/` 设计系统与 client；
- [x] Wave 1 领域服务已存在：auth/documents/retrieval/qa/runs/stream/exports/audit/parsing/chunking 与 `worker/`（Fake/stdlib）；
- [x] `spec/contracts/`、`spec/scenarios/`、`spec/acceptance/matrix.md` 已由 M00 建立；Golden Set v0.2-synthetic 已建（120 条合成）；企业人工标注与真实供应商 Fake 仍待；
- [x] `tests/` 已有 M00 契约 48、M03 数据 12、M08 基础 9、Wave 1 领域 97、M09 12、M10 8、M11 pipeline/ops/perf（合入后 45 passed / 2 skipped）；
- [x] 分组 CI（`.github/workflows/ci.yml` + `ops/run_grouped_tests.py`）已装配，不启动 Compose；
- [x] `docker-compose.yml` 依赖 fixture + opt-in `api` profile 已合入 main；CI **不得** `up`/`build`；本机未强制拉起；
- [x] FastAPI 健康装配：`GET /healthz`、`GET /readyz`（探测注入，失败闭环）；optional extra `http`；
- [x] FastAPI `/api/v1/auth/login|refresh|logout`（注入 AuthService 才挂载；HttpOnly refresh Cookie）；
- [x] FastAPI `GET/POST /api/v1/documents`（同时注入 DocumentService 与 AuthService 才挂载）；
- [x] FastAPI 文档详情/版本/重试/删除（`/documents/{id}` 及 `/versions|/retry|/delete`）；
- [x] FastAPI `GET /api/v1/search`（同时注入 RetrievalService 与 AuthService 才挂载）；
- [x] FastAPI `/api/v1/runs` 创建/详情/SSE 补发/取消（同时注入 RunService、QaOrchestrator 与 AuthService 才挂载）；
- [x] FastAPI `POST /api/v1/exports`、`GET /exports/{id}`、`GET /admin/audit-events`（分别与 AuthService 同时注入才挂载）；
- [x] FastAPI `POST /auth/change-password`、`GET/POST /admin/users`、`PATCH /admin/users/{id}`（status / role / reset_password）；
- [x] FastAPI `GET/POST /conversations`、`GET/DELETE /conversations/{id}`、`GET /conversations/{id}/messages`（与 AuthService 同时注入才挂载）；
- [x] FastAPI `GET /documents/{id}/preview`、`GET /documents/{id}/download`（与既有文档 router 同挂载；inline/attachment；不暴露 MinIO）；
- [x] Dockerfile + Compose api（profile `app`；默认 `docker compose up` 不起 api）；
- [x] Dockerfile.web + Compose web（profile `app`；默认 `docker compose up` 不起 web）；
- [x] Dockerfile.worker + Compose worker（profile `app`；默认 `docker compose up` 不起 worker；Celery + 注入 broker）；
- [x] `PIVOT_INGEST=celery` eager 任务适配（CI memory broker；缺省仍进程内 ingest）；
- [x] worker 进程装配共享 MinIO/PG ingest runner（CI sqlite + Fake MinIO；拒绝 memory 对象）；HTTP 缺省仍进程内 ingest；Compose api 已注入同一套 DATABASE_URL/MinIO 与 `PIVOT_INGEST=celery`；`PIVOT_VECTOR_STORE=qdrant` 时 worker 装配 IndexPublisher（CI Fake client）；
- [x] PostgreSQL 用户目录、文档事实与导出任务客户端（SQLAlchemy；默认 CI 用 sqlite；Compose Postgres 为 opt-in skip）；
- [x] MinIO 文档与导出对象（默认 CI 用内存 client；公开导出 URL 仍为 signer；Compose MinIO 为 opt-in skip）；hashed refresh、Conversation 与 Run/EventLog 可走 SQLAlchemy（CI sqlite）；Claim/Citation 仍不入库；
- [x] Qdrant 向量客户端（默认 CI 用内存 client；Compose Qdrant 为 opt-in skip）；dense 检索可消费 VectorStore；ingest `IndexPublisher` 可 `upsert`（CI Fake client）；HTTP 上传默认可进程内 ingest；`PIVOT_INGEST=celery` 为 eager；Compose api 注入 celery ingest（CI 不 up）；Compose worker 注入 broker 只听 parse，并装配共享 MinIO/PG runner 与 Qdrant IndexPublisher；Compose api/worker 注入同一套 Qdrant 变量（CI 不 up）；`PIVOT_EMBEDDING=http` / `PIVOT_RERANK=bge` 可注入（CI Fake HTTP，非 live 供应商）；ingest 与检索共用同一注入 HTTP embedder；stdlib BM25 可注入；`PIVOT_PARSER=mineru` 可注入云解析器（CI Fake HTTP；Compose api/worker 注入 `PIVOT_PARSER*`；缺省仍启发式/stdlib）；
- [x] Redis 缓存/队列客户端（默认 CI 用内存 client；Compose Redis 为 opt-in skip）；登录限流计数可注入 Redis CacheStore；Compose api 注入阈值/窗口（不写死次数；进程外缺省不锁定）；Compose Celery broker 为注入 fixture；Compose api/worker 注入 cache/queue/Redis endpoint（CI 不 up；Redis 不是业务事实源）；
- [ ] 真实 PG Alembic 冒烟因无 Docker/psycopg 为 skip；
- [ ] 所有 `TBD-P0` 均未冻结，禁止模块自行填默认值；
- [ ] P0 八项门槛均未验证；
- [x] Wave 0 三项变更申请已批准：`20260906-M00-contract-test-path.md`、`20260906-M03-ownership-clarification.md`、`20260906-M08-web-scaffold-ownership.md`。
- [x] Wave 1 观测包变更已批准：`20260906-M06-observability-package-init.md`。
- [x] Wave 1 `argon2-cffi` 已写入 pyproject：`20260906-M01-auth-dependencies.md`（2026-09-09 composition root 落实）。
- [ ] Wave 1 依赖变更仍暂缓：`20260906-M05-langgraph.md`；`20260906-M07-worker-dependencies.md` 的 Celery extra 已由本切片落实，PyMuPDF 等解析库仍暂缓。
- [x] Wave 3 FastAPI 健康端点已批准并合入：`20260907-M11-fastapi-health-assembly.md`。
- [x] Wave 3 认证 HTTP 挂载已批准并合入：`20260907-M11-api-v1-auth-mount.md`。
- [x] Wave 3 文档上传/列表 HTTP 挂载已批准并合入：`20260907-M11-api-v1-documents-mount.md`。
- [x] Wave 3 文档详情/版本/重试/删除 HTTP 已批准并合入：`20260907-M02-documents-lifecycle-http.md`。
- [x] Wave 3 搜索 HTTP 挂载已批准并合入：`20260907-M11-api-v1-search-mount.md`。
- [x] Wave 3 Run/SSE HTTP 挂载已批准并合入：`20260907-M11-api-v1-runs-sse-mount.md`。
- [x] Wave 3 导出/审计 HTTP 挂载已批准并合入：`20260908-M11-api-v1-export-audit-mount.md`。
- [x] Wave 3 改密/管理用户 HTTP 已批准并合入：`20260908-M01-auth-admin-users-http.md`。
- [x] Wave 3 会话 CRUD HTTP 已批准并合入：`20260908-M11-api-v1-conversations-mount.md`。
- [x] 主线开发流程已批准：`20260908-M00-mainline-development.md`（MODULE-SPEC-1.1）。历史 worktree 由 Owner 手动清理。
- [x] Wave 3 预览/下载 HTTP 已批准：`20260908-M02-documents-preview-download-http.md`。
- [x] Wave 3 composition root 已批准：`progress/changes/20260909-M11-composition-root.md`。
- [x] Wave 3 Next `/api/v1` 反代已批准：`progress/changes/20260909-M08-next-api-proxy.md`。
- [x] Wave 3 opt-in Playwright 登录已批准：`progress/changes/20260909-M11-playwright-login.md`。
- [x] Wave 3 PostgreSQL 用户目录客户端已批准：`progress/changes/20260909-M03-postgres-user-directory.md`。
- [x] Wave 3 MinIO 文档对象客户端已批准：`progress/changes/20260909-M03-minio-object-store.md`。
- [x] Wave 3 Qdrant 向量客户端已批准：`progress/changes/20260909-M03-qdrant-vector-store.md`。
- [x] Wave 3 Redis 缓存/队列客户端已批准：`progress/changes/20260909-M03-redis-cache-queue.md`。
- [x] Wave 3 Golden Set v0.1-synthetic 已批准：`progress/changes/20260909-M11-golden-set-synthetic.md`。
- [x] Wave 3 导出对象 MinIO 已批准：`progress/changes/20260909-M11-minio-export-objects.md`。
- [x] Wave 3 检索接 Qdrant 已批准：`progress/changes/20260909-M04-qdrant-retrieval.md`。
- [x] Wave 3 5 并发与进程内备份夹具已批准：`progress/changes/20260909-M11-capacity-backup-fixture.md`。
- [x] Wave 3 stdlib BM25 / 可注入 rerank 已批准：`progress/changes/20260909-M04-bm25-rerank.md`。
- [x] Wave 3 Dockerfile / Compose api 已批准：`progress/changes/20260909-M11-compose-api.md`。
- [x] Wave 3 100k Chunk opt-in 夹具已批准：`progress/changes/20260909-M11-chunk-capacity.md`。
- [x] Wave 3 HTTP Embedding / bge-reranker 适配器已批准：`progress/changes/20260909-M04-http-embedding-bge-rerank.md`。
- [x] Wave 3 Dockerfile.web / Compose web 已批准：`progress/changes/20260909-M11-compose-web.md`。
- [x] Wave 3 Golden Set v0.2-synthetic 已批准：`progress/changes/20260909-M11-golden-set-v02.md`。
- [x] Wave 3 ingest→Qdrant 已批准：`progress/changes/20260910-M07-ingest-qdrant.md`。
- [x] Wave 3 HTTP 上传自动 ingest 已批准：`progress/changes/20260910-M11-http-upload-ingest.md`。
- [x] Wave 3 Dockerfile.worker / Compose worker 已批准：`progress/changes/20260910-M11-compose-worker.md`。
- [x] Wave 3 Redis 登录限流已批准：`progress/changes/20260910-M01-redis-login-rate-limit.md`。
- [x] Wave 3 PostgreSQL 文档事实已批准：`progress/changes/20260910-M03-postgres-document-facts.md`。
- [x] Wave 3 Celery ingest 已批准：`progress/changes/20260910-M07-celery-ingest.md`。
- [x] Wave 3 Compose Celery worker 已批准：`progress/changes/20260910-M11-compose-celery-worker.md`。
- [x] Wave 3 worker 共享 MinIO/PG ingest 已批准：`progress/changes/20260910-M07-worker-minio-ingest.md`。
- [x] Wave 3 Compose api 共享 PG/MinIO 已批准：`progress/changes/20260910-M11-compose-api-shared-storage.md`。
- [x] Wave 3 worker Qdrant IndexPublisher 已批准：`progress/changes/20260910-M07-worker-qdrant-index.md`。
- [x] Wave 3 Compose api celery ingest 已批准：`progress/changes/20260910-M11-compose-api-celery-ingest.md`。
- [x] Wave 3 Compose api/worker Qdrant/Redis 已批准：`progress/changes/20260910-M11-compose-api-worker-qdrant-redis.md`。
- [x] Wave 3 Compose api 登录限流已批准：`progress/changes/20260910-M01-compose-login-rate.md`。
- [x] Wave 3 夹具收口评审已批准：`progress/changes/20260910-M11-wave3-closeout.md`。
- [x] Wave 3 导出任务 PostgreSQL 持久化已批准：`progress/changes/20260914-M06-postgres-export-tasks.md`。
- [x] Wave 3 PATCH 角色/重置密码 HTTP 已批准：`progress/changes/20260914-M01-admin-patch-role-reset.md`。
- [x] staging ingest/检索共用 HTTP Embedding 已批准：`progress/changes/20260914-M07-ingest-http-embedding.md`。
- [x] staging Deepseek-Flash Draft Writer 已批准：`progress/changes/20260914-M05-http-draft-writer.md`。
- [x] staging MinerU 云解析器已批准：`progress/changes/20260914-M07-mineru-cloud-parser.md`。
- [x] staging Compose overlay 已批准：`progress/changes/20260914-M11-compose-staging.md`。
- [x] Wave 3 会话/refresh 跨进程已批准：`progress/changes/20260914-M01-postgres-refresh-conversations.md`。
- [x] Wave 3 Run/EventLog 跨进程已批准：`progress/changes/20260914-M05-postgres-run-eventlog.md`。

## 6. 轮次日志

### 2026-09-14 — Run/EventLog 跨进程存储（ND-W3-14）

- **完成**：批准 `20260914-M05-postgres-run-eventlog.md`；`PIVOT_STORAGE=postgres` 时装配 `SqlAlchemyRunStore`（SPEC Run / AgentEvent / Message；fingerprint 重算不入库；answer 经 assistant Message；AgentEvent.summary 保存公开 SSE 摘要）。`RunService` 注入 `RunStore`；HTTP 同步编排后 commit。缺省 memory 不变。不把 Redis 当事实源。Claim/Citation 仍不入库。Accountable：M05 Run/SSE 端口，M03 SQL 适配，M11 装配。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`.venv/Scripts/python ops/run_grouped_tests.py --skip-web` → **572 passed, 13 skipped**（M05 28；M00-M03 96；pipeline 251 passed / 12 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。
- **限制**：CI sqlite 不是生产 PG；SSE 仍为同步补发，非 uvicorn 长连接；Claim/Citation 仍不入库；超时/SSE 预算仍 TBD-P0；GATE-P0 全部 unverified。
- **下一步**：ND-W3-08 SSE 长连接，或 ND-W3-03 真实解析库，或 Owner 提供 SSH/安全组/磁盘后实施 ND-STG-04 ECS apply，或人工标注企业 Golden Set。

### 2026-09-14 — 会话/refresh 跨进程存储（ND-W3-05）

- **完成**：批准 `20260914-M01-postgres-refresh-conversations.md`；`PIVOT_STORAGE=postgres` 时装配 `SqlAlchemyRefreshTokenStore`（只存 SHA-256 哈希）与 `SqlAlchemyConversationStore`（SPEC Conversation 字段；SQL 隐藏删除映射为删行，不新增 hidden 列）；授权 catalog 从会话 store 读 owner；缺省 memory 不变。不把 Redis 当事实源。Run/EventLog 仍 memory。Accountable：M01 refresh 端口，M05 会话端口，M03 SQL 适配/迁移，M11 装配。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`.venv/Scripts/python ops/run_grouped_tests.py --skip-web` → **565 passed, 13 skipped**（M01 37；M05 28；M00-M03 94；pipeline 246 passed / 12 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。
- **限制**：CI sqlite 不是生产 PG；access/refresh TTL 仍 TBD-P0；Run/EventLog 仍 memory 故消息不跨装配；GATE-P0 全部 unverified。
- **下一步**：Run/EventLog 跨进程，或 ND-W3-08 SSE，或 ND-W3-03 真实解析库，或 Owner 提供 SSH/安全组/磁盘后实施 ND-STG-04 ECS apply，或人工标注企业 Golden Set。

### 2026-09-14 — dev-staging Compose overlay（ND-STG-04）

- **完成**：批准 `20260914-M11-compose-staging.md`；入库 `docker-compose.staging.yml` + nginx 反代 web（默认 `${PIVOT_STAGING_HTTP_BIND:-127.0.0.1}:80:80`）；overlay 为 8 个服务补 restart / 日志轮转 / 8GiB 档 limits fixture；env 副本 gitignore；Runbook 列出 Owner SSH/安全组/磁盘/域名前置。不自建 MinerU/LLM。CI 不 up。Accountable：M11。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`.venv/Scripts/python ops/run_grouped_tests.py --skip-web` → **557 passed, 13 skipped**（M07 62；M00-M03 90；pipeline 242 passed / 12 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。
- **限制**：未 SSH、未改安全组、未挂数据盘、未打 live 冒烟；8GiB limits 不是冻结 TBD-P0；yml 不写 4C8G；GATE-P0-007/008 仍 unverified。
- **下一步**：Owner 提供 SSH/安全组/磁盘/域名后才上机；编码下一刀 ND-W3-05 会话/refresh 跨进程，或人工标注企业 Golden Set。

### 2026-09-14 — MinerU 云解析器（ND-STG-03）

- **完成**：批准 `20260914-M07-mineru-cloud-parser.md`；`PIVOT_PARSER=mineru` 时装配注入 endpoint/token 的 `MinerUCloudParser`（异步 batch 上传/轮询/zip）；加密/损坏本地拦截；扫描件走云 OCR；失败码沿用 `FR-DOC-004` 与 provider 码；Compose api/worker 注入同一套 `PIVOT_PARSER*`（选择 `${:?}`，yml 不写死 URL/模型）。缺省仍启发式/stdlib。Accountable：M07 解析器/装配，M11 Compose/bootstrap。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **544 passed, 12 skipped**（M07 62；M00-M03 90；pipeline 229 passed / 11 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。
- **限制**：CI Fake HTTP，不是 live MinerU；不冻页数/大小/轮询超时/模型名；不把 MinerU 标成 MVP 唯一解析器；不在 4C8G 自建；GATE-P0 全部 unverified。
- **下一步**：Owner 提供 SSH/安全组/磁盘后实施 ND-STG-04 ECS apply，或会话/refresh 跨进程（ND-W3-05），或人工标注企业 Golden Set。

### 2026-09-14 — Deepseek-Flash Draft Writer（ND-STG-02）

- **完成**：批准 `20260914-M05-http-draft-writer.md`；`PIVOT_LLM=http` 时装配注入 endpoint/model/api_key 的 OpenAI 兼容 Writer；鉴权头可注入；主失败（超时/429/5xx）才切 `PIVOT_LLM_FALLBACK_*`；Citation 只从检索候选生成；`external_llm_allowed=false` 不得 HTTP，Run `refused`；Compose 仅 api 注入 `PIVOT_LLM*`（yml 不写死 URL/模型）。缺省仍 local 证据拼接。Accountable：M05 Writer/编排，M02/M03 版本门禁字段，M11 装配/Compose。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **519 passed, 12 skipped**（M05 28；M02 28；M00-M03 90；pipeline 223 passed / 11 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。
- **限制**：CI Fake HTTP，不是 live DeepSeek/小米；不冻模型名/超时/token；LangGraph extra 仍暂缓；GATE-P0 全部 unverified。
- **下一步**：ND-STG-03 MinerU 云解析器，或会话/refresh 跨进程（ND-W3-05），或人工标注企业 Golden Set。

### 2026-09-14 — ingest 与检索共用注入 HTTP Embedding（ND-STG-01）

- **完成**：批准 `20260914-M07-ingest-http-embedding.md`；`PIVOT_EMBEDDING=http` 时 `assemble_runtime` ingest 与 query 共用同一 `HttpQueryEmbedder`；`assemble_ingest_runtime` 装配同形 HTTP embedder（维数仍注入）；HTTP 失败不 published、不回显 api_key；Compose api/worker 注入同一套 `PIVOT_EMBEDDING*`（选择 `${:?}`，endpoint/model/key `${:-}`，yml 不写死 URL/模型）。缺省仍 hash。Accountable：M07 装配/失败闭环，M04 只消费既有 embedder，M11 Compose。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **494 passed, 12 skipped**（M07 43；M00-M03 89；pipeline 216 passed / 11 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。
- **限制**：CI Fake HTTP，不是 live 硅基 bge-m3；不冻模型名/维数/超时；HTTP 缺省仍请求内 ingest；Rerank 仍只在 runtime；GATE-P0 全部 unverified。
- **下一步**：ND-STG-02 Deepseek-Flash Writer，或会话/refresh 跨进程（ND-W3-05），或人工标注企业 Golden Set。

### 2026-09-14 — PATCH 角色 / 重置密码 HTTP（ND-W3-07）

- **完成**：批准 `20260914-M01-admin-patch-role-reset.md`；`PATCH /api/v1/admin/users/{id}` 处理契约已有 `role` / `status` / `reset_password`；角色变更抬升 `token_version`、撤销 refresh 并审计 `auth.role_change`；重置口令经 HTTPS JSON 一次性返回且不进审计；未知用户 404。`must_change_password` 不入库；不冻结传递机制。Accountable：M01 领域/HTTP，M11 pipeline 测试。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **483 passed, 12 skipped**（M01 37；M00-M03 89；pipeline 210 passed / 11 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。
- **限制**：初始密码传递机制仍 TBD-P0；GET/POST 仍不回显口令；refresh 仍 memory；GATE-P0 全部 unverified。
- **下一步**：staging Embedding（ND-STG-01），或会话/refresh 跨进程（ND-W3-05），或人工标注企业 Golden Set。

### 2026-09-14 — 导出任务 PostgreSQL 持久化（ND-W3-04）

- **完成**：批准 `20260914-M06-postgres-export-tasks.md`；`SqlAlchemyExportRepository` 按 SPEC ExportTask 字段读写；`PIVOT_STORAGE=postgres` 时与用户目录/文档事实共用 session factory；跨装配 GET 可见 `ready` + `PublicDownloadSigner` URL；不新增 filename 等非 SPEC 列；不新增对象字节下载 HTTP。Accountable：M06 端口消费，M03 SQL 适配，M11 装配。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **475 passed, 12 skipped**（M00-M03 89；pipeline 206 passed / 11 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。
- **限制**：CI sqlite 不是生产 PG；导出 TTL 仍 TBD-P0；无对象字节下载 HTTP；PATCH 角色未挂；GATE-P0 全部 unverified。
- **下一步**：PATCH 角色（ND-W3-07），或 staging Embedding（ND-STG-01），或人工标注企业 Golden Set。

### 2026-09-10 — Wave 3 夹具收口评审（ND-W3-13）

- **完成**：批准 `20260910-M11-wave3-closeout.md`；核对 A1（ND-W3-01/02/12）与 ND-W3-06 已合入；回填矩阵为 Wave 3 夹具基线；证据写明八项 GATE-P0 仍 unverified；`wave-3-integrated` 仅表示夹具收口，不等于 P0 通过。Accountable：M11 收口，M00 矩阵/MODULE_SPEC 现状。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）：`python ops/run_grouped_tests.py --skip-web` → **469 passed, 12 skipped**（pipeline 202 passed / 11 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。
- **限制**：CI 不 build/up；HTTP 缺省仍请求内 ingest；导出任务仍内存；PATCH 角色未挂；Golden Set 仍为合成；未冻结 TBD-P0；GATE-P0 全部 unverified。
- **下一步**：导出任务 PG（ND-W3-04），或 PATCH 角色（ND-W3-07），或 staging Embedding（ND-STG-01），或人工标注企业 Golden Set。

### 2026-09-10 — Wave 3 Compose api 注入登录限流阈值/窗口

- **完成**：批准 `20260910-M01-compose-login-rate.md`；Compose `api` 同时注入 `PIVOT_LOGIN_MAX_FAILURES` / `PIVOT_LOGIN_WINDOW_SECONDS`（`${:?}`，yml 不写死次数）；example fixture 占位（不是冻结 TBD-P0）；worker 不注入；进程外 `assemble_runtime` 两者都缺时仍永不锁定；锁定后仍统一 `AUTH_INVALID_CREDENTIALS`。Accountable：M01 限流端口，M11 Compose 装配。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）：`python ops/run_grouped_tests.py --skip-web` → **463 passed, 12 skipped**；ruff / compileall 通过。
- **限制**：CI 不 build/up；阈值/窗口仍 TBD-P0；未打 `wave-3-integrated`；GATE-P0 全部 unverified。未冻结失败次数。
- **下一步**：Wave 3 收口评审（ND-W3-13），或导出任务 PG / PATCH 角色，或人工标注企业 Golden Set。

### 2026-09-10 — Wave 3 Compose api/worker 注入 Qdrant/Redis

- **完成**：批准 `20260910-M11-compose-api-worker-qdrant-redis.md`；Compose `api` 与 `worker` 注入同一套 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*` / `PIVOT_CACHE_STORE` / `PIVOT_QUEUE_STORE` / `PIVOT_REDIS_ENDPOINT`（`${}`，store 选择 `${:?}` 不静默 `:-memory`，yml 不写死 URL/维数/距离）；example 占位 `qdrant`/`redis`。Accountable：M11 Compose 装配。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）：`python ops/run_grouped_tests.py --skip-web` → **461 passed, 12 skipped**；ruff / compileall 通过。
- **限制**：CI 不 build/up；进程外 `assemble_runtime` 缺省仍 memory；Redis 不是业务事实源；未注入登录失败阈值；未打 `wave-3-integrated`；GATE-P0 全部 unverified。未冻结距离/TTL/维数。
- **下一步**：登录限流缺省接到 Redis（ND-W3-06），或 Wave 3 收口评审（ND-W3-13），或人工标注企业 Golden Set。

### 2026-09-10 — Wave 3 Compose api 注入 `PIVOT_INGEST=celery`

- **完成**：批准 `20260910-M11-compose-api-celery-ingest.md`；Compose `api` 注入 `PIVOT_INGEST` / 队列名 / concurrency / `PIVOT_CELERY_BROKER`（`${:?}`，不写死 `redis://`，不静默 `:-sync`）；example 占位 `celery`；Dockerfile 安装 `./worker[celery]`，CMD 仍 uvicorn factory。Accountable：M11 Compose 装配，M07 只消费既有 submitter。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）：`python ops/run_grouped_tests.py --skip-web` → **457 passed, 12 skipped**；ruff / compileall 通过。
- **限制**：CI 不 build/up；不注入 `PIVOT_CELERY_EAGER`；进程外 `assemble_runtime` 缺省仍 sync；Compose api 未必选接 Qdrant/Redis；未打 `wave-3-integrated`；GATE-P0 全部 unverified。未冻结 concurrency/broker。
- **下一步**：人工标注企业 Golden Set，或 Compose 注入 Qdrant/Redis。

### 2026-09-10 — Wave 3 worker 装配 Qdrant IndexPublisher

- **完成**：批准 `20260910-M07-worker-qdrant-index.md`；`assemble_ingest_runtime` 在 `PIVOT_VECTOR_STORE=qdrant` 时装配 `IndexPublisher` + 注入维数的 `HashingQueryEmbedder`；缺 endpoint/collection/vector_size 失败闭环；Compose worker 注入 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*`，yml 不写死 URL/维数/距离。Accountable：M07 进程装配，M11 Compose 注入。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）：`python ops/run_grouped_tests.py --skip-web` → **453 passed, 12 skipped**；ruff / compileall 通过。
- **限制**：CI Fake Qdrant client + Hashing embedder，不是 live 供应商；HTTP 缺省仍进程内 ingest；Compose api 未注入 `PIVOT_INGEST=celery` / Qdrant；未打 `wave-3-integrated`；GATE-P0 全部 unverified。未冻结维数/距离。
- **下一步**：人工标注企业 Golden Set，或 Compose api 注入 celery ingest，或 Compose 注入 Qdrant/Redis。

### 2026-09-10 — Wave 3 Compose api 注入共享 PG/MinIO

- **完成**：批准 `20260910-M11-compose-api-shared-storage.md`；Compose `api` 与 `worker` 注入同一套存储/MinIO 变量（`${:?}`，不写死 URL，不静默 `:-memory`）；example 占位 `postgres`/`minio`；HTTP composition root 与 worker assembly 可共享 Fake MinIO 对象字节。Accountable：M11 Compose 装配。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）：`python ops/run_grouped_tests.py --skip-web` → **445 passed, 12 skipped**；ruff / compileall 通过。
- **限制**：CI 不 build/up；HTTP 缺省仍进程内 ingest；Compose api 未注入 `PIVOT_INGEST=celery`；worker 未必选接 Qdrant；未打 `wave-3-integrated`；GATE-P0 全部 unverified。未冻结 endpoint。
- **下一步**：人工标注企业 Golden Set，或 worker 接 Qdrant，或 Compose api 注入 celery ingest。

### 2026-09-10 — Wave 3 worker 装配共享 MinIO/PG ingest runner

- **完成**：批准 `20260910-M07-worker-minio-ingest.md`；`assemble_ingest_runtime` 为 worker 装配 `DocumentIngestRunner`（PG 事实 + MinIO 对象）；拒绝 memory 存储/对象；`python -m pivot_worker` 在 Celery 前装配 runner；Compose worker 注入存储/MinIO 变量，yml 不写死 URL。Accountable：M07 进程装配，M11 Compose 注入。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）：`python ops/run_grouped_tests.py --skip-web` → **441 passed, 12 skipped**；ruff / compileall 通过。
- **限制**：CI sqlite + Fake MinIO，不是 live MinIO/PG/Celery；HTTP 缺省仍进程内 ingest；Compose api 尚未注入同一套 DATABASE_URL/MinIO；worker 未必选接 Qdrant；未打 `wave-3-integrated`；GATE-P0 全部 unverified。未冻结 endpoint/concurrency。
- **下一步**：人工标注企业 Golden Set，或 Compose api 注入共享 PG/MinIO，或 worker 接 Qdrant。

### 2026-09-10 — Wave 3 Compose Celery worker（注入 Redis broker）

- **完成**：批准 `20260910-M11-compose-celery-worker.md`；`Dockerfile.worker` 安装 `worker[celery]`；`python -m pivot_worker` 在 `/healthz` 后启动 Celery，只监听 parse 队列；Compose 注入 `PIVOT_CELERY_BROKER`，yml 不写死 `redis://`。Accountable：M11 装配，M07 进程入口。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）：`python ops/run_grouped_tests.py --skip-web` → **431 passed, 12 skipped**；ruff / compileall 通过。
- **限制**：CI 不 build/up；worker 未装配共享 MinIO/PG ingest runner；HTTP 缺省仍进程内 ingest；未打 `wave-3-integrated`；GATE-P0 全部 unverified。未冻结 concurrency/broker。
- **下一步**：人工标注企业 Golden Set，或 worker 装配共享 MinIO/PG ingest runner。

### 2026-09-10 — Wave 3 Celery ingest 可见 PG version/task

- **完成**：批准 `20260910-M07-celery-ingest.md`；`worker[celery]` extra；`CeleryIngestSubmitter` 把既有 runner 注册到 parse 队列；`PIVOT_INGEST=celery` 时 HTTP 入队（CI eager + 注入 `memory://`）；第二装配可从 sqlite 文档事实读取 version，ingest 后 `celery_tasks` 可见。Accountable：M07 任务适配，M11 装配。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）：`python ops/run_grouped_tests.py --skip-web` → **426 passed, 12 skipped**；ruff / compileall 通过。
- **限制**：eager + memory broker 不是 Redis/Celery worker；Compose worker CMD 仍 ping；对象字节仍需共享 ObjectStore；sqlite 不是生产 PG；未打 `wave-3-integrated`；GATE-P0 全部 unverified。未冻结 concurrency/broker。
- **下一步**：人工标注企业 Golden Set，或 Compose/Redis broker 上的 Celery worker / 共享 MinIO 对象字节。

### 2026-09-10 — Wave 3 PostgreSQL 文档事实

- **完成**：批准 `20260910-M03-postgres-document-facts.md`；`SqlAlchemyDocumentStore`/`VersionStore`/`ChunkStore`/`TaskStore`；`PIVOT_STORAGE=postgres` 时与用户目录共用 session factory；HTTP 上传后新装配可列出/打开详情。Accountable：M03 适配，M02 publish 写回 chunk，M11 装配。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **414 passed, 12 skipped**；ruff / compileall 通过。
- **限制**：sqlite 测试 URL 不是生产 PG；未持久化 version.idempotency_key；对象字节仍 memory/MinIO；非 Celery；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：Celery 队列（文档事实已可跨装配），或人工标注企业 Golden Set。

### 2026-09-10 — Wave 3 Redis 登录限流计数

- **完成**：批准 `20260910-M01-redis-login-rate-limit.md`；`CacheLoginAttempts` 把失败计数写入注入 CacheStore；`PIVOT_LOGIN_MAX_FAILURES`/`PIVOT_LOGIN_WINDOW_SECONDS` 同时注入且 `PIVOT_CACHE_STORE=redis` 才锁定；缺省永不锁定；锁定后仍统一 `AUTH_INVALID_CREDENTIALS`。Accountable：M01 限流端口，M11 装配。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **408 passed, 12 skipped**；ruff / compileall 通过。
- **限制**：阈值/窗口仍 TBD-P0；CI 内存 Redis client；无 Celery；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：人工标注企业 Golden Set，或 Celery 队列。

### 2026-09-10 — Wave 3 Dockerfile.worker 与 Compose worker

- **完成**：批准 `20260910-M11-compose-worker.md`；`Dockerfile.worker` 钉 `python:3.12.10-slim-bookworm`，`python -m pivot_worker` 提供 `/healthz` ping；Compose `worker` 为 profile `app`，端口 `127.0.0.1:8001`，注入隔离的 parse/online 队列与 concurrency；`IngestQueueConsumer` 只消费 parse 队列。Accountable：M11 装配，M07 进程入口。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **398 passed, 12 skipped**；ruff / compileall 通过。
- **限制**：非 Celery；HTTP 上传仍进程内 ingest；CI 不 build/up；本机未强制拉起容器；未打 `wave-3-integrated`；GATE-P0 全部 unverified。未冻结 concurrency / ECS 4C8G。
- **下一步**：人工标注企业 Golden Set，或 Celery 队列，或 Qdrant 100k 索引峰值。

### 2026-09-10 — Wave 3 HTTP 上传进程内 ingest

- **完成**：批准 `20260910-M11-http-upload-ingest.md`；`DocumentService.prepare_ingest`；`DocumentIngestRunner`；`assemble_runtime` 注入后 `POST /documents` 信封仍 `uploaded`，随后进程内跑 Worker 至 `ready`；qdrant 时搜索可召回；重复 SHA 不重入。Accountable：M02 状态准备/HTTP，M07 runner，M11 装配。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **389 passed, 11 skipped**；ruff / compileall 通过。
- **限制**：非 Celery / 非 Compose worker；请求内同步执行；CI Fake embedder；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：Compose worker，或人工标注企业 Golden Set。

### 2026-09-10 — Wave 3 ingest→Qdrant

- **完成**：批准 `20260910-M07-ingest-qdrant.md`；`IndexPublisher` 可注入 `VectorStore`，`publish` 前 `upsert`；payload 含水合字段；缺 `document_id` 或 upsert 失败不 published。`PIVOT_VECTOR_STORE=qdrant` 时 ingest embedding 复用 query embedder。HTTP 上传不自动跑 Worker。Accountable：M07 索引发布，M11 装配。
- **验证**（main，2026-09-10，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **379 passed, 11 skipped**；ruff / compileall 通过。
- **限制**：CI 内存 client + Fake embedder；不是真实 Qdrant 原子发布；无 Celery / Compose worker；未打 `wave-3-integrated`；GATE-P0 全部 unverified。维数/距离仍 TBD-P0。
- **下一步**：Compose worker，或人工标注企业 Golden Set，或 HTTP 上传自动 ingest。

### 2026-09-09 — Wave 3 Golden Set v0.2-synthetic（120 条）

- **完成**：批准 `20260909-M11-golden-set-v02.md`；确定性生成器 `ops/golden_set_synthetic.py` 产出 `v0.2-synthetic.json`（十层各 12 条，共 120）；评测器默认改载 v0.2；v0.1 保留。Accountable：M04 夹具路径，M11 评测/证据。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **369 passed, 11 skipped**；ruff / compileall 通过。
- **限制**：仍是合成 Fake Keyword，不是企业人工标注；未冻结 NFR-QUAL；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：ingest→Qdrant，或 Compose worker，或人工标注企业 Golden Set。

### 2026-09-09 — Wave 3 Dockerfile.web 与 Compose web

- **完成**：批准 `20260909-M11-compose-web.md`；`Dockerfile.web` 钉 `node:20.19.0-bookworm-slim`，`next start --hostname 0.0.0.0 --port 3000`；Compose `web` 为 profile `app`，端口 `127.0.0.1:3000`，healthcheck `/login`，`PIVOT_API_ORIGIN` 注入，依赖 api healthy。Accountable：M11。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **368 passed, 11 skipped**；ruff / compileall 通过。
- **限制**：CI 不 build/up；本机未强制拉起容器；无 worker；未打 `wave-3-integrated`；GATE-P0 全部 unverified。未冻结 ECS 4C8G / 浏览器版本。
- **下一步**：Golden Set 100~150，或 ingest→Qdrant，或 Compose worker。

### 2026-09-09 — Wave 3 HTTP Embedding / bge-reranker 适配器

- **完成**：批准 `20260909-M04-http-embedding-bge-rerank.md`；`HttpQueryEmbedder` / `HttpBgeReranker` 注入 endpoint/model/key/timeout；`PIVOT_EMBEDDING=hash|http`（http 需 qdrant）；`PIVOT_RERANK` 增 `bge`；CI 用 `ScriptedJsonHttpClient`；rerank 失败回退 RRF。Accountable：M04 实现，M11 装配。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **363 passed, 10 skipped**；ruff / compileall 通过。
- **限制**：非 live 供应商冒烟；ingest 仍 Fake Embedding；未打 `wave-3-integrated`；GATE-P0 全部 unverified。维数/模型/超时/阈值仍 TBD-P0。
- **下一步**：Compose web，或 Golden Set 100~150，或 ingest→Qdrant。

### 2026-09-09 — Wave 3 100k Chunk opt-in 夹具

- **完成**：批准 `20260909-M11-chunk-capacity.md`；`ops/chunk_capacity.py` 要求注入 `PIVOT_CHUNK_COUNT`；`PIVOT_REQUIRE_100K=1` 时必须为 100000。CI 用小 N retrieve；tracemalloc peak 只记录不作为门禁。Accountable：M11。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **346 passed, 10 skipped**；ruff / compileall 通过。
- **限制**：CI 不跑 100k；进程内 Fake Keyword，不是 Qdrant 索引峰值 / ECS 4C8G；未打 `wave-3-integrated`；GATE-P0 全部 unverified。P95/内存阈值仍 TBD-P0。
- **下一步**：真实 Embedding/bge-reranker，或 Compose web。

### 2026-09-09 — Wave 3 Dockerfile 与 Compose api

- **完成**：批准 `20260909-M11-compose-api.md`；根 `Dockerfile` 钉 `python:3.12.10-slim-bookworm`，`uvicorn pivot.http.main:app --factory`；Compose `api` 为 profile `app`，端口 `127.0.0.1:8000`，healthcheck `/healthz`，TTL/k 环境注入。默认 `docker compose up` 仍只起依赖。Accountable：M11。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **340 passed, 9 skipped**；ruff / compileall 通过。
- **限制**：CI 不 build/up；本机未强制拉起容器；无 worker/web；未打 `wave-3-integrated`；GATE-P0 全部 unverified。未冻结 TTL/k/ECS 4C8G。
- **下一步**：100k Chunk 夹具，或真实 Embedding/bge-reranker，或 Compose web。

### 2026-09-09 — Wave 3 stdlib BM25 与可注入 rerank

- **完成**：批准 `20260909-M04-bm25-rerank.md`；`Bm25Retriever` + `SimpleLexTokenizer`（CJK 单字，非 jieba）；k1/b 注入；`PIVOT_RERANK=none|overlap|bm25`（非 bge）。未注入 BM25 参数时 runtime 仍 Keyword。Accountable：M04 实现，M11 装配。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **334 passed, 8 skipped**；ruff / compileall 通过。
- **限制**：非生产分词/bge；Golden Set 仍 Keyword；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：100k Chunk / Compose api，或真实 Embedding/bge-reranker。

### 2026-09-09 — Wave 3 5 并发夹具与进程内备份恢复

- **完成**：批准 `20260909-M11-capacity-backup-fixture.md`；5 路并发 `retrieve` 全部完成；`ops/fact_backup.py` 对用户/对象/向量点/审计 roundtrip，Redis 不进事实包；恢复记 `ops.backup_restore`。不采集 P95，不冻结 RPO/RTO，CI 不生成 100k。Accountable：M11。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **323 passed, 8 skipped**；ruff / compileall 通过。
- **限制**：进程内 Fake，不是 ECS 压测/加密 OSS/新 ECS 演练；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：stdlib BM25 已完成；再下一步为 100k Chunk / Compose api。

### 2026-09-09 — Wave 3 检索 dense 路接到 Qdrant

- **完成**：批准 `20260909-M04-qdrant-retrieval.md`；`PIVOT_VECTOR_STORE=qdrant` 时 dense 为 `VectorStoreRetriever` 消费 `QdrantVectorStore`；query embedder 为注入维数的 `HashingQueryEmbedder`；k 来自 `PIVOT_RETRIEVAL_K`，不写死 50/距离。空 corpus 的 `search_documents` 走 payload 水合；payload 缺 ready/current/allowed 失败闭环。BM25 仍 Fake Keyword。Accountable：M04 检索适配，M11 装配。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / fastapi 0.141.1）：`python ops/run_grouped_tests.py --skip-web` → **314 passed, 8 skipped**；ruff / compileall 通过。
- **限制**：Fake embedder 不是生产 Embedding；无 ingest→Qdrant；Golden Set 仍 Keyword；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：5 并发 / 备份恢复夹具已完成；再下一步为真实 BM25/rerank 或 100k Chunk。

### 2026-09-09 — Wave 3 导出对象接到 MinIO

- **完成**：批准 `20260909-M11-minio-export-objects.md`；`PIVOT_OBJECT_STORE=minio` 时导出字节经 `ExportObjectAdapter` 写入同一 MinIO bucket；公开 `download_url` 仍为 `PublicDownloadSigner`，`presign` 失败闭环。Accountable：M11 装配，M06 只消费端口。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / fastapi 0.141.1）：`python ops/run_grouped_tests.py --skip-web` → **301 passed, 8 skipped**；ruff / compileall 通过。
- **限制**：内存 client 不是生产 MinIO；无对象字节下载 HTTP；导出任务仍内存；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：检索接 Qdrant 已完成；再下一步为 5 并发 / 备份恢复。

### 2026-09-09 — Wave 3 Golden Set v0.1-synthetic

- **完成**：批准 `20260909-M11-golden-set-synthetic.md`；`spec/fixtures/golden-set/retrieval/v0.1-synthetic.json` 覆盖 SPEC §10.8 十层；M11 Fake 检索标签评测。Accountable：M04 夹具路径，M11 评测/证据。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`python ops/run_grouped_tests.py --skip-web` → **296 passed, 8 skipped**；ruff / compileall 通过。
- **限制**：10 条合成样本，不是 100~150；Fake KeywordRetriever；未冻结 NFR-QUAL；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：导出对象 MinIO / 检索接 Qdrant，或 5 并发 / 备份恢复。

### 2026-09-09 — Wave 3 Redis 缓存/队列客户端

- **完成**：批准 `20260909-M03-redis-cache-queue.md`；M03 `RedisCacheStore`/`RedisQueueStore` + optional extra `redis`；M11 `PIVOT_CACHE_STORE`/`PIVOT_QUEUE_STORE=redis` 装配，缺 endpoint 失败闭环。登录限流仍内存 Attempts。Accountable：M03 适配器，M11 装配。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / fastapi 0.141.1）：`python ops/run_grouped_tests.py --skip-web` → **291 passed, 8 skipped**；ruff / compileall 通过。
- **限制**：内存 client 不是生产 Redis；未冻结限流阈值；无 Celery；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：Golden Set / 性能门禁，或导出对象 MinIO / 检索接 Qdrant。

### 2026-09-09 — Wave 3 Qdrant 向量客户端

- **完成**：批准 `20260909-M03-qdrant-vector-store.md`；M03 `QdrantVectorStore` + optional extra `qdrant`；M11 `PIVOT_VECTOR_STORE=qdrant` 装配向量端口，缺 endpoint/collection 失败闭环。检索仍为 Fake KeywordRetriever。Accountable：M03 适配器，M11 装配。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / fastapi 0.141.1）：`python ops/run_grouped_tests.py --skip-web` → **278 passed, 7 skipped**；ruff / compileall 通过。
- **限制**：内存 client 不是生产 Qdrant；未冻结距离函数/维数/k；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：Redis 队列/缓存客户端，或 Golden Set / 性能门禁。

### 2026-09-09 — Wave 3 MinIO 文档对象客户端

- **完成**：批准 `20260909-M03-minio-object-store.md`；M03 `MinioObjectStore` + optional extra `minio`；M11 `PIVOT_OBJECT_STORE=minio` 装配文档对象，缺 endpoint/bucket/密钥失败闭环。导出仍走 memory + `PublicDownloadSigner`。Accountable：M03 适配器，M11 装配。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / fastapi 0.141.1）：`python ops/run_grouped_tests.py --skip-web` → **266 passed, 6 skipped**；ruff / compileall 通过。
- **限制**：内存 client 不是生产 MinIO；预览不暴露 endpoint/密钥；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：Qdrant/Redis 客户端，或 Golden Set / 性能门禁。

### 2026-09-09 — Wave 3 PostgreSQL 用户事实源客户端

- **完成**：批准 `20260909-M03-postgres-user-directory.md`；M03 `SqlAlchemyUserDirectory` 按 SPEC §2.2 User 字段实现 `UserDirectory`；M11 `PIVOT_STORAGE=postgres` 要求 `PIVOT_DATABASE_URL`，失败闭环不回退 memory。Accountable：M03 目录，M11 装配。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / fastapi 0.141.1）：`python ops/run_grouped_tests.py --skip-web` → **256 passed, 5 skipped**；ruff / compileall 通过。
- **限制**：sqlite 测试 URL 不是生产事实源；`must_change_password` 不入库；文档对象等仍为 memory；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：MinIO ObjectStore 客户端，或 Golden Set / 性能门禁。

### 2026-09-09 — Wave 3 opt-in Playwright 浏览器登录

- **完成**：批准 `20260909-M11-playwright-login.md`；Chromium 打开 `/login` 经 Next rewrite 打到 composition root；错误密码统一文案。Accountable：M11 测试/ops，M03 `playwright` extra。
- **验证**（main，2026-09-09）：`python ops/run_grouped_tests.py --skip-web` → **247 passed, 4 skipped**；opt-in `PIVOT_REQUIRE_PLAYWRIGHT=1` → 浏览器登录 **2 passed**（playwright 1.62.0 / Next 14.2.15）。
- **限制**：CI 不启动 uvicorn/Next；未打 `wave-3-integrated`；GATE-P0 全部 unverified；Chrome/Edge 版本仍 TBD-P0。
- **下一步**：真实存储客户端，或 Golden Set / 性能门禁。

### 2026-09-09 — Wave 3 Next `/api/v1` 反代

- **完成**：批准 `20260909-M08-next-api-proxy.md`；`apiProxyRewrites` + `next.config.mjs` 把 `/api/v1/:path*` 转到注入的 `PIVOT_API_ORIGIN`；浏览器 `API_BASE` 仍为 `/api/v1`。Accountable：M08 next.config，M11 证据。
- **验证**（main，2026-09-09，Node v24.15.0 / Next 14.2.15）：`npm --prefix web test` → **15 passed**；user E2E **12**；admin E2E **8**；typecheck/lint 通过。未启动 Next/uvicorn。
- **限制**：当时无 Playwright；未设 origin 时登录仍 404；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：Playwright 登录已完成（opt-in）；再下一步为真实存储客户端。

### 2026-09-09 — Wave 3 composition root

- **完成**：批准 `20260909-M11-composition-root.md`；M11 `assemble_runtime` / `assemble_runtime_app` / `uvicorn pivot.http.main:app --factory`；运行时 Argon2id + memory 端口；M03 将 `argon2-cffi` 写入 `api/pyproject.toml`。Accountable：M11 装配，M03 依赖锁。
- **验证**（main，2026-09-09，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / fastapi 0.141.1 / argon2-cffi 25.1.0）：`python ops/run_grouped_tests.py --skip-web` → **245 passed, 2 skipped**；ruff / compileall 通过。
- **限制**：memory 适配，非真实 PG/MinIO；未加 Dockerfile / Compose api；未打 `wave-3-integrated`；GATE-P0 全部 unverified。TTL/检索 k 仅注入，未冻结 TBD-P0。
- **下一步**：Next 反代已完成；再下一步为 Playwright 或真实存储客户端。

### 2026-09-08 — Wave 3 文档预览/下载 HTTP

- **完成**：批准 `20260908-M02-documents-preview-download-http.md`；M02 `ObjectStore.get` + `DocumentService.open_content`；`GET /api/v1/documents/{id}/preview|download`；M11 pipeline HTTP 测试。Accountable：M02 领域/router，M11 pipeline。
- **验证**（main，2026-09-08，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / fastapi 0.141.1）：`python ops/run_grouped_tests.py --skip-web` → **236 passed, 2 skipped**；ruff / compileall 通过。
- **限制**：内存 Fake 对象字节；无真实 MinIO；未启动 uvicorn；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：composition root 已完成；再下一步为 Next 反代 `/api/v1`。

### 2026-09-08 — 改为主线开发（MODULE-SPEC-1.1）

- **完成**：批准 `20260908-M00-mainline-development.md`；默认工作区改为 `Pivot/` 的 `main`；废止为每个模块新建 worktree；主线切片可跨模块路径并直接更新本文件。
- **未做**：未删除 `E:/AI Project/Pivot-Mxx-*` 历史目录（需 Owner 手动 `git worktree remove`）。
- **下一步**：仍在 Wave 3；下一刀预览/下载 HTTP。不要冻结 `TBD-P0`。

### 2026-09-08 — Wave 3 `/api/v1/conversations` 合入 main

- **完成**：批准 `20260908-M11-api-v1-conversations-mount.md`；M05 `ConversationService` + `build_conversations_router`；M11 `create_app(conversations=..., auth=...)` 注入挂载；非快进合并 `module/M05-conversations-http`（`19da428`）；tag `M05-v0.3.0`。
- **验证**（main，2026-09-08）：`python ops/run_grouped_tests.py --skip-web` → **227 passed, 2 skipped**；ruff / compileall 通过。
- **限制**：内存会话；删除为隐藏；消息由已持久化 Run 合成；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：预览/下载 HTTP。

### 2026-09-08 — Wave 3 改密与管理员用户 HTTP 合入 main

- **完成**：批准 `20260908-M01-auth-admin-users-http.md`；M01 扩展 `build_auth_router`；非快进合并 `module/M01-admin-users-http`（`6cb9118`）；tag `M01-v0.3.0`。
- **验证**（main，2026-09-08）：`python ops/run_grouped_tests.py --skip-web` → **221 passed, 2 skipped**；ruff / compileall 通过。
- **限制**：PATCH 仅 `status`；不回显初始密码；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：会话 CRUD HTTP 或预览/下载 HTTP。

### 2026-09-08 — Wave 3 `/api/v1/exports` 与审计查询合入 main

- **完成**：批准 `20260908-M11-api-v1-export-audit-mount.md`；M06 `build_exports_router` / `build_audit_router`；M11 `create_app(exports=..., audits=..., auth=...)` 注入挂载；非快进合并 `module/M06-export-http`（`35d37bc`）；tag `M06-v0.2.0`。
- **验证**（main，2026-09-08）：`python ops/run_grouped_tests.py --skip-web` → **216 passed, 2 skipped**；ruff / compileall 通过。
- **限制**：导出为内存存储 + 短时公开 URL，无对象字节下载 HTTP；无预览/下载；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：预览/下载 HTTP 或改密/管理用户 HTTP。

### 2026-09-07 — Wave 3 `/api/v1/runs` 与 SSE 合入 main

- **完成**：批准 `20260907-M11-api-v1-runs-sse-mount.md`；M05 `build_runs_router`；M01 `ensure_conversation_owner`；M11 `create_app(runs=..., qa=..., auth=...)` 注入挂载；非快进合并 `module/M05-runs-http`（`717b7ad`）；tag `M05-v0.2.0`。
- **验证**（main，2026-09-07）：`python ops/run_grouped_tests.py --skip-web` → **208 passed, 2 skipped**；ruff / compileall 通过。
- **限制**：SSE 为内存 EventLog 补发，非 uvicorn 长连接；无导出 HTTP；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：导出 HTTP。

### 2026-09-07 — Wave 3 `/api/v1/search` 合入 main

- **完成**：批准 `20260907-M11-api-v1-search-mount.md`；M04 `build_search_router`；M11 `create_app(retrieval=..., auth=...)` 注入挂载；非快进合并 `module/M04-search-http`（`0750291`）；tag `M04-v0.2.0`。
- **验证**（main，2026-09-07）：`python ops/run_grouped_tests.py --skip-web` → **201 passed, 2 skipped**；ruff / compileall 通过。
- **限制**：检索为 Fake；无问答 SSE/导出 HTTP；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：问答 SSE 或导出 HTTP。

### 2026-09-07 — Wave 3 文档详情/重试/删除 HTTP 合入 main

- **完成**：批准 `20260907-M02-documents-lifecycle-http.md`；扩展 `build_documents_router`；非快进合并 `module/M02-documents-lifecycle-http`（`7d4e8d9`）；tag `M02-v0.3.0`。
- **验证**（main，2026-09-07）：`python ops/run_grouped_tests.py --skip-web` → **197 passed, 2 skipped**；ruff / compileall 通过。
- **限制**：预览/下载未挂；无搜索/SSE/导出 HTTP；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：搜索 HTTP 或问答 SSE。

### 2026-09-07 — Wave 3 `/api/v1/documents` 合入 main

- **完成**：批准 `20260907-M11-api-v1-documents-mount.md`；M02 `build_documents_router`；M11 `create_app(documents=..., auth=...)` 注入挂载；非快进合并 `module/M02-documents-http`（`54a1026`）；tag `M02-v0.2.0`。
- **验证**（main，2026-09-07）：`python ops/run_grouped_tests.py --skip-web` → **189 passed, 2 skipped**；ruff / compileall 通过。
- **限制**：详情/重试/删除/预览/下载 HTTP 未挂；无搜索/SSE/导出 HTTP；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：文档详情/删除 HTTP，或搜索/问答 SSE。

### 2026-09-07 — Wave 3 `/api/v1/auth` 合入 main

- **完成**：批准 `20260907-M11-api-v1-auth-mount.md`；M01 `build_auth_router`；M11 `create_app(auth=...)` 注入挂载；非快进合并 `module/M01-auth-http`（`f0f4352`）；tag `M01-v0.2.0`。
- **验证**（main，2026-09-07）：`python ops/run_grouped_tests.py --skip-web` → **178 passed, 2 skipped**；ruff / compileall 通过。
- **限制**：改密/管理用户 HTTP 未挂；无文档/SSE/导出 HTTP；未打 `wave-3-integrated`；GATE-P0 全部 unverified。
- **下一步**：文档上传/列表 HTTP 或问答 SSE。

### 2026-09-07 — Wave 3 `/healthz` `/readyz` 合入 main

- **完成**：批准 `20260907-M11-fastapi-health-assembly.md`；M03 extra `http`；M11 `create_app()` 仅健康路由；非快进合并 `module/M11-wave3-health`（`646ab12`）；tag `M11-v0.2.2`。
- **验证**（main，2026-09-07，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / fastapi 0.141.1）：
  - `python ops/run_grouped_tests.py --skip-web` → **174 passed, 2 skipped**；
  - ruff / compileall 通过。
- **限制**：未挂 `/api/v1`；未打 `wave-3-integrated`；GATE-P0 全部 unverified；CI 不启动 uvicorn/Compose。
- **下一步**：`/api/v1` HTTP/SSE 装配（跨业务模块）。

### 2026-09-07 — Wave 3 依赖 Compose 切片合入 main

- **完成**：非快进合并 `module/M11-wave3-compose`（`c98b012`）；模块 tag `M11-v0.2.0`（四依赖 Compose）与 `M11-v0.2.1`（opt-in Alembic 冒烟）。
- **验证**（main，2026-09-07，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：
  - `python ops/run_grouped_tests.py --skip-web` → **168 passed, 2 skipped**（skip = postgres 未监听 / 未装 psycopg）；
  - ruff / compileall 通过。
- **限制**：未打 `wave-3-integrated`；无 FastAPI `/healthz`；CI 不启动 Compose；GATE-P0 全部 unverified；未冻结 TBD-P0。
- **下一步**：审核 FastAPI 健康端点变更申请；本机 Docker 可用时跑 `ops/smoke_postgres_alembic.py`。

### 2026-09-07 — Wave 2 退出评审与 `wave-2-integrated`

- **完成**：非快进合并 M10 → M09 → M11；适配 M09 删除装配页后的后台路由断言；将前台/后台 Fake E2E 与 typecheck/lint 接入 `ops/run_grouped_tests.py`。
- **合并**：`39ede47` merge(M10)、`e16c3cd` merge(M09)、`f242341` merge(M11)；模块 tag `M09/M10/M11-v0.1.0` 已存在。
- **验证**（main，2026-09-07，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / Node v24.15.0 / Next 14.2.15）：
  - `python ops/run_grouped_tests.py --skip-web` → **165 passed**（M01 27 + M02 15 + M04 10 + M05 12 + M06 26 + M07 7 + Wave 0 60 + M11 8）；ruff / compileall 通过；
  - `npm --prefix web test` → **9 passed**；
  - `npx tsx ../tests/e2e/user/test_user_web.mjs`（cwd=`web/`）→ **12 passed**；
  - `npx tsx ../tests/e2e/admin/test_admin_web.mjs`（cwd=`web/`）→ **8 passed**；
  - `npm --prefix web run typecheck` / `lint` → 通过。
- **退出条件核对**（`MODULE_SPEC.md` §4.4）：
  - M09/M10 十页与首批 Fake E2E 合入；
  - M11 分组 CI 与 Fake 领域链路合入，**未**写入可启动 Compose/FastAPI/Celery；
  - 矩阵回填页面层 `implemented`（不标 `verified`）；
  - 八项 GATE-P0 仍见 `evidence/wave2-m11/limits.md`，全部 unverified。
- **限制/不通过项**：无 HTTP/SSE 传输；Worker 非 Celery；未连接 PG/MinIO/Qdrant/Redis；无 Playwright；全部 `TBD-P0` 与 GATE-P0 仍未冻结/验证。
- **基线**：文档提交后创建 `wave-2-integrated`。

### 2026-09-06 — Wave 1 退出评审与 `wave-1-integrated`

- **完成**：按 DAG 非快进合并 M01 → M02 → M07 → M04 → M05 → M06；补齐 `M01/M02/M04/M05/M07-v0.1.0`；批准 M06 观测包 `__init__.py`；依赖类变更申请暂缓写入 pyproject。
- **验证**（main，2026-09-06，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：
  - M01 `tests/unit/auth tests/security/auth` → **27 passed**；
  - M02 `tests/unit/documents` → **15 passed**；
  - M04 `tests/unit/retrieval tests/security/retrieval` → **10 passed**；
  - M05 `tests/unit/qa tests/unit/runs tests/contract/stream` → **12 passed**；
  - M06 `tests/unit/exports tests/unit/audit tests/security/export` → **26 passed**；
  - M07 `tests/unit/worker` → **7 passed**；
  - Wave 0：`tests/integration/db` **12** + `tests/contract --ignore stream` **48** → **60 passed**；
  - 合计领域+回归 **157 passed**（因各模块 `fakes.py` 同名，分组执行而非单进程收集）；
  - ruff check / compileall 覆盖 Wave 1 Python 包 → 通过。
- **退出条件核对**（`MODULE_SPEC.md` §4.3）：
  - 六模块单元/契约测试通过；
  - 模块 tag `M01–M07-v0.1.0` 齐全；
  - M00 追踪矩阵已回填单元层 `implemented`（不标 `verified`）；
  - M11 可装配单元/契约 fixture（无 Compose/真实存储，属 Wave 2/3）。
- **限制/不通过项**：无 HTTP/SSE 传输；Worker 非 Celery；解析器非 PyMuPDF 全家桶；未连接 PG/MinIO/Qdrant/Redis；`argon2-cffi` 仅本地 venv；全部 `TBD-P0` 与 GATE-P0 仍未冻结/验证。
- **基线**：合并终点 `db42789`；文档提交后创建 `wave-1-integrated`。

### 2026-09-06 — Wave 0 退出评审与 `wave-0-integrated`

- **完成**：非快进合并 `module/M08-web-foundation`（`1181e28`）；批准三项所有权变更并写入 `MODULE_SPEC.md`；创建 `wave-0-integrated`。
- **验证**（main，2026-09-06）：
  - `pytest tests/integration/db tests/contract -q` → **60 passed**（M03 12 + M00 48）；
  - `npm --prefix web ci && npm --prefix web test` → **9 passed**；
  - `npm --prefix web run typecheck`、`npm --prefix web run lint` → 通过。
- **退出条件核对**：
  - `contract-v0.1` 已冻结（OpenAPI/SSE/Worker + 48 项契约测试）；
  - 数据 adapter 协议已冻结（Repository/UoW、Object/Vector/Queue/Cache ports）；
  - Web API/SSE client 输入已冻结（`/api/v1`、错误包、SSE 事件白名单、`Last-Event-ID`）；
  - 公共路径所有权无歧义（三项变更申请已写入 MODULE_SPEC）；
  - M00/M03/M08 均有进度文件、模块 tag 与测试证据。
- **限制/不通过项**：未连接真实 PostgreSQL/MinIO/Qdrant/Redis；无浏览器 E2E；`web/app/page.tsx` 为装配页，M09 必须替换；`npm audit` 报告 Next 14.2.15 传递依赖漏洞，不在 Wave 0 静默升级；全部 `TBD-P0` 与 GATE-P0 仍未冻结/验证。
- **基线**：M08 模块提交 `2fac277`、标签 `M08-v0.1.0`；Wave 0 标签 `wave-0-integrated`。

### 2026-09-06 — M00 contract-v0.1 集成

- **完成**：合并 `module/M00-contracts`（merge commit 由本集成会话产生）；集成 OpenAPI、SSE、Worker schema、六组 Gherkin、验收矩阵及 48 项契约测试。
- **验证**：主分支运行 `tests/contract` → **48 passed**；M00 tags：`contract-v0.1`、`M00-v0.1.0`。
- **前置**：Wave 0 尚未完成，`wave-0-integrated` 需等待 M03/M08 交付后再创建。

### 2026-09-06 — M03 数据基础集成

- **完成**：以非快进方式合并 `module/M03-data`，集成 SQLAlchemy 模型、Alembic 初始迁移、UnitOfWork、Repository/存储端口、opaque ID/UTC 工具和审计追加写保护。
- **验证**：在 M03 worktree 环境运行 `tests/integration/db tests/contract` → **60 passed**；Ruff check 与 compileall 均通过。
- **限制**：尚未连接真实 PostgreSQL/MinIO/Qdrant/Redis；PostgreSQL 权限、partial index、审计触发器由 M11 后续验证。
- **基线**：M03 模块提交 `9a8e851`、标签 `M03-v0.1.0`；本次集成提交为当前 main HEAD。

### 2026-09-06 — MODULE-SPEC-1.0 建立

- **完成**：创建 `MODULE_SPEC.md`、`AGENTS.md`、本进度文档和 `progress/modules/` 模板；定义 M00–M11、依赖 DAG、Wave 0–3、文件 Owner、worktree、交接和门禁协议。
- **文档治理**：按用户确认，保留工作区对 `问枢Pivot-技术方案V2.md`、`问枢Pivot.txt` 的删除，并在 README 中说明历史可从 Git 恢复；不修改历史规格内容。
- **验证**：待文档链接、覆盖范围和 Git 差异检查；完成后创建 `module-spec-v1.0` 标签。
- **下一步**：选择 M00/M03/M08 中一个 Wave 0 模块，创建独立 worktree，先完成 DoR 和 Red/Contract 工作。
- **风险**：模块并行前必须先提交并冻结本基线；契约、数据库迁移、共享组件和根进度不可由多个会话并发修改。

## 7. TBD-P0 与 ADR 提醒

不要在本文件或模块进度中把以下内容伪装成已冻结事实：登录限流、上传资源限制、分块/检索/RRF/rerank 参数、超时/token/并发预算、分页、质量阈值、保留期限、RPO/RTO 等。任何改变状态机、权限、引用/删除语义、模型或检索配置的提案，都必须关联 SPEC 附录 E 的 ADR。
