# 问枢 Pivot 开发进度

> **进度文档不是需求源**：需求以 [`SPEC.md`](SPEC.md) 为准，模块边界以 [`MODULE_SPEC.md`](MODULE_SPEC.md) 为准。  
> **最后更新**：2026-09-07  
> **当前状态**：Wave 3 进行中；依赖 Compose fixture 已合入 main。波次基线仍为 `wave-2-integrated`（未打 `wave-3-integrated`）。
> **当前基线**：`wave-2-integrated` + Compose `c98b012` + 健康端点 `646ab12` + 认证 HTTP `f0f4352` + 文档 HTTP `7d4e8d9`。

## 1. 新会话恢复入口

1. 读取 `AGENTS.md`；
2. 读取 `MODULE_SPEC.md`；
3. 读取本文件和对应的 `progress/modules/Mxx.md`；
4. 用 `git log --oneline --decorate -20`、`git worktree list` 确认实际基线；
5. 只有满足模块 DoR 后，才在对应 `module/Mxx-*` worktree 开发。

如果没有指定模块：继续 **Wave 3**。`/api/v1/auth` 与文档上传/列表/详情/版本/重试/删除 HTTP 已在 main；下一刀是搜索/问答 SSE 或导出 HTTP。不要冻结 `TBD-P0`，不要把 HTTP 装配标成 GATE verified。

## 2. 当前波次与模块状态

状态枚举：`planned` → `claimed` → `in_progress` → `blocked` → `review` → `integrated`；只有集成会话可将模块标记为 `integrated`。

| 模块 | 状态 | 分支/worktree | 会话/Owner | 基线契约 | 最近证据 | 下一步 |
|---|---|---|---|---|---|---|
| M00 契约治理 | integrated | `module/M00-contracts` / `../Pivot-M00-contracts` | 本会话已集成 | `contract-v0.1` | `tests/contract`: 48 passed | 已完成契约、场景、矩阵；依赖模块开始消费 |
| M01 身份授权 | integrated | `module/M01-auth-http` / `../Pivot-M01-auth-http` | 本集成会话 | `contract-v0.1` | 27 单元 + HTTP 登录/刷新/退出；tag `M01-v0.2.0` | 改密/管理用户 HTTP 与限流 TBD-P0 仍待 |
| M02 文档接入 | integrated | `module/M02-documents-lifecycle-http` / `../Pivot-M02-documents-lifecycle-http` | 本集成会话 | `contract-v0.1` | 21 单元 + 上传/列表/详情/重试/删除 HTTP；tag `M02-v0.3.0` | 预览/下载 HTTP 仍待 |
| M03 数据基础 | integrated | `module/M03-data` / `../Pivot-M03-data` | 本集成会话 | `contract-v0.1` | M03 12 + M00 48 tests passed；Ruff/compile 通过 | PostgreSQL/外部存储集成待 M11 验证 |
| M04 检索 RAG | integrated | `module/M04-retrieval` / `../Pivot-M04-retrieval` | 本集成会话 | `contract-v0.1` | 10 passed；tag `M04-v0.1.0` | 真实 dense/BM25/rerank 与 Golden Set 待后续 |
| M05 QA/Run/SSE | integrated | `module/M05-qa-stream` / `../Pivot-M05-qa-stream` | 本集成会话 | `contract-v0.1` | 12 passed；tag `M05-v0.1.0` | HTTP/SSE 传输与 LangGraph extra 待后续 |
| M06 导出/审计 | integrated | `module/M06-export-audit` / `../Pivot-M06-export-audit` | 本集成会话 | `contract-v0.1` | 26 passed；tag `M06-v0.1.0` | 导出 HTTP 与 PG/MinIO 持久化待后续 |
| M07 Worker/解析/索引 | integrated | `module/M07-worker` / `../Pivot-M07-worker` | 本集成会话 | `contract-v0.1` | 7 passed；tag `M07-v0.1.0` | Celery/真实解析库待依赖审核 |
| M08 Web 基础 | integrated | `module/M08-web-foundation` / `../Pivot-M08-web-foundation` | 本集成会话 | `contract-v0.1` | M08 9 tests + typecheck/lint 通过 | 共享组件已被 M09/M10 消费 |
| M09 员工前台 | integrated | `module/M09-user-web` / `../Pivot-M09-user-web` | 本集成会话 | `wave-1-integrated` | 12 passed；tag `M09-v0.1.0` | Playwright / FastAPI HTTP 待 Wave 3 |
| M10 管理后台 | integrated | `module/M10-admin-web` / `../Pivot-M10-admin-web` | 本集成会话 | `wave-1-integrated` | 8 passed；tag `M10-v0.1.0` | Playwright / FastAPI HTTP 待 Wave 3 |
| M11 集成/质量/运维 | in_progress | `module/M02-documents-lifecycle-http`（挂载） | 本集成会话 | `wave-2-integrated` | 分组 Python 197 passed / 2 skipped | 搜索/SSE/导出 HTTP、Playwright、GATE-P0 仍待 |

模块详细状态由各自 `progress/modules/Mxx.md` 维护；模块会话不要并发编辑本表。

## 3. 需求追踪摘要

完整映射和 Accountable/Contributors 见 [`MODULE_SPEC.md §8`](MODULE_SPEC.md#8-需求-accountable-映射)。验收链必须遵循：需求 ID → 场景 ID → 契约/数据 → 测试 ID → 验收证据 → verified。

| 需求范围 | Accountable | 测试/场景入口 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| FR-AUTH-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/`、`tests/integration/pipeline/test_FR_AUTH_001_http_login.py` | implemented | 27 项单元/安全 + `/api/v1/auth` 登录/刷新/退出 HTTP；改密 HTTP 未挂 |
| FR-RBAC-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/`、`spec/scenarios/auth.feature` | implemented | 资源四重授权与会话隔离负向测试通过 |
| FR-DOC-001~008 | M02 | `tests/unit/documents/`、`tests/integration/pipeline/test_FR_DOC_001_http_upload.py`、`tests/integration/pipeline/test_FR_DOC_007_http_lifecycle.py` | implemented | 21 项 M02 单元 + 文档上传/列表/详情/版本/重试/删除 HTTP；无预览/下载 / 真实 MinIO |
| FR-SEARCH-001~002 / FR-RAG-001~006 | M04 | `tests/unit/retrieval/`、`tests/security/retrieval/` | implemented | 10 项 M04 测试通过；dense/BM25 为 Fake |
| FR-QA-001~006 / FR-STREAM-001~005 | M05 | `tests/unit/qa/`、`tests/unit/runs/`、`tests/contract/stream/` | implemented | 12 项 M05 测试通过；SSE 为内存 EventLog |
| FR-EXPORT-001~003 / FR-AUDIT-001~003 | M06 | `tests/unit/exports/`、`tests/unit/audit/`、`tests/security/export/` | implemented | 26 项 M06 测试通过；内存审计/导出存储 |
| §2 存储不变量 | M03 | `tests/integration/db/`、`api/src/pivot/db/`、`migrations/` | implemented | M03 12 项测试 + 48 项 M00 契约回归通过；Compose Postgres Alembic 冒烟为 opt-in skip |
| §6 解析/分块/索引执行 | M07 | `tests/unit/worker/` | implemented | 7 项 M07 测试通过；stdlib/Fake Embedding，非 Celery |
| §1.5 / NFR-UX 设计系统与 client | M08 | `tests/e2e/fixtures/web/test-foundation.mjs` | implemented | M08 9 项基础测试通过；产品页由 M09/M10 接管 |
| 前台 6 页 | M09 | `tests/e2e/user/test_user_web.mjs` | implemented | 12 项 Fake fetch 测试通过；无 Playwright |
| 后台 4 页 | M10 | `tests/e2e/admin/test_admin_web.mjs` | implemented | 8 项 Fake fetch 测试通过；无 Playwright |
| NFR-CAP/PERF/OBS/DR、GATE-P0-001~008 | M11 | `tests/integration/pipeline/`、`tests/security/ops/`、`tests/performance/`、`evidence/wave2-m11/`、`evidence/wave3-m11/` | implemented（CI/Fake + Compose + health + auth/documents HTTP）；GATE-P0 unverified | TestClient；无搜索/SSE/导出 HTTP；CI 不启动 Compose |

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

### Wave 3 — P0/P1 门禁（进行中）

- [x] 依赖 Compose fixture：postgres / minio / qdrant / redis（钉镜像 + healthcheck + localhost；`M11-v0.2.0`）
- [x] Compose Postgres 的 opt-in Alembic 冒烟（默认 skip；`M11-v0.2.1`）
- [x] 应用 `/healthz` `/readyz`（TestClient 薄装配，`M11-v0.2.2`）
- [x] `/api/v1/auth/login|refresh|logout`（`M01-v0.2.0`）
- [x] `GET/POST /api/v1/documents`（`M02-v0.2.0`）
- [x] 文档详情/版本/重试/删除 HTTP（`M02-v0.3.0`）
- [ ] 搜索/问答 SSE/导出 HTTP、预览/下载；Playwright、Golden Set、5 并发 / 100k Chunk、新 ECS 备份恢复
- [ ] 任一 `GATE-P0-*` verified；未打 `wave-3-integrated`

## 5. 未完成项与已知差距

- [x] Wave 0 基础已存在：`api/` 数据端口、`web/` 设计系统与 client；
- [x] Wave 1 领域服务已存在：auth/documents/retrieval/qa/runs/stream/exports/audit/parsing/chunking 与 `worker/`（Fake/stdlib）；
- [x] `spec/contracts/`、`spec/scenarios/`、`spec/acceptance/matrix.md` 已由 M00 建立；Golden Set 和真实供应商 Fake 仍待 M11；
- [x] `tests/` 已有 M00 契约 48、M03 数据 12、M08 基础 9、Wave 1 领域 97、M09 12、M10 8、M11 pipeline/ops/perf（合入后 34 passed / 2 skipped）；
- [x] 分组 CI（`.github/workflows/ci.yml` + `ops/run_grouped_tests.py`）已装配，不启动 Compose；
- [x] `docker-compose.yml` 依赖 fixture 已合入 main（postgres/minio/qdrant/redis）；CI **不得** `up`；本机未实测拉起；
- [x] FastAPI 健康装配：`GET /healthz`、`GET /readyz`（探测注入，失败闭环）；optional extra `http`；
- [x] FastAPI `/api/v1/auth/login|refresh|logout`（注入 AuthService 才挂载；HttpOnly refresh Cookie）；
- [x] FastAPI `GET/POST /api/v1/documents`（同时注入 DocumentService 与 AuthService 才挂载）；
- [x] FastAPI 文档详情/版本/重试/删除（`/documents/{id}` 及 `/versions|/retry|/delete`）；
- [ ] 无预览/下载、搜索/问答/SSE/导出 HTTP；无 Celery；无 api/worker/web Compose 服务；
- [ ] PostgreSQL/Qdrant/MinIO/Redis **客户端适配**尚未建立；真实 PG Alembic 冒烟因无 Docker/psycopg 为 skip；
- [ ] 所有 `TBD-P0` 均未冻结，禁止模块自行填默认值；
- [ ] P0 八项门槛均未验证；
- [x] Wave 0 三项变更申请已批准：`20260906-M00-contract-test-path.md`、`20260906-M03-ownership-clarification.md`、`20260906-M08-web-scaffold-ownership.md`。
- [x] Wave 1 观测包变更已批准：`20260906-M06-observability-package-init.md`。
- [ ] Wave 1 依赖变更暂缓写入 pyproject：`20260906-M01-auth-dependencies.md`、`20260906-M05-langgraph.md`、`20260906-M07-worker-dependencies.md`。
- [x] Wave 3 FastAPI 健康端点已批准并合入：`20260907-M11-fastapi-health-assembly.md`。
- [x] Wave 3 认证 HTTP 挂载已批准并合入：`20260907-M11-api-v1-auth-mount.md`。
- [x] Wave 3 文档上传/列表 HTTP 挂载已批准并合入：`20260907-M11-api-v1-documents-mount.md`。
- [x] Wave 3 文档详情/版本/重试/删除 HTTP 已批准并合入：`20260907-M02-documents-lifecycle-http.md`。

## 6. 轮次日志

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
