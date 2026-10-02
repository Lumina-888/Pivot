# 问枢 Pivot 后续工单

> 配套 [`next-dev-spec.md`](next-dev-spec.md)。需求源为 SPEC-1.1 及其引用的 [AGENT_SPEC](../spec/AGENT_SPEC.md)。\
> **目标基线**：ADR-009；**实现基线**：`main` / `wave-3-integrated`（旧夹具，≠ ReAct/≠ P0）。\
> 状态：`ready / blocked / done / superseded`；历史票的部分完成/限定延期按原记录保留。架构 accepted 不等于每刀 DoR；ND-AGENT-01 done；默认下一刀 **ND-AGENT-02-A 内部 Contract 提案**，业务实现仍 blocked。
> **2026-10-02 拆票入口**：[SPEC-1.1 剩余工作 Tickets](tickets/spec-1.1-remaining.md)（29 张细化票、逐票场景/依赖/计划测试/DoD、SPEC 覆盖与 P0/P1 门禁映射）。本文件保留既有父票 ID 和历史证据；子票完成不自动关闭父票或门禁。

图例：`S` 约 1 个主线切片；`M` 约 2–3 切片；`L` 多个串行切片或必须人工/受控环境，不表示并行会话。

---

## 总表

| ID | 标题 | 阶段 | 规模 | Accountable | SPEC | 依赖 | 状态 |
|---|---|---|---|---|---|---|---|
| ND-AGENT-01 | 答案一致性与支持校验门禁 | Agent S1 | M | M05 | FR-QA-002/004, FR-AGENT-005 | 无新公开接口；ADR-009 | done（安全子集，完整持久化仍待 04） |
| ND-AGENT-02 | 工具/模型/预算 Contract 与 LangGraph ReAct | Agent S2 | L | M05 | FR-AGENT-001~004/009 | 01、DR-010、锁依赖 Contract | blocked |
| ND-AGENT-03 | Run/SSE/取消与澄清恢复/Web | Agent S3 | L | M05 | FR-AGENT-007/008, FR-STREAM | 02、M00 恢复/错误契约 | blocked |
| ND-AGENT-04 | 结果事实/checkpoint/租约/一致性 | Agent S4 | L | M03 | FR-AGENT-006, FR-QA-002 | 03、DR-011、迁移 Contract | blocked |
| ND-AGENT-05 | live 模型工具能力与 Agent Golden Set | Agent S5 | L | M11 | FR-AGENT-009/010 | 前序闭环、批准模型/低敏环境 | blocked |
| ND-W3-01 | worker 装配 Qdrant IndexPublisher | A1 | S | M07 | FR-DOC-006, FR-RAG-001 | 无 | done |
| ND-W3-02 | Compose api 注入 `PIVOT_INGEST=celery` | A1 | S | M11 | FR-DOC-005, NFR-OBS | ND-W3-01 建议先 | done |
| ND-W3-12 | Compose api/worker 注入 Qdrant/Redis | A1 | S | M11 | §2.1, NFR-OBS | ND-W3-01 | done |
| ND-W3-03 | 真实解析库 extra（PyMuPDF/docx/pptx/xlsx） | A3 | M | M07 | FR-DOC-004, §6.1 | `20260906-M07-worker-dependencies.md` | done |
| ND-W3-04 | 导出任务 PostgreSQL 持久化 | A2 | S | M06 | FR-EXPORT-001 | 无 | done |
| ND-W3-05 | 会话/refresh 跨进程存储 | A2 | M | M01/M05 | FR-AUTH-001, FR-RBAC-002 | 无 | done |
| ND-W3-06 | 登录限流缺省接到 Redis（仍不冻阈值） | A2 | S | M01 | FR-AUTH-002 | ND-W3-12 | done |
| ND-W3-07 | PATCH 角色 / 重置密码 HTTP | A2 | S | M01 | FR-AUTH-003 | 无 | done |
| ND-W3-08 | SSE 长连接推送与缓冲 | A3 | M | M05/M08 | FR-STREAM-001~003 | 无 | done |
| ND-W3-09 | 旧可选 LangGraph extra | 历史 A3 | M | M05 | FR-QA-001 | ADR-009、ND-AGENT-02 | superseded |
| ND-W3-10 | Playwright 十页 opt-in | A3/C | M | M09/M10/M11 | NFR-UX, GATE-P1 | ND-W3-02 建议 | done |
| ND-W3-11 | version.idempotency_key 入库 | A2 | S | M03/M02 | FR-DOC-005 | 需变更申请；SPEC 字段确认 | blocked |
| ND-W3-13 | Wave 3 收口评审 / tag | A | S | M11 | — | A1 完成 | done |
| ND-W3-14 | Run/EventLog 跨进程存储 | A2 | S | M05/M03 | FR-STREAM-001~004 | ND-W3-05 | done |
| ND-P0-01 | 企业人工标注 Golden Set | B1 | L | 业务/M04/M11 | GATE-P0-002, NFR-QUAL | 人 | 脱敏 120 条 done；业务复核仍待 |
| ND-STG-01 | ingest 与检索共用注入 HTTP Embedding | STG | S | M07/M04 | FR-RAG-001, FR-DOC-006 | ND-W3-01 | done |
| ND-STG-02 | Deepseek-Flash Draft Writer 适配器 | STG | M | M05 | FR-QA-001/002, DR-007 | ND-STG-01 | done |
| ND-STG-03 | MinerU 云 API 解析器（staging） | STG | M | M07 | §6.1 V2 | ND-W3-01 | done |
| ND-STG-04 | 阿里云 4C8G Compose 部署 | STG | M | M11 | NFR-OBS | A1+STG-01~03 | done（overlay）；apply blocked |
| ND-P0-02 | 外发/留存/训练审批 | B1 | L | 法务/安全 | GATE-P0-001, DR-001 | 人 | deferred（企业化；staging 不挡） |
| ND-P0-03 | live Embedding/rerank 冒烟与真实混合检索评测 | B1/STG | M | M04 | FR-RAG-001, GATE-P0-002 | 批准样本/模型/密钥/环境；评测须业务复核集 | blocked（执行）；可先准备计划 |
| ND-P0-04 | Verifier 阈值与盲评 | B1 | L | 算法/M05 | GATE-P0-004, DR-004 | ND-P0-01 | blocked |
| ND-P0-05 | 共享库准入规则 | B1 | S | M01（业务确认） | DR-005, FR-RBAC-004 | 业务确认准入与管理员会话边界 | blocked（签认）；可先起草规则 |
| ND-P0-06 | 真实存储一致性与原子发布环境 | B2 | L | M02/M07/M11 | GATE-P0-003 | ND-W3-01, ND-W3-02, Compose 真跑 | blocked |
| ND-P0-07 | 上线传输/审计/密钥安全验证 | B2 | M | M01/M11 | GATE-P0-005 | HTTPS 拓扑 | blocked |
| ND-P0-08 | 加密 OSS + 新 ECS 备份恢复 | B3 | L | M11 | GATE-P0-006, NFR-DR, DR-003 | 新 ECS | blocked |
| ND-P0-09 | 5 并发 / 100k / P95 峰值 | B3 | L | M11 | GATE-P0-007, NFR-CAP/PERF | 新 ECS | blocked |
| ND-P0-10 | 冻结 TBD-P0 参数包 | B | L | Owner 按附录 E | 各 TBD-P0 | 实测报告 | blocked |
| ND-P0-11 | 固定版本发布、健康门禁、回滚 | B3 | L | M11 | GATE-P0-008 | 镜像仓库/Runbook | blocked |
| ND-P1-01 | P1 进入检查 | C | S | M00/M11 | §12.3 | 八项 verified | blocked |
| ND-P1-02 | 10 页真实系统矩阵 | C | L | M09/M10/M11 | GATE-P1, §12.3 退出 | ND-P1-01 | blocked |

---

## Agent 改造票（当前关键路径）

### ND-AGENT-01 答案安全门禁

- **Accountable / Contributors**：M05 / M03、M06、M11。
- **Given/When/Then**：证据仅支持考勤，模型输出奖金等无关 Markdown；经真实编排器调用后不得 answered，不能从证据另造 Claims 背书原文。
- **范围**：先 Red 覆盖自由 Markdown/Claims 不一致、非法结构、悬空/候选外 Citation、支持性不足；严格结构化输出、完整绑定、保守全量支持门禁和受控渲染。
- **不做**：不装 LangGraph、不增加公开路由、不冻结预算；不把此票视为 Agent 已实现。
- **测试**：`test_FR_AGENT_005_unverified_markdown_never_published`、`test_FR_QA_002_dangling_citation_rejected`、`test_FR_QA_004_verifier_failure_never_answers`；覆盖旧 QA/Run/SSE/导出路径。
- **DoD**：原负向复现被测试锁定，未验证事实不能正式发布；正向/负向回归通过，明确记录尚未持久化的差距。
- **结果**（2026-10-02）：done；M05 实现，M00/M04/M11 贡献。证据 `evidence/agent-m05/nd-agent-01.md`；QA/Run/SSE **79 passed**，全量 **661 passed, 19 skipped**；Web **18/13/8 passed**、typecheck/lint passed。采用完整 Chunk 原文支持门禁，DR-004/010/011 仍开放；Claims/Citation 事务/outbox 未完成，不验收完整 Agent。

### ND-AGENT-02 LangGraph ReAct 最小闭环

- **Accountable / Contributors**：M05 / M00、M01、M03、M04、M11。
- **先决**：01；模型/工具/预算内部 Contract、DR-010 Fixture/运行策略与锁依赖完成后才能从 blocked 改 ready。
- **范围**：真实 StateGraph、scripted Fake tool-calling model、两个只读工具、Observation 再决策、预算和 Finalizer；服务端注入身份/scope，不静默 fallback。
- **测试**：FR-AGENT-001/002/003/004/009 计划测试；不同观察改变工具序列，重复空检索终止，越权和外发阻断。
- **DoD**：Fake 替换模型而非图；可复现“空/不足 → 改写再搜 → 读证据 → 校验答案”；记录生产恢复仍未完成。

### ND-AGENT-03 Run/SSE/澄清与 Web

- **Accountable / Contributors**：M05 / M00、M01、M08、M09、M11。
- **先决**：02；M00 先冻结恢复 endpoint/字段/幂等/错误映射及消费者契约。
- **范围/测试**：粗粒度状态映射、interrupt/授权 resume、取消、白名单公开阶段、校验后 token；FR-AGENT-007/008 与 FR-STREAM 负向/重连测试。
- **DoD**：晚到答案不覆盖取消，SSE 不泄漏消息或重执行，十页/引用抽屉无回归。

### ND-AGENT-04 持久恢复与事实一致性

- **Accountable / Contributors**：M03 / M00、M01、M05、M06、M11。
- **先决**：03；DR-011、checkpoint/Claims/Citation/租约/事件一致性迁移 Contract。
- **范围/测试**：Postgres Checkpointer、一 Run 一 thread、单执行者/fencing、预算恢复、业务结果事务/outbox；FR-AGENT-006 和宕机/争用/取消测试。
- **DoD**：跨进程恢复证据，不重复业务发布；明确供应商调用/计费不保证 exactly-once，记录风险与对账。

### ND-AGENT-05 模型能力与评测

- **Accountable / Contributors**：M11 / M03、M04、M05、业务。
- **先决**：前序闭环，批准的模型配置/低敏或脱敏样本/环境。
- **范围/测试**：主备模型工具协议、用量、外发和超时；Agent Golden Set 的证据支持/工具选择/注入/预算/恢复；FR-AGENT-009/010。
- **DoD**：Fake/live 报告分开；阈值经业务复核/实测冻结；未满足 GATE 的内容保持 unverified。

---

## 当前细化执行队列

详细工单见 [SPEC-1.1 剩余工作 Tickets](tickets/spec-1.1-remaining.md)，不是重开 Wave 3。5 张 ready 仅允许 Contract 调研/提案与 Red 设计，其他实现票仍 blocked。

| 父票 / 新缺口 | 子票 | 本轮拆分范围 |
|---|---|---|
| ND-AGENT-02 | 02-A~H | 内部 Contract、DR-010、依赖锁定、工具、上下文/外发、预算、真实图、答案门禁接图 |
| ND-AGENT-03 | 03-A~E | 恢复公开 Contract、Run/SSE 投影、取消、interrupt/resume、Web 消费 |
| ND-AGENT-04 | 04-A~F | DR-011/迁移、结果事务/outbox、PG checkpoint、租约/fencing/在线入口、用量对账、真实故障测试 |
| ND-AGENT-05 | 05-A~D | 原生工具 HTTP Adapter、主备 live 能力、Agent Golden Set、live 评测 |
| ND-GAP-01~04 | 4 张独立票 | 后台 metrics/tasks、持久审计接线、首次改密生命周期验收、签名下载消费者验收 |
| ND-P0-01 / ND-STG-04 | 01-A / 04-A | 业务复核 120 条脱敏集 / ECS apply；既有填写与 overlay 完成记录不变 |

开工默认：**ND-AGENT-02-A → 02-B → 02-C**，经 Contract/DR-010/依赖审批后才推进 02 实现。03-A/04-A 可先写 proposed 设计，不提前发布路由/迁移。人工与环境票不得由编码会话冒充完成。

---

## Phase A — 历史 Wave 3 工程票

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
- **完成**：2026-09-10。`assemble_ingest_runtime` 在 `PIVOT_VECTOR_STORE=qdrant` 时装配 `IndexPublisher` + Hashing embedder；Compose worker 注入 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*`；CI Fake client。变更 `progress/changes/20260910-M07-worker-qdrant-index.md`。

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
- **完成**：2026-09-10。Compose api 注入 `PIVOT_INGEST` / 队列 / concurrency / `PIVOT_CELERY_BROKER`（`${:?}`）；example 占位 celery；Dockerfile 安装 `worker[celery]`；不注入 eager。变更 `progress/changes/20260910-M11-compose-api-celery-ingest.md`。

### ND-W3-12 Compose 注入 Qdrant/Redis（api+worker）

- **规模 / Owner**：S / M11
- **映射**：§2.1、NFR-OBS
- **依赖**：ND-W3-01
- **范围**：api/worker 注入 `PIVOT_VECTOR_STORE` / Qdrant / `PIVOT_CACHE_STORE` / `PIVOT_QUEUE_STORE` / Redis endpoint（`${}`）。vector/cache 仍允许 memory，但 app profile example 写明 fixture 值。
- **不做**：不冻距离/TTL；不把 Redis 当业务事实源。
- **测试**：`test_NFR_OBS_compose_api_injects_qdrant_redis_*`。
- **完成**：2026-09-10。Compose api/worker 注入同一套 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*` / `PIVOT_CACHE_STORE` / `PIVOT_QUEUE_STORE` / `PIVOT_REDIS_ENDPOINT`（`${}`，store 选择不静默 `:-memory`）；example 占位 qdrant/redis。变更 `progress/changes/20260910-M11-compose-api-worker-qdrant-redis.md`。

### ND-W3-03 真实解析库 extra

- **规模 / Owner**：M / M07（依赖锁 M03/M11）
- **映射**：`FR-DOC-004`、SPEC §6.1
- **依赖**：落实 `20260906-M07-worker-dependencies.md`（Celery extra 已做，解析库仍暂缓）
- **范围**：`worker` optional extra：PyMuPDF/python-docx/python-pptx/openpyxl；解析注册表可切换；CI 默认仍走 stdlib/启发式夹具或受控 fixture 文件（非企业文档）。
- **不做**：不提交企业 PDF；不冻页数/大小；扫描件 OCR 属 P2。
- **测试**：`test_FR_DOC_004_*` 扩展真实库夹具；失败码仍走既有契约。
- **完成**：2026-09-14。`worker[parse]` extra（PyMuPDF / python-docx / python-pptx / openpyxl）；`PIVOT_PARSER=native` 装配真实库注册表；未装 extra 失败闭环；缺省 `local` 仍启发式/stdlib；Dockerfile / CI 安装 `worker[celery,parse]`。变更 `progress/changes/20260914-M07-native-parsers.md`。

### ND-W3-04 导出任务 PostgreSQL 持久化

- **规模 / Owner**：S / M06（M03 端口，M11 装配）
- **映射**：`FR-EXPORT-001~003`、`FR-AUDIT-001`
- **范围**：ExportTask 走 SQLAlchemy；跨装配可见状态；对象仍 MinIO；公开 URL 仍 `PublicDownloadSigner`。
- **不做**：不新增「直接下发 MinIO 字节」的破坏性 HTTP（契约仅短时 `download_url`）；不冻 TTL。
- **测试**：`test_FR_EXPORT_001_postgres_task_survives_assembly`、`test_FR_EXPORT_001_download_url_does_not_leak_minio`。
- **完成**：2026-09-14。`SqlAlchemyExportRepository` 读写 SPEC ExportTask 字段；`PIVOT_STORAGE=postgres` 时与用户目录共用 session factory；跨装配 GET 可见 `ready` + signer URL。变更 `progress/changes/20260914-M06-postgres-export-tasks.md`。

### ND-W3-05 会话 / refresh 跨进程存储

- **规模 / Owner**：M / M01（refresh）+ M05（conversation/run 若仍内存）
- **映射**：`FR-AUTH-001`、`FR-RBAC-002`、FR-STREAM
- **范围**：refresh 与会话/Run 在 `PIVOT_STORAGE=postgres` 时跨 api 实例存活；多 worker/api 不丢登录态。
- **不做**：不把 Redis 当会话事实源（SPEC：Redis 非业务事实）。
- **测试**：`test_FR_AUTH_001_refresh_survives_new_assembly`、`test_FR_RBAC_002_conversation_survives_new_assembly`。
- **完成**：2026-09-14。`PIVOT_STORAGE=postgres` 时 hashed refresh 与 Conversation 跨装配存活；SQL 隐藏删除映射为删行；不新增 hidden 列；不把 Redis 当事实源。Run/EventLog 余量见 ND-W3-14。变更 `progress/changes/20260914-M01-postgres-refresh-conversations.md`。

### ND-W3-14 Run / EventLog 跨进程存储

- **规模 / Owner**：S / M05（Run/SSE）+ M03（SQL 适配）+ M11（装配）
- **映射**：`FR-STREAM-001~004`、`FR-RBAC-002`（消息由 Run 合成）、SPEC §2.2 Run/AgentEvent/Message
- **依赖**：ND-W3-05（Conversation 行已可跨装配）
- **范围**：`PIVOT_STORAGE=postgres` 时 Run 与 EventLog 跨装配存活；幂等键仍唯一；SSE Last-Event-ID 补发可读已持久化事件；消息由已持久化 Run 合成。
- **不做**：不把 Redis 当事实源；不新增 fingerprint/payload 列；不接入 Claim/Citation SQL；不做 uvicorn 长连接；不冻 SSE 预算。
- **测试**：`test_FR_STREAM_001_run_survives_new_assembly`、`test_FR_STREAM_002_003_event_log_survives_new_assembly`、`test_FR_RBAC_002_messages_survive_new_assembly`。
- **完成**：2026-09-14。`SqlAlchemyRunStore` 读写 SPEC Run / AgentEvent / Message；fingerprint 重算；answer 经 assistant Message；AgentEvent.summary 保存公开 SSE 摘要。变更 `progress/changes/20260914-M05-postgres-run-eventlog.md`。

### ND-W3-06 登录限流缺省接到 Redis

- **规模 / Owner**：S / M01
- **映射**：`FR-AUTH-002`
- **依赖**：ND-W3-12（Compose 有 Redis）
- **范围**：Compose 同时注入阈值/窗口 **或** 保持「两者都缺则永不锁定」。禁止在代码里写死次数。
- **不做**：不冻 TBD-P0 阈值；失败仍统一 `AUTH_INVALID_CREDENTIALS`。
- **测试**：沿用 `test_FR_AUTH_002_http_login_rate.py`；新增 compose 注入断言。
- **完成**：2026-09-10。Compose api 注入 `PIVOT_LOGIN_MAX_FAILURES` / `PIVOT_LOGIN_WINDOW_SECONDS`（`${:?}`，不写死次数）；example fixture 占位；进程外缺省仍永不锁定。变更 `progress/changes/20260910-M01-compose-login-rate.md`。

### ND-W3-07 PATCH 角色 / 重置密码 HTTP

- **规模 / Owner**：S / M01
- **映射**：`FR-AUTH-003`、契约 admin users
- **范围**：`PATCH /admin/users/{id}` 支持契约已有角色/重置字段；初始密码不进审计；权限仅 admin。
- **不做**：不把 `must_change_password` 塞进 User 表（非 SPEC §2.2 字段，见既有 M03 结论）。
- **测试**：`test_FR_AUTH_003_http_admin_patch_role_*`、`test_FR_AUTH_003_http_reset_password_*`。
- **完成**：2026-09-14。`PATCH /admin/users/{id}` 处理 `role` / `status` / `reset_password`；角色变更抬升 `token_version` 并审计 `auth.role_change`；重置口令经 HTTPS JSON 一次性返回且不进审计；未知用户 404。`must_change_password` 不入库。变更 `progress/changes/20260914-M01-admin-patch-role-reset.md`。

### ND-W3-08 SSE 长连接与缓冲

- **规模 / Owner**：M / M05（M08 client）
- **映射**：`FR-STREAM-001~003`
- **范围**：uvicorn 长连接推送；Last-Event-ID 补发保持；前端缓冲。
- **不做**：不冻超时；不在事件里带思考链/Prompt。
- **测试**：契约已有重连用例；补 opt-in 集成，CI 默认 skip 长连接。
- **完成**：2026-09-14。`POST /runs` 立即返回 `received`；SSE 按帧推送并去缓冲；`followRunEvents` 非终态续订；uvicorn opt-in skip。变更 `progress/changes/20260914-M05-sse-long-connection.md`。

### ND-W3-09 旧 LangGraph extra（superseded）

- **状态**：superseded，2026-10-02，由 ADR-009 与 ND-AGENT-02 取代。
- **历史范围**：原仅 optional extra/保持固定主图；不是当前实现依据。
- **当前路线**：真实 StateGraph + 原生工具 ReAct；缺配置不得静默 fallback。依赖、预算和恢复按新工单 Contract 逐刀冻结。

### ND-W3-10 Playwright 十页 opt-in

- **状态**：done（2026-09-14）
- **规模 / Owner**：M / M09+M10，M11 装配
- **映射**：NFR-UX、§12.3 P1 退出（10 页）
- **范围**：`PIVOT_REQUIRE_PLAYWRIGHT=1` 覆盖前台 6 + 后台 4；CI 默认 skip。
- **不做**：不把 Fake fetch 当浏览器证据；不标 GATE-P0-005 verified。
- **完成**：2026-09-14。opt-in Chromium 覆盖 SPEC 十页；夹具播种共享文档与普通用户；UserShell 增加 sr-only「管理后台」供键盘/客户端跳转。变更 `progress/changes/20260914-M11-playwright-ten-pages.md`。

### ND-W3-11 version.idempotency_key 入库

- **状态**：blocked
- **原因**：M03 已记录「本切片不新增列」。若契约/幂等跨进程必须落库，先写 `progress/changes/` + 迁移，确认 SPEC §2.2 / 附录是否要求该列。
- **不做**：不在未批变更时加列。

### ND-W3-13 Wave 3 收口评审

- **状态**：done（2026-09-10；A1 ND-W3-01/02/12 已完成；GATE-P0 仍全部 unverified）
- **Owner**：M11
- **DoD**：分组回归绿；更新矩阵；证据写明 **全部 GATE-P0 仍 unverified**；tag `wave-3-integrated` 仅表示夹具收口，不等于 P0 通过。
- **完成**：2026-09-10。`evidence/wave3-m11/wave3-closeout.md` + 矩阵 Wave 3 夹具基线；分组 Python 469 passed / 12 skipped。变更 `progress/changes/20260910-M11-wave3-closeout.md`。

---

## Phase B — P0 闸门票（人 / 受控环境）

### ND-P0-01 企业人工标注 Golden Set

- **状态**：脱敏填写 **done**（2026-09-14，120 条）；业务部门复核仍 **待做**；GATE 仍 unverified
- **规模**：L（人工）
- **映射**：GATE-P0-002、NFR-QUAL-001~012、§10.8
- **范围**：真实/脱敏企业问句 + 期望文档/Citation；版本化；禁止把 v0.2-synthetic 改名成企业集。
- **DoD**：标注规范、条数与分层、评测脚本入口；阈值仍等 ND-P0-10。填写 100~150 条后才算标注完成。
- **完成（工程）**：2026-09-14。`ANNOTATION.md` + 空 schema + `ops/run_golden_set.py`。变更 `progress/changes/20260914-M11-golden-set-enterprise-schema.md`。
- **完成（脱敏填写）**：2026-09-14。`retrieval/v0.3-enterprise.json` 120 条，十层各 12；`ops/golden_set_enterprise.py`。变更 `progress/changes/20260914-M11-golden-set-enterprise-fill.md`。不是业务复核，不标 GATE verified。

### ND-P0-02 外发/留存/训练审批

- **状态**：deferred for `dev-staging`；企业化部署前必须重开
- **映射**：GATE-P0-001、DR-001
- **staging**：规章制度等低敏测试文档 + 注入外部 API 不挡。仍禁止企业合同/人事材料。
- **产物（企业化）**：审批记录（区域、留存、不训练、删除）。

### ND-P0-03 live Embedding / rerank 冒烟与真实混合检索评测

- **状态**：blocked（live 执行缺批准配置/样本/密钥/环境确认）；可先准备 opt-in 计划。原 ready 是开发准备口径，不是供应商已可调用的证据。
- **映射**：FR-RAG-001~006、GATE-P0-002、DR-002
- **范围**：CI 默认 skip，不提交 URL/密钥；先验证 HTTP 能力，再于业务复核集上验证真实 dense+BM25+RRF+bge、过滤/scope/降级/冲突/代次，报告 Recall 与限制。
- **依赖 / 验收**：冒烟需要批准低敏范围/配置；评测需 ND-P0-01-A 和真实索引环境。详细计划测试/报告见剩余 Tickets §4。
- **不做**：不标 GATE verified（冒烟 ≠ 评测通过）；不因 staging 延期审批而允许真实企业文档外发。

### ND-P0-04 Verifier 阈值与模型盲评

- **映射**：GATE-P0-004、DR-004、FR-QA-004~006
- **产物**：评测报告；阈值写入 SPEC/ADR 后才能当默认。

### ND-P0-05 共享库准入规则

- **状态 / Accountable**：blocked（业务签认）；M01，业务贡献准入决策。可先起草，不假定业务已确认。
- **映射**：DR-005、FR-RBAC-004
- **产物**：仅低敏、全员可见且允许外发的准入规则；管理员查看他人会话边界明确。代码已有 `shared_visible` 不替代业务确认；不满足共享库前提时走独立 ACL 需求/ADR。

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

- **状态**：done（2026-09-14）
- **依赖**：ND-W3-01（worker 已能接 VectorStore）
- **范围**：`PIVOT_EMBEDDING=http` 时 ingest 与 query 用同一注入 embedder（硅基 `BAAI/bge-m3` 与现有 OpenAI embeddings 形状兼容）；维数仍注入不写死；失败不 published。Rerank 硅基 `BAAI/bge-reranker-v2-m3` 与现有 `/rerank` 适配器兼容，本票可顺带接到 worker/runtime。
- **不做**：不冻模型名/维数。
- **完成**：2026-09-14。`assemble_ingest_runtime` 在 `PIVOT_EMBEDDING=http` 时装配 `HttpQueryEmbedder`；HTTP runtime ingest 与 query 共用同一实例；失败不 published；Compose api/worker 注入同一套 `PIVOT_EMBEDDING*`。Rerank 仍只在 runtime。变更 `progress/changes/20260914-M07-ingest-http-embedding.md`。

### ND-STG-02 Deepseek-Flash Draft Writer

- **范围**：注入 endpoint/model/api_key 的 HTTP Writer，替换证据拼接；Citation 仍必须落在检索候选；`external_llm_allowed` 为 false 不得外发；失败闭环（超时/429→既有错误码）。
- **不做**：不写死 DeepSeek/硅基 URL；CI Fake transport；不把 LangGraph 绑死本票。
- **Owner 已给**：主模型 **DeepSeek 官方** `deepseek-flash`；备用 **小米官方** `mimo-v2.5`。**不走硅基。** 两套 endpoint/key 分开注入；鉴权头可注入（小米可能非 Bearer）。CI Fake。
- **完成**：2026-09-14。`PIVOT_LLM=http` 装配 OpenAI 兼容 Writer；主失败才切 `PIVOT_LLM_FALLBACK_*`；`external_llm_allowed=false` 不得 HTTP；Compose 仅 api 注入。变更 `progress/changes/20260914-M05-http-draft-writer.md`。

### ND-STG-03 MinerU 云 API 解析器

- **状态**：done（2026-09-14）
- **范围**：可插拔解析器；CI 默认启发式/stdlib；`PIVOT_PARSER=mineru` 时注入云 API；加密/空文本/失败码沿用既有契约。
- **不做**：不在 4C8G 上自建 MinerU；不把 MinerU 标成 MVP 唯一解析器（SPEC 仍写 V2）。
- **Owner 已给**：MinerU **官方云**。公开文档为 Bearer JWT、异步任务（`mineru.net`）。实现时注入 endpoint/token；轮询超时不冻死。不在 4C8G 自建。
- **完成**：2026-09-14。`PIVOT_PARSER=mineru` 装配 `MinerUCloudParser`（异步 batch 上传/轮询/zip）；加密/损坏本地拦截；扫描件走云 OCR；Compose api/worker 注入 `PIVOT_PARSER*`。变更 `progress/changes/20260914-M07-mineru-cloud-parser.md`。

### ND-STG-04 阿里云 4C8G Compose 部署

- **状态**：overlay/runbook **done**（2026-09-14）；ECS apply 仍 **blocked**（Owner SSH/安全组/磁盘/域名）
- **范围**：服务器 Docker Compose overlay；env 文件 gitignore；只暴露 80 或 SSH 隧道（443 待证书）；资源 limits 适配 8GiB（外部模型，不跑 MinerU）。
- **不做**：不标 GATE-P0-007/008 verified；不把 4C8G 写成已冻生产规格；编码会话不冒充 SSH 上机。
- **完成**：2026-09-14。`docker-compose.staging.yml` + nginx 默认 `127.0.0.1:80` 反代 web；8GiB limits fixture；`ops/compose.staging.env.example`；gitignore `*.env`；Runbook 列出 Owner 前置。变更 `progress/changes/20260914-M11-compose-staging.md`。
- **何时找 Owner**：apply 仍需要 root/SSH、安全组、磁盘、是否要域名。

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
另读 spec/AGENT_SPEC.md、ADR-009。本切片只做 <TICKET-ID>。
另读 progress/tickets/spec-1.1-remaining.md，选择一张子票，不一次实现整个父票。
ND-AGENT-01 已完成；默认下一刀 ND-AGENT-02-A Contract 提案，随后 02-B/02-C；预算/锁依赖未满足不得写业务实现；恢复/checkpoint 依赖票仍 blocked。
先登记 progress/changes/，再 Red；旧 ECS/live 票不覆盖当前 Agent 关键路径。
不冻结 TBD-P0，不把 Fake/Compose fixture 标成 GATE verified。
```
