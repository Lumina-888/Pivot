# 问枢 Pivot 后续工单

> 配套 [`next-dev-spec.md`](next-dev-spec.md)。需求源仍是 [`SPEC.md`](../SPEC.md)。  
> **基线**：`main` @ `e06a869` / `M11-v0.16.0`。  
> 状态：`ready` → `blocked` → `done`。本文件开写时除特别注明外均为 `ready` 或 `blocked`。

图例：`S` 约 1 个主线切片；`M` 约 2–3 切片；`L` 多会话或必须人工/受控环境。

---

## 总表

| ID | 标题 | 阶段 | 规模 | Accountable | SPEC | 依赖 | 状态 |
|---|---|---|---|---|---|---|---|
| ND-W3-01 | worker 装配 Qdrant IndexPublisher | A1 | S | M07 | FR-DOC-006, FR-RAG-001 | 无 | ready |
| ND-W3-02 | Compose api 注入 `PIVOT_INGEST=celery` | A1 | S | M11 | FR-DOC-005, NFR-OBS | ND-W3-01 建议先 | ready |
| ND-W3-12 | Compose api/worker 注入 Qdrant/Redis | A1 | S | M11 | §2.1, NFR-OBS | ND-W3-01 | ready |
| ND-W3-03 | 真实解析库 extra（PyMuPDF/docx/pptx/xlsx） | A3 | M | M07 | FR-DOC-004, §6.1 | `20260906-M07-worker-dependencies.md` | ready |
| ND-W3-04 | 导出任务 PostgreSQL 持久化 | A2 | S | M06 | FR-EXPORT-001 | 无 | ready |
| ND-W3-05 | 会话/refresh 跨进程存储 | A2 | M | M01/M05 | FR-AUTH-001, FR-RBAC-002 | 无 | ready |
| ND-W3-06 | 登录限流缺省接到 Redis（仍不冻阈值） | A2 | S | M01 | FR-AUTH-002 | ND-W3-12 | ready |
| ND-W3-07 | PATCH 角色 / 重置密码 HTTP | A2 | S | M01 | FR-AUTH-003 | 无 | ready |
| ND-W3-08 | SSE 长连接推送与缓冲 | A3 | M | M05/M08 | FR-STREAM-001~003 | 无 | ready |
| ND-W3-09 | LangGraph extra（原暂缓变更） | A3 | M | M05 | FR-QA-001 | `20260906-M05-langgraph.md` | blocked |
| ND-W3-10 | Playwright 十页 opt-in | A3/C | M | M09/M10/M11 | NFR-UX, GATE-P1 | ND-W3-02 建议 | ready |
| ND-W3-11 | version.idempotency_key 入库 | A2 | S | M03/M02 | FR-DOC-005 | 需变更申请；SPEC 字段确认 | blocked |
| ND-W3-13 | Wave 3 收口评审 / tag | A | S | M11 | — | A1 完成 | blocked |
| ND-P0-01 | 企业人工标注 Golden Set | B1 | L | 业务/M04/M11 | GATE-P0-002, NFR-QUAL | 人 | ready |
| ND-STG-01 | ingest 与检索共用注入 HTTP Embedding | STG | S | M07/M04 | FR-RAG-001, FR-DOC-006 | ND-W3-01 | ready |
| ND-STG-02 | Deepseek-Flash Draft Writer 适配器 | STG | M | M05 | FR-QA-001/002, DR-007 | ND-STG-01 | ready |
| ND-STG-03 | MinerU 云 API 解析器（staging） | STG | M | M07 | §6.1 V2 | ND-W3-01 | ready |
| ND-STG-04 | 阿里云 4C8G Compose 部署 | STG | M | M11 | NFR-OBS | A1+STG-01~03 | blocked |
| ND-P0-02 | 外发/留存/训练审批 | B1 | L | 法务/安全 | GATE-P0-001, DR-001 | 人 | deferred（企业化；staging 不挡） |
| ND-P0-03 | live Embedding/rerank 冒烟 | B1/STG | S | M04 | FR-RAG-001, GATE-P0-002 | 密钥（staging 不挡在 ND-P0-02） | ready |
| ND-P0-04 | Verifier 阈值与盲评 | B1 | L | 算法/M05 | GATE-P0-004, DR-004 | ND-P0-01 | blocked |
| ND-P0-05 | 共享库准入规则 | B1 | S | 业务 | DR-005, FR-RBAC-004 | 人 | ready |
| ND-P0-06 | 真实存储一致性与原子发布环境 | B2 | L | M02/M07/M11 | GATE-P0-003 | ND-W3-01, ND-W3-02, Compose 真跑 | blocked |
| ND-P0-07 | 上线传输/审计/密钥安全验证 | B2 | M | M01/M11 | GATE-P0-005 | HTTPS 拓扑 | blocked |
| ND-P0-08 | 加密 OSS + 新 ECS 备份恢复 | B3 | L | M11 | GATE-P0-006, NFR-DR, DR-003 | 新 ECS | blocked |
| ND-P0-09 | 5 并发 / 100k / P95 峰值 | B3 | L | M11 | GATE-P0-007, NFR-CAP/PERF | 新 ECS | blocked |
| ND-P0-10 | 冻结 TBD-P0 参数包 | B | L | Owner 按附录 E | 各 TBD-P0 | 实测报告 | blocked |
| ND-P0-11 | 固定版本发布、健康门禁、回滚 | B3 | L | M11 | GATE-P0-008 | 镜像仓库/Runbook | blocked |
| ND-P1-01 | P1 进入检查 | C | S | M00/M11 | §12.3 | 八项 verified | blocked |
| ND-P1-02 | 10 页真实系统矩阵 | C | L | M09/M10/M11 | GATE-P1, §12.3 退出 | ND-P1-01 | blocked |

---

## Phase A — Wave 3 工程票

### ND-W3-01 worker 装配 Qdrant IndexPublisher

- **规模 / Owner**：S / M07（M11 注入，M04 只消费检索端口）
- **映射**：`FR-DOC-006`、`FR-RAG-001`、§6.2
- **为什么**：HTTP ingest 在 `PIVOT_VECTOR_STORE=qdrant` 时可 upsert；Compose worker 只接了 PG/MinIO，发布仍可能停在进程内 IndexPublisher，API 检索看不见 worker 产物。
- **范围**：
  - `assemble_ingest_runtime` 在 `PIVOT_VECTOR_STORE=qdrant` 时装配 `IndexPublisher` + 同一 embedding 维数注入；
  - Compose worker 注入 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*`（`${}`，不写死 URL）；
  - CI Fake Qdrant client；缺 endpoint/collection 失败闭环。
- **不做**：不冻维数/距离；不标 GATE-P0-002/003 verified；不改 HTTP 缺省 sync。
- **测试**：`test_FR_DOC_006_worker_qdrant_publish_*`、`test_NFR_OBS_compose_worker_injects_qdrant_*`、`test_GATE_P0_002_not_verified_by_worker_qdrant`。
- **DoD**：worker 装配可写入与 API 相同的 VectorStore 端口；分组回归绿；证据写明 Fake client。

### ND-W3-02 Compose api 注入 `PIVOT_INGEST=celery`

- **规模 / Owner**：S / M11（M07 只消费既有 submitter）
- **映射**：`FR-DOC-005`、NFR-OBS、§9.1
- **为什么**：api 与 worker 已共享 PG/MinIO，但 HTTP 缺省仍请求内 ingest；Compose 上 worker 听队列却收不到生产路径任务。
- **范围**：
  - Compose api 注入 `PIVOT_INGEST` / 队列名 / concurrency / `PIVOT_CELERY_BROKER`（`${}`）；
  - example 给 celery 占位，标明不是冻 TBD-P0；
  - 进程外 `assemble_runtime` 缺省仍 `sync`。
- **不做**：CI 不 up；不把 eager 当生产队列；不标 GATE-P0-003 verified。
- **测试**：`test_NFR_OBS_compose_api_injects_celery_ingest_*`、`test_FR_DOC_001_http_celery_envelope_stays_uploaded`（已有，保持）。
- **DoD**：yml 不写死 `redis://`；缺变量失败闭环；HTTP 非 Compose 缺省仍 sync。

### ND-W3-12 Compose 注入 Qdrant/Redis（api+worker）

- **规模 / Owner**：S / M11
- **映射**：§2.1、NFR-OBS
- **依赖**：ND-W3-01
- **范围**：api/worker 注入 `PIVOT_VECTOR_STORE` / Qdrant / `PIVOT_CACHE_STORE` / `PIVOT_QUEUE_STORE` / Redis endpoint（`${}`）。vector/cache 仍允许 memory，但 app profile example 写明 fixture 值。
- **不做**：不冻距离/TTL；不把 Redis 当业务事实源。
- **测试**：`test_NFR_OBS_compose_api_injects_qdrant_redis_*`。

### ND-W3-03 真实解析库 extra

- **规模 / Owner**：M / M07（依赖锁 M03/M11）
- **映射**：`FR-DOC-004`、SPEC §6.1
- **依赖**：落实 `20260906-M07-worker-dependencies.md`（Celery extra 已做，解析库仍暂缓）
- **范围**：`worker` optional extra：PyMuPDF/python-docx/python-pptx/openpyxl；解析注册表可切换；CI 默认仍走 stdlib/启发式夹具或受控 fixture 文件（非企业文档）。
- **不做**：不提交企业 PDF；不冻页数/大小；扫描件 OCR 属 P2。
- **测试**：`test_FR_DOC_004_*` 扩展真实库夹具；失败码仍走既有契约。

### ND-W3-04 导出任务 PostgreSQL 持久化

- **规模 / Owner**：S / M06（M03 端口，M11 装配）
- **映射**：`FR-EXPORT-001~003`、`FR-AUDIT-001`
- **范围**：ExportTask 走 SQLAlchemy；跨装配可见状态；对象仍 MinIO；公开 URL 仍 `PublicDownloadSigner`。
- **不做**：不新增「直接下发 MinIO 字节」的破坏性 HTTP（契约仅短时 `download_url`）；不冻 TTL。
- **测试**：`test_FR_EXPORT_001_postgres_task_survives_assembly`、`test_FR_EXPORT_001_download_url_does_not_leak_minio`。

### ND-W3-05 会话 / refresh 跨进程存储

- **规模 / Owner**：M / M01（refresh）+ M05（conversation/run 若仍内存）
- **映射**：`FR-AUTH-001`、`FR-RBAC-002`、FR-STREAM
- **范围**：refresh 与会话/Run 在 `PIVOT_STORAGE=postgres` 时跨 api 实例存活；多 worker/api 不丢登录态。
- **不做**：不把 Redis 当会话事实源（SPEC：Redis 非业务事实）。
- **测试**：`test_FR_AUTH_001_refresh_survives_new_assembly`、`test_FR_RBAC_002_conversation_survives_new_assembly`。

### ND-W3-06 登录限流缺省接到 Redis

- **规模 / Owner**：S / M01
- **映射**：`FR-AUTH-002`
- **依赖**：ND-W3-12（Compose 有 Redis）
- **范围**：Compose 同时注入阈值/窗口 **或** 保持「两者都缺则永不锁定」。禁止在代码里写死次数。
- **不做**：不冻 TBD-P0 阈值；失败仍统一 `AUTH_INVALID_CREDENTIALS`。
- **测试**：沿用 `test_FR_AUTH_002_http_login_rate.py`；新增 compose 注入断言。

### ND-W3-07 PATCH 角色 / 重置密码 HTTP

- **规模 / Owner**：S / M01
- **映射**：`FR-AUTH-003`、契约 admin users
- **范围**：`PATCH /admin/users/{id}` 支持契约已有角色/重置字段；初始密码不进审计；权限仅 admin。
- **不做**：不把 `must_change_password` 塞进 User 表（非 SPEC §2.2 字段，见既有 M03 结论）。
- **测试**：`test_FR_AUTH_003_http_admin_patch_role_*`、`test_FR_AUTH_003_http_reset_password_*`。

### ND-W3-08 SSE 长连接与缓冲

- **规模 / Owner**：M / M05（M08 client）
- **映射**：`FR-STREAM-001~003`
- **范围**：uvicorn 长连接推送；Last-Event-ID 补发保持；前端缓冲。
- **不做**：不冻超时；不在事件里带思考链/Prompt。
- **测试**：契约已有重连用例；补 opt-in 集成，CI 默认 skip 长连接。

### ND-W3-09 LangGraph extra

- **状态**：blocked（`20260906-M05-langgraph.md` 仍暂缓）
- **规模 / Owner**：M / M05
- **映射**：`FR-QA-001`
- **范围**：optional extra；主图语义不变；缺 extra 失败闭环或走现有确定性编排。
- **先决**：单独再批变更申请，不在本票偷偷加依赖。

### ND-W3-10 Playwright 十页 opt-in

- **规模 / Owner**：M / M09+M10，M11 装配
- **映射**：NFR-UX、§12.3 P1 退出（10 页）
- **范围**：`PIVOT_REQUIRE_PLAYWRIGHT=1` 覆盖前台 6 + 后台 4；CI 默认 skip。
- **不做**：不把 Fake fetch 当浏览器证据；不标 GATE-P0-005 verified。

### ND-W3-11 version.idempotency_key 入库

- **状态**：blocked
- **原因**：M03 已记录「本切片不新增列」。若契约/幂等跨进程必须落库，先写 `progress/changes/` + 迁移，确认 SPEC §2.2 / 附录是否要求该列。
- **不做**：不在未批变更时加列。

### ND-W3-13 Wave 3 收口评审

- **状态**：blocked until A1（至少 ND-W3-01 + ND-W3-02）完成
- **Owner**：M11
- **DoD**：分组回归绿；更新矩阵；证据写明 **全部 GATE-P0 仍 unverified**；tag `wave-3-integrated` 仅表示夹具收口，不等于 P0 通过。

---

## Phase B — P0 闸门票（人 / 受控环境）

### ND-P0-01 企业人工标注 Golden Set

- **规模**：L（人工）
- **映射**：GATE-P0-002、NFR-QUAL-001~012、§10.8
- **范围**：真实/脱敏企业问句 + 期望文档/Citation；版本化；禁止把 v0.2-synthetic 改名成企业集。
- **DoD**：标注规范、条数与分层、评测脚本入口；阈值仍等 ND-P0-10。

### ND-P0-02 外发/留存/训练审批

- **状态**：deferred for `dev-staging`；企业化部署前必须重开
- **映射**：GATE-P0-001、DR-001
- **staging**：规章制度等低敏测试文档 + 注入外部 API 不挡。仍禁止企业合同/人事材料。
- **产物（企业化）**：审批记录（区域、留存、不训练、删除）。

### ND-P0-03 live Embedding / rerank 冒烟

- **状态**：ready（staging 用 Owner 注入的密钥；CI 仍 Fake）
- **映射**：FR-RAG-001、GATE-P0-002
- **范围**：opt-in 环境变量；CI 默认 skip；不提交 URL/密钥。可与 ND-STG-01 同一切片。
- **不做**：不标 GATE verified（冒烟 ≠ 评测通过）。

### ND-P0-04 Verifier 阈值与模型盲评

- **映射**：GATE-P0-004、DR-004、FR-QA-004~006
- **产物**：评测报告；阈值写入 SPEC/ADR 后才能当默认。

### ND-P0-05 共享库准入规则

- **映射**：DR-005、FR-RBAC-004
- **产物**：仅低敏全员文档的业务规则；代码已有 `shared_visible`，缺的是业务确认。

### ND-P0-06 真实一致性环境

- **映射**：GATE-P0-003
- **依赖**：ND-W3-01/02 + 可运行的 Compose/ECS
- **产物**：上传/重试/删除/索引代次在真实 PG+MinIO+Qdrant+Celery 上的原子发布报告。sqlite/Fake 不算。

### ND-P0-07 上线安全验证

- **映射**：GATE-P0-005、NFR-SEC
- **产物**：HTTPS/Cookie、RBAC 越权、上传隔离、日志脱敏、密钥扫描的上线清单。opt-in Playwright 登录不够。

### ND-P0-08 加密备份与新 ECS 恢复

- **映射**：GATE-P0-006、NFR-DR-001/002、DR-003
- **产物**：加密 OSS 备份、独立账号、恢复演练日志、实测 RPO/RTO。进程内 roundtrip 不算。

### ND-P0-09 容量与 P95

- **映射**：GATE-P0-007、NFR-CAP-004/005、NFR-PERF-*
- **产物**：5 并发解析/检索、100k Chunk、资源峰值、P95。opt-in Fake 100k 不算。

### ND-P0-10 冻结 TBD-P0 参数包

- **映射**：SPEC 全文 `TBD-P0`、附录 E
- **做法**：每项一份实测/ADR，回写 SPEC，再改夹具。禁止在业务代码里先写死再补文档。

### ND-P0-11 固定版本、发布、回滚

- **映射**：GATE-P0-008、NFR-OBS
- **产物**：不可变镜像 tag、健康门禁、回滚 Runbook、一次演练记录。Compose fixture pin ≠ 本票。

---

## Phase C — P1

### ND-P1-01 P1 进入检查

- **依赖**：GATE-P0-001~008 均为 verified
- **检查**：准入规则生效；`contract-v0.1`（或已升版本）冻结；TDD/Fixture 仍在。

### ND-P1-02 10 页真实系统矩阵

- **映射**：SPEC §12.3 退出、GATE-P1-001~004（SPEC 仅索引，细则以当时 SPEC 为准）
- **范围**：前台 6 + 后台 4 真实后端；功能/安全/性能/可靠性/灾备矩阵；低敏内测可回放。

---

## Phase STG — 开发调试环境（非生产上线）

范围：[`changes/20260910-M00-dev-staging-scope.md`](changes/20260910-M00-dev-staging-scope.md)。

### ND-STG-01 ingest 与检索共用 HTTP Embedding

- **依赖**：ND-W3-01（worker 已能接 VectorStore）
- **范围**：`PIVOT_EMBEDDING=http` 时 ingest 与 query 用同一注入 embedder（硅基 `BAAI/bge-m3` 与现有 OpenAI embeddings 形状兼容）；维数仍注入不写死；失败不 published。Rerank 硅基 `BAAI/bge-reranker-v2-m3` 与现有 `/rerank` 适配器兼容，本票可顺带接到 worker/runtime。
- **不做**：不冻模型名/维数。

### ND-STG-02 Deepseek-Flash Draft Writer

- **范围**：注入 endpoint/model/api_key 的 HTTP Writer，替换证据拼接；Citation 仍必须落在检索候选；`external_llm_allowed` 为 false 不得外发；失败闭环（超时/429→既有错误码）。
- **不做**：不写死 DeepSeek/硅基 URL；CI Fake transport；不把 LangGraph 绑死本票。
- **Owner 已给**：主模型 `deepseek-flash`；备用 `mimo-v2.5`。实现时以控制台完整 model 字符串注入（硅基可能带 `deepseek-ai/` 前缀）。备用可能走小米 OpenAI 兼容口，鉴权头可能不是 Bearer，适配器必须可注入。CI Fake。

### ND-STG-03 MinerU 云 API 解析器

- **范围**：可插拔解析器；CI 默认启发式/stdlib；`PIVOT_PARSER=mineru` 时注入云 API；加密/空文本/失败码沿用既有契约。
- **不做**：不在 4C8G 上自建 MinerU；不把 MinerU 标成 MVP 唯一解析器（SPEC 仍写 V2）。
- **Owner 已给**：MinerU **官方云**。公开文档为 Bearer JWT、异步任务（`mineru.net`）。实现时注入 endpoint/token；轮询超时不冻死。不在 4C8G 自建。

### ND-STG-04 阿里云 4C8G Compose 部署

- **状态**：blocked until A1 + STG-01~03 可在 Fake/注入下绿
- **范围**：服务器 Docker Compose；env 文件 gitignore；只暴露 80/443 或 SSH 隧道；资源 limits 适配 8G（外部模型，不跑 MinerU）。
- **不做**：不标 GATE-P0-007/008 verified；不把 4C8G 写成已冻生产规格。
- **何时找 Owner**：见该票 Ready 之后，需要 root/SSH、安全组、磁盘、是否要域名。

---

## 明确不做的票

| 想法 | 原因 |
|---|---|
| 再合成 500 条当企业 Golden Set | 违反 SPEC §10.8 / GATE-P0-002 |
| `must_change_password` 入库 | 非 SPEC §2.2 User 字段（M03 已否） |
| 导出 HTTP 直接流 MinIO 字节并暴露内部地址 | 违反 FR-EXPORT-001 |
| CI `docker compose up` | MODULE_SPEC / 既有变更 |
| 在 Phase A 把 GATE 标 verified | `implemented ≠ verified` |
| Redis 当文档/会话事实源 | SPEC §2.1 |

---

## 会话开场（复制即用）

```text
工作区 E:/AI Project/Pivot，分支 main。
读 AGENTS.md、SPEC.md、MODULE_SPEC.md、PROGRESS.md、
progress/next-dev-spec.md、progress/tickets.md。
本切片只做 <TICKET-ID>。先写 progress/changes/，再 Red。
不冻结 TBD-P0，不把 Fake/Compose fixture 标成 GATE verified。
```
