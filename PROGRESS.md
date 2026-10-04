# 问枢 Pivot 开发进度

> **进度文档不是需求源**：需求以 [`SPEC.md`](SPEC.md) 为准，模块边界以 [`MODULE_SPEC.md`](MODULE_SPEC.md) 为准。  
> **最后更新**：2026-10-04（02-C Ubuntu 手动候选 CI 入口准备/新增61项检查；Python 1031 passed/19 skipped，Hosted CI 尚未执行，安全/Agent 签认仍 pending）\
> **目标状态**：SPEC-1.1/AGENT-SPEC-1.0/ADR-009 已接受 LangGraph 受控 ReAct；当前代码仍是旧线性 RAG，框架/工具循环/checkpoint 尚未接入；ND-AGENT-01 已修复答案一致性/引用/支持门禁与校验前草稿泄漏（保守完整原文策略）。ND-AGENT-02-A/B/C 内部、预算及依赖/锁定提案、03-A恢复与04-A持久化Contract提案均review待签认；04-A新增173项元数据shape检查通过，不代表PG恢复/迁移/租约实施；02-C Windows Python 3.12 验证与候选哈希锁已提交，预算映射已修订为 proposed draft.2（独立累计执行前门禁），新增9项技术 canary/合计20 probes passed；旧 Windows 环境 Linux 验证因无 Docker/WSL 故障 blocked；当前 Arch 本机开发环境已配置并通过既有回归/浏览器组，Docker 镜像拉取及 daemon proxy 授权仍 blocked，02-C 目标平台原生锁与消费者/Owner/安全签认仍 pending，不满足 DR-010/锁依赖时禁止业务实现。架构 accepted 不等于 implemented/verified；预算 DR-010、恢复契约、checkpoint DR-011 仍待关闭。
> **当前实现状态**：主线开发（MODULE-SPEC-1.2）；Wave 3 夹具已收口；ingest/检索可共用注入 HTTP Embedding；可注入 HTTP Draft Writer 与 MinerU 云解析器；`PIVOT_PARSER=native` 可装配 PyMuPDF/docx/pptx/xlsx extra（缺省仍启发式/stdlib）；dev-staging Compose overlay 已入库（ECS apply 待 Owner SSH/安全组/磁盘）；hashed refresh、Conversation 与 Run/EventLog 可跨装配；SSE 长连接推送（opt-in uvicorn）；opt-in Playwright 十页；企业 Golden Set v0.3 脱敏摘录 120 条（非业务复核，非 GATE）。工作区仅为 `Pivot/` 的 `main`。波次基线 `wave-3-integrated`（**不等于** P0 通过）。
> **当前基线**：`wave-3-integrated`：HTTP + composition root + Next `/api/v1` 反代 + opt-in Playwright 十页 + PG/MinIO/Qdrant/Redis 客户端 + Golden Set v0.2-synthetic（120 条）+ 企业 Golden Set v0.3 脱敏摘录 120 条（annotated_desensitized，Fake Keyword） + 导出对象 MinIO + 导出任务 SQLAlchemy（CI sqlite） + hashed refresh / Conversation / Run/EventLog SQLAlchemy（CI sqlite） + 检索 dense 消费 Qdrant + ingest→Qdrant + HTTP 上传进程内 ingest + 5 并发/进程内备份夹具 + stdlib BM25/可注入 rerank + Dockerfile/Compose api+web+worker profile `app` + 100k Chunk opt-in 夹具 + HTTP Embedding/bge-reranker 适配器 + ingest/检索共用注入 HTTP Embedding + Redis 登录限流计数 + PG 文档事实 + Celery ingest eager + Compose Celery worker + worker 共享 MinIO/PG ingest runner + Compose api 共享 PG/MinIO + worker 装配 Qdrant IndexPublisher + Compose api 注入 `PIVOT_INGEST=celery` + Compose api/worker 注入 Qdrant/Redis + Compose api 注入登录限流阈值/窗口 + Compose api/worker 注入 `PIVOT_EMBEDDING*` + 可注入 HTTP Draft Writer（Compose 仅 api 注入 `PIVOT_LLM*`） + 可注入 MinerU 云解析器（Compose api/worker 注入 `PIVOT_PARSER*`） + `worker[parse]` 真实解析库 extra（`PIVOT_PARSER=native`；CI 微型夹具；缺省仍启发式/stdlib） + dev-staging Compose overlay（nginx loopback :80，8GiB limits fixture） + SSE 长连接（POST 立即返回 received；逐帧推送；Next SSE Route Handler 去缓冲；opt-in uvicorn）。GATE-P0 全部 unverified。

## 1. 新会话恢复入口

1. 确认 cwd 为当前 Linux 仓库 `/home/lumina888/Projects/Pivot`，分支为 `main`；`E:/AI Project/Pivot` 是历史 Windows 路径，不要进入 `../Pivot-Mxx-*`；
2. 读取 `AGENTS.md`；
3. 读取 `MODULE_SPEC.md`；
4. 读取本文件和本切片涉及的 `progress/modules/Mxx.md`；
5. 用 `git log --oneline --decorate -20` 确认实际基线。
6. 后续开发计划与工单：[`progress/next-dev-spec.md`](progress/next-dev-spec.md)、[`progress/tickets.md`](progress/tickets.md)、[SPEC-1.1 剩余 Tickets](progress/tickets/spec-1.1-remaining.md)（不是需求源；29张细化票，0张ready，02-A/B/C、03-A、04-A共5张review待签认，24张blocked）。Owner 历史 `dev-staging` 环境范围：[`progress/changes/20260910-M00-dev-staging-scope.md`](progress/changes/20260910-M00-dev-staging-scope.md)。

本机开发/测试入口见 [Linux runbook](ops/runbook-local-linux.md) 与 [2026-10-03 环境证据](evidence/local-linux-20261003.md)。Python 3.12.10、Node/npm、现有 extras、Playwright 与 loopback API/Web 可用；Python 661 passed/19 skipped、Web 18/13/8 passed、浏览器11 passed。Docker daemon/组权限已配置，但真实依赖镜像与代理授权未完成；memory 模式 readyz=503、检索为空，不宣称真实存储/RAG 就绪。未安装未批准 Agent 依赖、不关闭 02-C 或 GATE。

最新 [02-C Ubuntu 手动候选 CI 入口准备](evidence/agent-m03/nd-agent-02-c/ubuntu-ci-preparation.md)：新增仅手动确认触发的 Ubuntu24.04/Python3.12.10 验证流程，Actions 固定 commit、隔离 driver/native resolver/双离线重建/哈希负向/20技术探针与旧回归；准备工具严格拒绝平台/材料漂移、非官方URL、畸形JSON及越界/旧输出。新增61项本地检查，安全组128 passed；原环境完整Python **1031 passed/19 skipped/0 failed**、harness exit0、ruff/compileall通过，工具/测试/YAML主动LSP clean。本机Arch前检正确拒绝且无输出，主.venv未装LangGraph。未推送或触发Hosted CI，默认ci.yml/正式依赖/既有候选/业务不变；02-C review、0 ready/5 review/24 blocked、所有签认/DR/GATE不变。下一步经Owner审查后在远端运行手动CI并归档真实证据，不把入口准备当CI passed。

此前 [02-C压缩wheel错误脱敏回归](evidence/agent-m03/nd-agent-02-c/compression-errors.md)：修复离线核验工具未捕获DEFLATE/LZMA底层解压异常、CLI泄漏traceback/本机路径的问题，沿用既有脱敏分类。新增三种压缩格式9项正负向测试，Red4 failed/5 passed后安全组67 passed；原环境完整Python**970 passed/19 skipped/0 failed**、harness exit0、ruff/compileall与两Python文件主动LSP clean。Windows111项材料、bookworm/Ubuntu各109个缓存wheel复核通过；未改业务/依赖/锁/CI/用户配置，未重跑目标候选/正式CI/Web/PG/live。02-C review、0 ready/5 review/24 blocked及签认/DR/GATE不变，下一步仍须前置提案签认与批准验证环境。

此前 [02-C离线候选一致性工具](evidence/agent-m03/nd-agent-02-c/integrity-tool.md)：`ops/check_candidate_integrity.py`严格核验manifest/锁集合、文本摘要、固定项目输入和可选wheel字节/METADATA，拒绝重复项/越界路径，CLI错误脱敏且明确不等于批准。Windows manifest补齐锁文件名（版本/哈希不变）；Windows111项材料、bookworm/Ubuntu各109个缓存wheel复核通过。新增56项安全测试，原环境完整Python**961 passed/19 skipped/0 failed**、ruff/compileall与两Python文件主动LSP clean。未改业务/依赖/锁/CI/用户配置，未重跑目标候选/正式CI/Web/PG/live；02-C review、0 ready/5 review/24 blocked、所有签认/DR/GATE不变。

此前 [02-C公开供应链诊断](evidence/agent-m03/nd-agent-02-c/supply-chain-public-check.md)：Ubuntu/bookworm109个包名/版本集合一致，OSV batch未返回命中、已知漏洞正/负对照通过；只作数据库快照，不称零漏洞或安全签认。grpcio-tools/langsmith源码hash/身份核验后补充对应上游版本标签主LICENSE全文、commit/blob/静态版本绑定，wheel缺文本仍保留。原项目Python**905 passed/19 skipped/0 failed**、ruff/compileall通过；未改依赖/业务/CI或发送项目数据。正式CI/角色锁/许可证兼容/CVE/遥测/原生库与所有签认仍pending，业务DoR/DR/GATE不变。

此前 [M11 私有配置回归修正](evidence/wave3-m11/private-env-regression.md)：staging测试改为验证Git索引及仓库实际忽略规则，允许正常本地配置存在，不读删用户`.env`。新增9项临时仓库负向/正向用例；本机完整Python分组**905 passed/19 skipped/0 failed**，ruff/compileall通过。测试要求Git及工作区元数据；未重跑候选容器/正式Ubuntu CI，不解除Agent签认或GATE。

此前 [Ubuntu 独立候选锁验证](evidence/agent-m03/nd-agent-02-c/linux-ubuntu.md)：在新容器/目录原生重新解析109 wheel，逐字节核验已有缓存后完成双venv离线hashes安装/pip check、错误哈希负向与技术探针各20 passed。完整Python分组895 passed/1 failed/19 skipped、ruff/compileall通过；唯一失败仍是根`.env`存在性断言，未读删配置或放宽测试。已提交独立proposed锁/含源码工具链来源的manifest；Ubuntu源码诊断不等于Actions artifact/Hosted CI，正式CI/角色锁/供应链/签认仍pending，不解锁业务。

上轮 [清华源 Ubuntu 诊断](evidence/agent-m03/nd-agent-02-c/linux-ubuntu-tuna.md)：Python3.12.10源码20.5MB/3.4秒下载，摘要与官方HTTPS Sigstore bundle相符（未做完整签名链验证）；Ubuntu24.04/glibc2.39源码构建、stdlib与pip25.0.1验证通过，清华pip原生dry-run解析109个wheel，版本/报告哈希与bookworm差异0。仅临时容器配置清华apt/pip；未装Agent依赖，未做独立Ubuntu锁/双重建/探针/Hosted CI，不代签或解锁业务。

02-C 新增 [离线供应链材料与 Ubuntu 下载阻断](evidence/agent-m03/nd-agent-02-c/supply-chain.md)：109 个 bookworm wheel 哈希/身份相符、107 个检出随包许可证文本，2 个待补齐；许可证兼容性/CVE/遥测仍 pending。Ubuntu 镜像可运行，但固定 Python 构建连续下载超时，未生成 Ubuntu 锁，不解除业务 DoR。

当前跟进见 [02-A/B/C 审核与待签清单](evidence/agent-m03/nd-agent-02-abc-review.md)：预算 draft.2 映射已修订但未批准。Debian bookworm runtime 候选锁已验证（109 wheel、双环境 20 probes、895/1/19），见 [证据](evidence/agent-m03/nd-agent-02-c/linux-bookworm.md)；Ubuntu CI、供应链与签认仍 pending，执行单见 [原生验证单](evidence/agent-m03/nd-agent-02-c/linux-validation.md)。**02-A/B/C review、02-D～H blocked 不变**，技术验证不能代签各消费者/Owner。

如果没有指定切片：优先 **02-A/B/C 签认、Linux 锁验证与预算映射确认**；02-A [内部模型/工具/State 提案](progress/changes/20261002-M05-agent-internal-contract.md)、02-B [预算提案](progress/changes/20261002-M05-agent-budget-contract.md)、02-C [依赖/锁定申请](progress/changes/20261002-M03-agent-dependencies-lock.md)均 review 待签认，未发布。02-C Windows 候选 111 个 wheel 哈希、两个隔离 venv/11 探针与旧回归通过，不是生产锁或 Agent 验收；[证据](evidence/agent-m03/nd-agent-02-c.md)。03-A [恢复Contract提案](progress/changes/20261003-M00-agent-resume-contract.md)/独立proposed schema与62项形状检查已提交、review待签认；[证据](evidence/agent-m00/nd-agent-03-a.md)。04-A [checkpoint/租约/事实/outbox提案](progress/changes/20261003-M03-agent-persistence-contract.md)与独立schema/173项shape检查已提交，review待7项签认；[证据](evidence/agent-m03/nd-agent-04-a.md)。独立前置提案已全部提交，下一步须签认/目标平台锁验证/批准PG环境，不把形状绿灯当业务DoR；ND-AGENT-02~05父票业务实现仍blocked。ND-AGENT-01 done，证据见 `evidence/agent-m05/nd-agent-01.md`。先读 `spec/AGENT_SPEC.md` 和 ADR-009。旧 ECS apply/live 检索工单保留，不覆盖 Agent 关键路径。企业 Golden Set v0.3 已填 120 条脱敏摘录，**不等于**业务复核或 GATE-P0-002。Wave 3 夹具已收口（`wave-3-integrated` **不等于** P0 通过）。不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / 企业 Golden Set 空 schema / Fake embedder / stdlib BM25 / 进程内压测/恢复 / Dockerfile fixture / opt-in 100k Fake retrieve / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / sqlite 导出任务 / sqlite refresh/会话 / sqlite Run/EventLog / eager Celery / Compose Celery fixture / Fake MinIO worker ingest / Compose api 共享存储注入 / Fake worker Qdrant upsert / Compose api celery 注入 / Compose Qdrant·Redis 注入 / Compose 登录限流注入 / Wave 3 夹具收口 / ingest 共用 HTTP Embedding / Fake HTTP Writer / Fake MinerU 解析器 / staging Compose overlay / SSE 长连接夹具 / 真实解析库 extra / opt-in Playwright 十页 标成 GATE verified。不要新建 worktree。

## 2. 当前波次与模块状态

状态枚举：`planned` → `claimed` → `in_progress` → `blocked` → `review` → `integrated`。主线会话可更新本表。

| 模块 | 状态 | 代码位置 | 基线契约 | 最近证据 | 下一步 |
|---|---|---|---|---|---|
| M00 契约治理 | in_progress | `main` | 目标 SPEC-1.1；发布 contract-v0.1 | 公共契约48 passed；03-A schema62/04-A schema173 passed；5前置review | 消费者签认；Linux/预算映射；04-A治理审核 |
| M01 身份授权 | integrated | `main`（tag `M01-v0.6.0`） | `contract-v0.1` | 37 单元/安全 + 登录/改密/管理用户 HTTP + PATCH 角色/重置 + Compose 注入 Redis 限流 + refresh 跨装配 | 人工标注 Golden Set 或 STG-04 ECS apply |
| M02 文档接入 | integrated | `main`（tag 目标 `M02-v0.6.0`） | `contract-v0.1` | 27 单元 + 上传/列表/详情/重试/删除/预览/下载 HTTP；runtime 上传后进程内 ingest；`PIVOT_INGEST=celery` 可入队；Compose api 注入 celery ingest；publish 写回 chunk | HTTP 缺省仍 sync ingest |
| M03 数据基础 | in_progress | `main`（旧 tag 目标 `M03-v0.8.0`） | `contract-v0.1`；依赖 draft proposed | 02-C Windows/bookworm/Ubuntu源码诊断候选锁与双重建；04-A proposed/schema173 passed；旧 SQL 基线保留 | 正式Ubuntu CI/角色锁、供应链与依赖审核；04-A签认/DR-011/批准PG环境 |
| M04 检索 RAG | integrated | `main`（tag 目标 `M04-v0.5.0`） | `contract-v0.1` | 31 单元 + 搜索 HTTP + Qdrant dense + stdlib BM25 + ingest/检索共用注入 HTTP Embedding/bge + 合成 Golden Set 120 条 + 企业脱敏摘录 120 条 | STG-04 ECS apply 或 live 供应商冒烟 |
| M05 ReAct/QA/Run/SSE | in_progress | `main`（旧 tag `M05-v0.6.0`） | 目标 AGENT-SPEC-1.0；发布 contract-v0.1 | ND-AGENT-01 done；79 QA/Run/SSE 回归；02-A/B/C proposed/review，未验收新 ReAct | 签认累计硬预算与 strict/serde 约束；Claim/Citation/checkpoint 待实现 |
| M06 导出/审计 | integrated | `main`（tag 目标 `M06-v0.3.0`） | `contract-v0.1` | 26 单元 + 导出/审计 HTTP + PG 任务跨装配 | 对象字节下载 HTTP 仍不新增（契约仅短时 URL） |
| M07 Worker/解析/索引 | integrated | `main`（tag `M07-v0.10.0`） | `contract-v0.1` | 79 单元 + ingest→Qdrant + HTTP 进程内 runner + parse 队列消费 + Celery eager ingest + Compose Celery worker + 共享 MinIO/PG runner + worker Qdrant IndexPublisher + ingest HTTP Embedding + MinerU 云解析器 + `worker[parse]` native extra | 缺省仍启发式；OCR 属 P2 |
| M08 Web 基础 | integrated | `main`（tag `M08-v0.3.0`） | `contract-v0.1` | M08 18 tests + SSE 去缓冲 Route Handler + typecheck/lint 通过 | Compose web 由 M11 装配 |
| M09 员工前台 | integrated | `main`（tag 目标 `M09-v0.2.0`） | `wave-1-integrated` | 13 Fake + followRunEvents + opt-in Playwright 十页 | Chrome/Edge 版本仍 TBD-P0 |
| M10 管理后台 | integrated | `main`（tag `M10-v0.1.0`） | `wave-1-integrated` | 8 Fake + opt-in Playwright 后台页 | `/admin/metrics` `/admin/tasks` HTTP 仍未挂 |
| M11 集成/质量/运维 | in_progress | `main`（tag `M11-v0.25.0` / `wave-3-integrated`） | `wave-3-integrated` | 分组回归见本切片日志 | GATE-P0 仍全部 unverified；企业 Golden Set 为脱敏摘录诊断；staging ECS apply 待 Owner SSH/安全组/磁盘 |

模块详细状态由各自 `progress/modules/Mxx.md` 维护。历史 `../Pivot-Mxx-*` worktree 不再使用。

### 当前 Agent 改造

FR-AGENT-001~010 仍为 accepted、未完整实现/验收；FR-AGENT-005 的迁移基线答案门禁已修复（ND-AGENT-01 done），不代表事实持久化或真实图通过。02 因预算/依赖 Contract blocked，03 因恢复公开 Contract blocked，04 因 checkpoint/迁移策略 blocked，05 因前序闭环/批准 live 环境 blocked。不得以旧 integrated 状态或旧绿灯验收新需求；完整 Accountable/测试见 AGENT_SPEC 和验收矩阵。

## 3. 需求追踪摘要

完整映射和 Accountable/Contributors 见 [`MODULE_SPEC.md §8`](MODULE_SPEC.md#8-需求-accountable-映射)。验收链必须遵循：需求 ID → 场景 ID → 契约/数据 → 测试 ID → 验收证据 → verified。

| 需求范围 | Accountable | 测试/场景入口 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| FR-AUTH-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/`、`tests/integration/pipeline/test_FR_AUTH_001_http_login.py`、`tests/integration/pipeline/test_FR_AUTH_004_http_admin_users.py`、`tests/integration/pipeline/test_FR_AUTH_002_http_login_rate.py`、`tests/integration/pipeline/test_FR_AUTH_001_http_postgres_sessions.py` | implemented | 37 项单元/安全 + 登录/刷新/退出/改密/管理用户 HTTP；PATCH 角色/重置；限流计数可注入 Redis CacheStore；Compose api 注入阈值/窗口（不写死次数；进程外缺省不锁定）；`PIVOT_STORAGE=postgres` 时 hashed refresh 跨装配存活（CI sqlite） |
| FR-RBAC-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/`、`spec/scenarios/auth.feature`、`tests/integration/pipeline/test_FR_RBAC_002_http_conversations.py`、`tests/integration/pipeline/test_FR_RBAC_003_http_preview.py`、`tests/integration/pipeline/test_FR_AUTH_001_http_postgres_sessions.py` | implemented | 资源四重授权与会话隔离；会话 CRUD HTTP 仅 owner 可见；`PIVOT_STORAGE=postgres` 时 Conversation 跨装配存活（CI sqlite）；预览/下载按详情同等可见性 |
| FR-DOC-001~008 | M02 | `tests/unit/documents/`、`tests/integration/pipeline/test_FR_DOC_001_http_upload.py`、`tests/integration/pipeline/test_FR_DOC_007_http_lifecycle.py`、`tests/integration/pipeline/test_FR_RBAC_003_http_preview.py`、`tests/unit/worker/test_FR_DOC_006_qdrant_index.py`、`tests/integration/pipeline/test_FR_DOC_006_ingest_qdrant.py`、`tests/integration/pipeline/test_FR_DOC_001_http_postgres_facts.py`、`tests/integration/pipeline/test_FR_DOC_005_celery_postgres.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_minio_ingest.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_qdrant_publish.py` | implemented | 28 项 M02 单元 + 文档上传/列表/详情/版本/重试/删除/预览/下载 HTTP；runtime 上传后进程内 ingest（信封仍 uploaded）；`PIVOT_INGEST=celery` 时可 eager 入队；Compose api 注入 celery ingest（yml 不写死 broker，CI 不 up）；`PIVOT_STORAGE=postgres` 时文档事实可跨装配存活（sqlite 测试 URL）；worker 可从共享 MinIO 读取对象字节（CI Fake client）；worker 可向注入 Qdrant 发布（CI Fake client） |
| FR-SEARCH-001~002 / FR-RAG-001~006 | M04 | `tests/unit/retrieval/`、`tests/security/retrieval/`、`tests/integration/pipeline/test_FR_SEARCH_001_http_search.py`、`tests/integration/pipeline/test_FR_SEARCH_001_qdrant_retrieval.py`、`tests/integration/pipeline/test_FR_RAG_001_bm25_runtime.py`、`tests/integration/pipeline/test_FR_RAG_001_http_embedding_bge.py`、`tests/integration/pipeline/test_FR_DOC_006_ingest_http_embedding.py`、`tests/integration/pipeline/test_NFR_QUAL_golden_set.py`、`tests/integration/pipeline/test_NFR_QUAL_golden_set_enterprise.py` | implemented | 31 项 M04 单元 + 搜索 HTTP + Qdrant dense + ingest 可写入同一端口 + stdlib BM25 + ingest/检索共用注入 HTTP Embedding/bge（CI Fake transport）+ 合成 Golden Set 120 条 + 企业脱敏摘录 120 条（Fake Keyword，非业务复核） |
| FR-QA-001~006 / FR-STREAM-001~005 | M05 | `tests/unit/qa/`、`tests/unit/runs/`、`tests/contract/stream/`、`tests/integration/pipeline/test_FR_STREAM_001_http_runs.py`、`tests/integration/pipeline/test_FR_STREAM_001_http_postgres_runs.py`、`tests/integration/pipeline/test_FR_STREAM_002_sse_live.py`、`tests/integration/pipeline/test_FR_RBAC_002_http_conversations.py`、`tests/integration/pipeline/test_FR_QA_001_http_writer.py` | accepted（ND-AGENT-01 门禁已实现；新图/恢复/完整持久化待实现） | 79 项 M05 QA/Run/SSE；新增 HTTP/SSE/消息/导出安全回归见 `test_FR_AGENT_005_answer_publication.py`；旧 30 项 M05 领域 + Run/SSE 长连接 + 会话 CRUD HTTP（消息由 Run 合成）；Conversation 与 Run/EventLog 可走 SQLAlchemy（CI sqlite）；Claim/Citation 仍不入库；`PIVOT_LLM=http` 可注入 Writer（CI Fake transport）；uvicorn 长连接 opt-in skip |
| FR-EXPORT-001~003 / FR-AUDIT-001~003 | M06 | `tests/unit/exports/`、`tests/unit/audit/`、`tests/security/export/`、`tests/integration/pipeline/test_FR_EXPORT_001_http_exports.py`、`tests/integration/pipeline/test_FR_EXPORT_001_http_postgres_tasks.py` | implemented | 26 项 M06 单元 + 导出/审计 HTTP；运行时导出字节可接 MinIO，公开 URL 仍为 signer；`PIVOT_STORAGE=postgres` 时任务可跨装配存活（sqlite 测试 URL） |
| §2 存储不变量 | M03 | `tests/integration/db/`、`api/src/pivot/db/`、`migrations/` | implemented | M03 数据测试 + 48 项 M00 契约回归通过；用户目录、文档事实、导出任务、hashed refresh、Conversation 与 Run/EventLog 默认 SQLite 覆盖；MinIO/Qdrant/Redis 默认内存 client；Compose 为 opt-in skip |
| §6 解析/分块/索引执行 | M07 | `tests/unit/worker/`、`tests/integration/pipeline/test_FR_DOC_006_ingest_qdrant.py`、`tests/integration/pipeline/test_FR_DOC_001_http_runtime_ingest.py`、`tests/integration/pipeline/test_NFR_OBS_compose_worker.py`、`tests/integration/pipeline/test_NFR_OBS_compose_api.py`、`tests/integration/pipeline/test_FR_DOC_005_celery_postgres.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_minio_ingest.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_qdrant_publish.py`、`tests/integration/pipeline/test_FR_DOC_006_ingest_http_embedding.py`、`tests/integration/pipeline/test_FR_DOC_004_native_parser.py` | implemented | 79 项 M07 测试通过；stdlib/Fake 或注入 HTTP Embedding；可注入 MinerU 云解析器（CI Fake HTTP）；`PIVOT_PARSER=native` 可装配 PyMuPDF/docx/pptx/xlsx（`worker[parse]`；CI 微型夹具；缺 extra 失败闭环）；IndexPublisher 可写入注入 VectorStore；HTTP 上传默认可进程内 ingest；`PIVOT_INGEST=celery` 为 eager 任务（可见 PG version/task）；Compose api 注入 celery ingest（Dockerfile 装 worker[celery,parse]）；Compose worker 为注入 broker 的 Celery，只监听 parse 队列；worker 装配共享 MinIO/PG runner（CI sqlite + Fake MinIO）；`PIVOT_VECTOR_STORE=qdrant` 时 worker 装配 IndexPublisher（CI Fake client）；`PIVOT_EMBEDDING=http` 时 ingest 与检索共用注入 embedder（CI Fake HTTP）；`PIVOT_PARSER=mineru` 时装配云解析器（Compose api/worker 注入 `PIVOT_PARSER*`） |
| §1.5 / NFR-UX 设计系统与 client | M08 | `tests/e2e/fixtures/web/test-foundation.mjs` | implemented | M08 18 项基础测试通过（含 `/api/v1` rewrite 与 SSE 去缓冲 Route Handler）；产品页由 M09/M10 接管 |
| 前台 6 页 | M09 | `tests/e2e/user/test_user_web.mjs`、`tests/integration/pipeline/test_NFR_UX_browser_ten_pages.py` | implemented | 13 项 Fake fetch（含 followRunEvents）+ opt-in Playwright 十页；CI 默认 skip |
| 后台 4 页 | M10 | `tests/e2e/admin/test_admin_web.mjs`、`tests/integration/pipeline/test_NFR_UX_browser_ten_pages.py` | implemented | 8 项 Fake fetch + opt-in Playwright 后台页；CI 默认 skip；`/admin/metrics` `/admin/tasks` HTTP 仍未挂 |
| NFR-CAP/PERF/OBS/DR、GATE-P0-001~008 | M11 | `tests/integration/pipeline/`、`tests/security/ops/`、`tests/performance/`、`evidence/wave2-m11/`、`evidence/wave3-m11/` | implemented（CI/Fake + HTTP + composition root + Next rewrite + opt-in Playwright 十页 + PG/MinIO/Qdrant/Redis + 合成 Golden Set + 导出 MinIO + 检索 dense 消费 Qdrant + ingest→Qdrant + 5 并发/进程内备份 + stdlib BM25 + Dockerfile/Compose api+web+worker + 100k opt-in + HTTP Embedding/bge Fake transport + ingest/检索共用 HTTP Embedding + Celery eager ingest + Compose Celery worker + worker 共享 MinIO/PG ingest + Compose api 共享 PG/MinIO + worker Qdrant IndexPublisher + Compose api celery ingest + Compose api/worker Qdrant/Redis + Compose api 登录限流注入 + Compose api/worker Embedding 注入 + 可注入 HTTP Draft Writer + 可注入 MinerU 云解析器 + `worker[parse]` native extra）；GATE-P0 unverified | TestClient；CI 不 build/up Compose、不跑 100k、不打真实供应商；Playwright/Compose/100k 默认 skip |

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
- [x] opt-in Playwright 十页（ND-W3-10；前台 6 + 后台 4；CI 默认 skip；≠ GATE-P0-005）
- [x] PostgreSQL 用户事实源客户端（`SqlAlchemyUserDirectory`；`PIVOT_STORAGE=postgres`；URL 注入）
- [x] MinIO 文档对象客户端（`MinioObjectStore`；`PIVOT_OBJECT_STORE=minio`；endpoint/bucket 注入）
- [x] 导出对象接到 MinIO（`ExportObjectAdapter`；公开 URL 仍 `PublicDownloadSigner`）
- [x] Qdrant 向量客户端（`QdrantVectorStore`；`PIVOT_VECTOR_STORE=qdrant`；endpoint/collection 注入）
- [x] Redis 缓存/队列客户端（`RedisCacheStore`/`RedisQueueStore`；`PIVOT_CACHE_STORE`/`PIVOT_QUEUE_STORE=redis`；endpoint 注入）
- [x] Golden Set v0.1-synthetic 检索夹具（10 条分层，Fake KeywordRetriever）
- [x] Golden Set v0.2-synthetic 检索夹具（120 条分层，Fake KeywordRetriever；非企业标注）
- [x] 企业 Golden Set v0.3 脱敏摘录（ND-P0-01；120 条，十层各 12；Fake Keyword 诊断；≠ 业务复核；≠ GATE verified）
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
- [x] Run/EventLog 跨进程（ND-W3-14；CI sqlite；Claim/Citation 仍不入库）
- [x] SSE 长连接推送与 Next 去缓冲（ND-W3-08；POST 立即返回 received；逐帧推送；opt-in uvicorn；CI 默认 skip）
- [x] 真实解析库 extra（ND-W3-03；`worker[parse]` PyMuPDF/docx/pptx/xlsx；`PIVOT_PARSER=native`；CI 微型夹具；缺省仍启发式/stdlib）
- [x] opt-in Playwright 十页（ND-W3-10；`PIVOT_REQUIRE_PLAYWRIGHT=1`；CI 默认 skip；≠ GATE-P0-005）
- [x] 企业 Golden Set 脱敏摘录 / 评测入口（ND-P0-01；120 条；≠ GATE verified）
- [ ] Qdrant 100k 索引峰值、新 ECS 加密 OSS 备份恢复、live Embedding/rerank/MinerU 冒烟、staging ECS apply、业务部门复核 Golden Set
- [ ] 任一 `GATE-P0-*` verified

## 5. 未完成项与已知差距

- [x] Wave 0 基础已存在：`api/` 数据端口、`web/` 设计系统与 client；
- [x] Wave 1 领域服务已存在：auth/documents/retrieval/qa/runs/stream/exports/audit/parsing/chunking 与 `worker/`（Fake/stdlib）；
- [x] `spec/contracts/`、`spec/scenarios/`、`spec/acceptance/matrix.md` 已由 M00 建立；Golden Set v0.2-synthetic 已建（120 条合成）；企业集 v0.3 脱敏摘录已入库（120 条，非业务复核）；真实供应商 live 冒烟仍待；
- [x] `tests/` 已有 M00 契约 48、M03 数据 12、M08 基础 9、Wave 1 领域 97、M09 12、M10 8、M11 pipeline/ops/perf（合入后 45 passed / 2 skipped）；
- [x] 分组 CI（`.github/workflows/ci.yml` + `ops/run_grouped_tests.py`）已装配，不启动 Compose；
- [x] `docker-compose.yml` 依赖 fixture + opt-in `api` profile 已合入 main；CI **不得** `up`/`build`；本机未强制拉起；
- [x] FastAPI 健康装配：`GET /healthz`、`GET /readyz`（探测注入，失败闭环）；optional extra `http`；
- [x] FastAPI `/api/v1/auth/login|refresh|logout`（注入 AuthService 才挂载；HttpOnly refresh Cookie）；
- [x] FastAPI `GET/POST /api/v1/documents`（同时注入 DocumentService 与 AuthService 才挂载）；
- [x] FastAPI 文档详情/版本/重试/删除（`/documents/{id}` 及 `/versions|/retry|/delete`）；
- [x] FastAPI `GET /api/v1/search`（同时注入 RetrievalService 与 AuthService 才挂载）；
- [x] FastAPI `/api/v1/runs` 创建/详情/SSE 长连接/取消（同时注入 RunService、QaOrchestrator 与 AuthService 才挂载；POST 立即返回 received；uvicorn 长连接 opt-in skip）；
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
- [x] Qdrant 向量客户端（默认 CI 用内存 client；Compose Qdrant 为 opt-in skip）；dense 检索可消费 VectorStore；ingest `IndexPublisher` 可 `upsert`（CI Fake client）；HTTP 上传默认可进程内 ingest；`PIVOT_INGEST=celery` 为 eager；Compose api 注入 celery ingest（CI 不 up）；Compose worker 注入 broker 只听 parse，并装配共享 MinIO/PG runner 与 Qdrant IndexPublisher；Compose api/worker 注入同一套 Qdrant 变量（CI 不 up）；`PIVOT_EMBEDDING=http` / `PIVOT_RERANK=bge` 可注入（CI Fake HTTP，非 live 供应商）；ingest 与检索共用同一注入 HTTP embedder；stdlib BM25 可注入；`PIVOT_PARSER=mineru` 可注入云解析器（CI Fake HTTP；Compose api/worker 注入 `PIVOT_PARSER*`；缺省仍启发式/stdlib）；`PIVOT_PARSER=native` 可装配 `worker[parse]` 真实库（CI 微型夹具；未装 extra 失败闭环）；
- [x] Redis 缓存/队列客户端（默认 CI 用内存 client；Compose Redis 为 opt-in skip）；登录限流计数可注入 Redis CacheStore；Compose api 注入阈值/窗口（不写死次数；进程外缺省不锁定）；Compose Celery broker 为注入 fixture；Compose api/worker 注入 cache/queue/Redis endpoint（CI 不 up；Redis 不是业务事实源）；
- [ ] 真实 PG Alembic 冒烟因无 Docker/psycopg 为 skip；
- [ ] 所有 `TBD-P0` 均未冻结，禁止模块自行填默认值；
- [ ] P0 八项门槛均未验证；
- [x] Wave 0 三项变更申请已批准：`20260906-M00-contract-test-path.md`、`20260906-M03-ownership-clarification.md`、`20260906-M08-web-scaffold-ownership.md`。
- [x] Wave 1 观测包变更已批准：`20260906-M06-observability-package-init.md`。
- [x] Wave 1 `argon2-cffi` 已写入 pyproject：`20260906-M01-auth-dependencies.md`（2026-09-09 composition root 落实）。
- [ ] LangGraph 尚未安装到原环境/正式依赖或接入业务；02-C 仅在 `.pi/` 双隔离 venv 验证并提交 proposed 候选锁。旧 `20260906-M05-langgraph.md` 暂缓已被 ADR-009 取代，ND-AGENT-02 的预算/依赖 Contract 待签认/发布。`20260906-M07-worker-dependencies.md` 的 Celery extra 与解析库 extra 已落实。
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
- [x] Wave 3 SSE 长连接已批准：`progress/changes/20260914-M05-sse-long-connection.md`。
- [x] Wave 3 真实解析库 extra 已批准：`progress/changes/20260914-M07-native-parsers.md`。
- [x] Wave 3 opt-in Playwright 十页已批准：`progress/changes/20260914-M11-playwright-ten-pages.md`。
- [x] 企业 Golden Set 标注规范与空 schema 已批准：`progress/changes/20260914-M11-golden-set-enterprise-schema.md`。
- [x] 企业 Golden Set v0.3 脱敏摘录已批准：`progress/changes/20260914-M11-golden-set-enterprise-fill.md`。

## 6. 轮次日志

### 2026-10-04 — ND-AGENT-02-C Ubuntu 手动候选 CI 入口准备

- **范围 / 基线**：main `4fb1693`，开场clean；用户确认继续正式Ubuntu CI验证准备。M11工作流/准备工具/bootstrap候选锁/安全测试/证据，M03模块进度，根/交接同步。默认CI、pyproject/既有候选、业务/公开Contract/迁移/镜像、主环境与用户配置不变。见[范围记录](progress/changes/20261004-M11-candidate-ubuntu-ci-preparation.md)/[证据](evidence/agent-m03/nd-agent-02-c/ubuntu-ci-preparation.md)。
- **交付 / Red**：仅workflow_dispatch且确认默认false；Ubuntu24.04/Python3.12.10与三Actions固定commit，隔离hash driver/native report/双离线venv/各20 probes/错误hash负向/旧回归，失败保留有限artifact。准备工具拒绝漂移/非官方URL/重复项/畸形JSON/越界和旧输出。Red先缺入口，再暴露roots6项、report25项、CLI/workflow及整数URL问题，逐段Green；新增61项通过，无业务Agent实现。
- **验证 / 限制**：Python3.12.10/pip25.0.1/pytest9.1.1/ruff0.16.6；安全组128 passed，完整Python十组 **1031 passed/19 skipped/0 failed**、harness exit0、ruff/compileall通过，工具/测试/YAML三路径主动LSP clean。Arch CLI预期exit1/native_environment且无目录，主.venv无LangGraph。actionlint未安装，未跑Web/Hosted CI/目标候选/PG/live/镜像；不宣称正式Ubuntu CI通过，不推送或dispatch。
- **下一步**：Owner审核入口与待验证ref，远端手动运行并归档run/真实环境/双重建/负向/探针/回归证据；角色锁、来源/供应链及消费者/Owner签认仍pending。02-C review、0 ready/5 review/24 blocked、02-D～H/DR-010/011/TBD-P0/全部GATE不变。

### 2026-10-04 — ND-AGENT-02-C 离线候选一致性工具

- **范围 / 基线**：main `fa291b2`，开场clean；M11工具/安全测试/证据，M03 Windows manifest只补齐锁文件名与模块进度，根/交接同步。未改业务、pyproject/锁文件、公开Contract、CI/镜像/迁移、主环境或用户配置。见[范围记录](progress/changes/20261004-M11-candidate-integrity-tool.md)/[证据](evidence/agent-m03/nd-agent-02-c/integrity-tool.md)。
- **Red / Green**：缺工具1 error；首次实现Windows manifest缺字段1 failed/41 passed，补齐证据元数据（版本/哈希不变）。非 JSON 常量3 failed→显式拒绝后passed；新增56项负向/正向测试，安全组58 passed；严格JSON/锁全量集合/文本摘要/固定项目输入/可选wheel字节-METADATA核验，不执行wheel或读写供应商配置。
- **验证 / 限制**：Windows111项材料、bookworm/Ubuntu各109个既有缓存wheel原始字节/身份一致。原环境Python3.12.10/pytest9.1.1/ruff0.16.6/packaging26.3完整十组**961 passed/19 skipped/0 failed**、harness exit0、ruff/compileall通过，主动LSP两Python文件clean。未解析/下载/安装候选，未重跑目标候选/正式CI/Web/PG/Saver/live/镜像；一致性不证明来源可信或批准。
- **下一步**：正式Ubuntu CI/角色锁/构建来源、安全与消费者/Owner签认仍pending；02-C review、0 ready/5 review/24 blocked、02-D～H/DR-010/011/TBD-P0/全部GATE不变。

### 2026-10-04 — ND-AGENT-02-C 公开供应链诊断

- **范围 / 基线**：main `497c15c`，开场clean；M11公开依赖查询/生成报告/证据、M03候选范围与进度、根/交接同步。未改业务、pyproject/锁/CI/镜像/迁移/主环境/用户配置，不安装扫描器或候选包。
- **结果**：109项OSV batch未返回命中，requests已知受影响/修复版本目标advisory对照通过；不代表零漏洞/完整覆盖。grpcio-tools1.84.0/langsmith0.14.3源码hash/PKG-INFO相符，补充固定上游tag/commit/blob的主LICENSE全文与静态版本绑定；第三方版权不当主许可证，wheel缺文本仍保留。官方langsmith下载exit28、不完整文件未使用，清华完整下载hash匹配。见[证据](evidence/agent-m03/nd-agent-02-c/supply-chain-public-check.md)/[范围记录](progress/changes/20261004-M11-agent-public-supply-chain-check.md)。
- **验证 / 限制**：离线109查询/对照/2许可证版本材料复核通过；本机Python3.12.10/pytest9.1.1/ruff0.16.6完整十组**905 passed/19 skipped/0 failed**、harness exit0、ruff/compileall通过。未跑正式CI/目标候选/Web/真实PG/Saver/live/镜像，不发送项目/企业数据。来源签名、许可兼容/CVE/遥测/内嵌库仍pending。
- **下一步**：正式Ubuntu CI/角色锁/构建来源、安全与消费者/Owner签认；0 ready/5 review/24 blocked、02-D～H/DR-010/011/TBD-P0/全部GATE不变。

### 2026-10-04 — M11 本机私有配置安全回归修正

- **范围 / 基线**：main `75cf0aa`，开场clean；M11 staging测试、[变更记录](progress/changes/20261004-M11-private-env-regression.md)/[证据](evidence/wave3-m11/private-env-regression.md)、模块/根/交接同步。未改业务、公开Contract、依赖/CI/Compose、用户配置或`.gitignore`。
- **Red / Green**：原测试因本地`.env`存在失败；9项临时Git仓库用例旧实现5 failed/4 passed，揭示合法配置误报及注释伪规则漏检。改为Git索引与实际忽略来源检查，强制暂存/规则缺失/本地或全局排除均不能放行；staging最终22 passed/1 skipped。
- **验证 / 限制**：原项目Python3.12.10/pytest9.1.1/ruff0.16.6/Git2.55.0；完整Python十组**905 passed/19 skipped/0 failed**、harness exit0、ruff/compileall通过，主动Python LSP clean。未读删真实配置；Git缺失/元数据不可用必须失败，精简容器需提供Git，未重跑目标候选/正式CI/Web/真实PG/live，不冒称对应验收。
- **下一步**：02-A/B/C/03-A/04-A签认、正式Ubuntu CI与供应链审核仍pending，0 ready/5 review/24 blocked、DR-010/011/TBD-P0/GATE不变；本轮只修正测试安全边界。

### 2026-10-04 — ND-AGENT-02-C Ubuntu 独立候选锁与双重建

- **范围 / 基线**：main `3460a2f`，开场clean；M03独立候选锁/manifest，M11新隔离容器/回归/证据与执行单，根/交接同步。未改业务源码、pyproject/正式锁、CI/Dockerfile/Compose、迁移、主.venv、宿主源或用户配置。
- **结果**：固定Ubuntu24.04/glibc2.39、上轮只读源码CPython3.12.10/pip25.0.1，新resolver原生解析109 wheel；与bookworm集合/版本/hash差异0，Windows-only为colorama/pywin32。缓存wheel按本轮report逐字节核验，两全新venv离线hashes安装/pip check成功；独立proposed manifest显式标记source-built diagnostic/not-hosted-ci。见 [证据](evidence/agent-m03/nd-agent-02-c/linux-ubuntu.md)/[变更记录](progress/changes/20261004-M11-ubuntu-candidate-rebuild.md)。
- **验证 / 限制**：xxhash错误哈希dry-run exit1/hash mismatch；技术探针各20 passed；完整Python分组**895 passed/1 failed/19 skipped**，ruff/compileall passed。唯一失败仍是本机gitignored根`.env`与已有不存在断言冲突，未读取/删除/放宽测试，不宣称全量绿。docker run工具等待600秒超时后容器继续，最终wait/inspect exit1/running=false，不重跑或遗留运行。
- **下一步**：正式Ubuntu CI/Actions工具链、角色锁/系统库/构建工具、完整签名链/许可证/CVE/遥测与消费者/Owner签认仍pending；未跑Web/真实PG/Saver/live/应用镜像。02-C review、0 ready/5 review/24 blocked、DR-010/011/TBD-P0/全部GATE不变；全部业务DoR满足后才推进02-D～H。

### 2026-10-03 — ND-AGENT-02-C 清华源 Ubuntu 诊断

- **范围 / 基线**：main `93c24fe`，开场clean；Owner请求换清华源，M11临时Ubuntu容器/忽略artifact验证，M03候选范围进度，根/交接同步。不改宿主源/主.venv、业务/正式依赖/锁、CI/镜像/迁移或用户.env。
- **结果**：清华源码下载20.5MB/3.418秒；SHA-256与官方HTTPS Sigstore bundle摘要相符，完整签名链未验。Ubuntu24.04/glibc2.39/GCC13.3.0源码构建Python3.12.10/pip25.0.1，运行库补齐后stdlib导入/SQLite/bz2/lzma往返通过。清华pip原生dry-run解析109个wheel，包集合/版本/报告SHA-256与bookworm差异均0；验证容器exit0且已停止。首次构建工具调用600秒超时、容器随后完成，以及新基础镜像缺sqlite运行库的修复均记录在 [证据](evidence/agent-m03/nd-agent-02-c/linux-ubuntu-tuna.md)。
- **限制 / 下一步**：源码构建不冒充Actions artifact或Hosted CI。未安装Agent依赖/生成Ubuntu锁/双离线重建/探针/分组回归；工具链/签名/供应链和各消费者/Owner签认仍pending。02-C review、0 ready/5 review/24 blocked、DR-010/011/TBD-P0/GATE不变。

### 2026-10-03 — ND-AGENT-02-C 离线供应链材料与 Ubuntu 阻断

- **范围 / 基线**：main `8009841`，开场 clean；M11 证据/生成清单，M03 候选/进度，根与交接同步。未改业务源码、正式依赖/锁、CI/镜像/迁移或用户配置，未安装新包。
- **结果**：109 个既有 bookworm wheel 原始 SHA-256 与 METADATA 身份相符；62 有 SPDX 表达式、45 有旧 License 字段、45 有 classifier（覆盖重叠），107 检出随包许可证文件，grpcio-tools/langsmith 2 项待补齐。PyMuPDF 双许可/psycopg LGPL 等只记录声明，不代签法律/安全判断。Ubuntu 24.04 镜像检查通过；Actions Python 3.12.10 构建两次 240 秒下载超时，未安装/解析/生成 Ubuntu 锁。详见 [证据](evidence/agent-m03/nd-agent-02-c/supply-chain.md)。
- **验证**：bookworm verify 既有技术探针 **20 passed**；公共 Contract/DB **331 passed**，QA/Run/SSE **79 passed**，109 项清单复核、6 文档/69 本地链接、JSON/内嵌命令语法与 ruff 检查通过。上一轮全量 `.env` 存在性失败未修、不读删配置，未将部分回归当全量绿。
- **下一步**：完整且经审核的 Ubuntu 固定 Python 构建、原生锁/双重建/CI，许可证兼容性/CVE/遥测/原生库与角色锁/构建审核、消费者/Owner 签认。02-C review、0 ready / 5 review / 24 blocked、DR-010/011 与全部 GATE 不变。

### 2026-10-03 — ND-AGENT-02-C Debian bookworm 候选锁

- **范围 / 基线**：main `93f7e50`，开场 clean。M03 候选解析/锁，M11 容器验证、证据与分组回归；M00 只同步恢复入口。未改 pyproject、正式锁、CI、Dockerfile、业务源码、迁移或生产默认。
- **结果**：`python:3.12.10-slim-bookworm`（digest `sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db`，glibc 2.36，pip 25.0.1）解析 109 个 wheel。与 Windows 候选规范化后版本差 0，仅少 colorama/pywin32；28 个原生 wheel 独立哈希。官方文件源超时后，清华 HTTPS 按 `--require-hashes` 下载，原始 SHA-256 一致。材料为 proposed/pending，不是发布锁。
- **验证**：verify/rebuild 离线安装与 pip check 通过；xxhash 零哈希 dry-run exit 1。两环境技术探针各 **20 passed**。分组 **895 passed / 1 failed / 19 skipped**，ruff/compileall passed；唯一失败是既有根 `.env` 存在性断言，未读取、删除或放宽。完整限制见 [证据](evidence/agent-m03/nd-agent-02-c/linux-bookworm.md)。
- **下一步**：Ubuntu CI 原生锁、许可证/CVE 与镜像构建仍 pending。02-A/B/C/03-A/04-A 签认不变；0 ready / 5 review / 24 blocked，02-D～H 不解除。DR-010/011、TBD-P0 与全部 GATE 不关闭。

### 2026-10-03 — ND-AGENT-04-A 持久化 Contract 前置

- **范围 / 基线**：main `d613318`，开场clean；M03持久化/DR-011提案，M00独立proposed schema/根级契约测试/工单/README，M05消费者进度，M11证据/回归，根/交接同步。未改业务源码、公开契约/错误、依赖/迁移/CI/Compose/生产默认。
- **结果**：AGENT-PERSISTENCE-0.1-draft.1 proposed；定义Saver写入fencing、版本/已确认checkpoint绑定、累计预算/epoch、原助手Message与事实/终态/outbox事务、取消/重放、ProviderAttempt unknown对账、治理/备份与非破坏回滚。04-A review，7项签认pending；0 ready/5 review/24 blocked，所有业务父票/04-B~F仍blocked。
- **验证**：缺schema Red1 error→1 passed；缺5组件Red5 failed/1 passed→6 passed；日期负向发现可选format checker缺失，2 failed→stdlib日历校验通过；最终shape173 passed。完整Python分组**895 passed/1 failed/19 skipped**，契约/DB331、QA/Run/SSE79 passed；已有staging要求根`.env`不存在，本机gitignored配置存在，未读取/删除或放宽测试，不宣称全量绿。ruff/compileall通过；LSP JSON/提案clean，Python导入pytest/jsonschema存在home根解释器错配，项目venv导入/执行已验证，不宣称LSP整体clean。完整命令/限制见 [证据](evidence/agent-m03/nd-agent-04-a.md)。
- **下一步**：02-A/B/C/03-A/04-A消费者与Owner签认、02-C目标平台锁/批准PG环境。真实Saver/租约/结果事务/恢复测试仍未实施；DR-010/011/TBD-P0与全部GATE不关闭，不再把已提交前置提案当ready业务票。

### 2026-10-03 — ND-AGENT-03-A 澄清恢复 Contract 前置

- **范围 / 基线**：main `20e8f15`，开场clean；M00提案/独立proposed schema/根级契约测试/工单与契约README，M05消费者进度，M11证据与回归，根/交接同步。不改业务源码/公开OpenAPI/SSE/Worker/依赖/迁移/生产默认。
- **结果**：AGENT-RESUME-0.1-draft.1 proposed；定义owner-only、澄清ID、202历史受理回执、原键授权重放/异参冲突、一次受理/取消竞争、累计预算/期限、敏感字段白名单与04-A边界。03-A review，7项签认pending，1 ready/4 review/24 blocked；没有可调用resume或新Agent验收。
- **验证**：缺schema Red 1 error → 1 passed；回执/等待视图/错误组件Red 12 failed/1 passed → 13 passed；最终拟议shape62、既有公共契约48、QA/Run/SSE79 passed。全量Python分组 **724 passed/1 failed/17 skipped**，已有staging测试要求根`.env`不存在而本地gitignored文件存在，未读取/删除或放宽测试；**不宣称全量绿**。ruff/compileall通过；LSP两个导入告警为home根/项目venv错配，已用实际导入佐证，Markdown unavailable不当clean。完整命令/限制见 [证据](evidence/agent-m00/nd-agent-03-a.md)。
- **下一步**：02-A/B/C/03-A消费者与Owner签认、02-C目标平台锁验证；独立可做04-A proposed。03-B~E和02~05业务仍blocked；DR-010/011/TBD-P0/全部GATE不关闭。全量staging本地环境断言差距单独跟进，不移除用户配置修绿。

### 2026-10-03 — 本机 Linux 开发环境与清华默认源

- **范围 / 基线**：main `8782c7c`，开场 clean；M11 用户授权本机配置与验证，M03 解释器记录，M00 恢复入口。配置独立 Python 3.12.10/.venv、现有 extras、原 Web lock、Playwright、loopback 用户服务；pip/Arch 首选清华。系统 Python、正式依赖/锁、CI/镜像、业务源码/迁移/契约不变。
- **验证**：Python 十组 **661 passed/19 skipped**、ruff/compileall passed；Web **18/13/8 passed**、typecheck/lint passed；真实浏览器组 **11 passed**。本地 health/login/native PDF 解析/无证据 refused/SSE 通过，完整命令与初轮超时记录见 [环境证据](evidence/local-linux-20261003.md)。整体 harness 在 npm 阶段超时，Web 独立补跑，不宣称单次 harness exit 0。
- **限制 / 下一步**：Docker client/server 已验证、用户组已配置；官方镜像直连超时，daemon proxy 两次 pkexec 等待超时，四容器未启动。memory 默认未连检索索引，readyz 真实503/四依赖false；只能本机开发/测试，真实存储联调待 Owner 授权。操作见 [runbook](ops/runbook-local-linux.md)，[变更边界](progress/changes/20261003-M11-local-linux-environment.md)。Arch 环境不替代 Debian runtime/Ubuntu CI 候选锁，02-A/B/C review、D~H blocked、DR-010/011/TBD-P0/全部 GATE 不变。

### 2026-10-02 — 02-A/B/C 技术审核、预算映射修订与 Linux 前置阻断

- **基线 / 范围**：main `bfe8971`；M05 内部/预算申请（02-B draft.2）、M03 依赖申请/平台 probe、M11 新增技术探针/审核证据/Linux 执行单、M00/M03/M05/M11 进度与根/交接/工单入口同步。六处已有业务源码和所有用户文件保留，不纳入提交。
- **结果**：补齐同步/异步 None/Command/多节点同一步边界的技术审核；独立累计图账本/节点体前预扣、恢复 epoch、重放/unknown 保守占用及 provider 双计量要求明确。最终 wire strict/序列化白名单/遥测要求保留；不写业务 BudgetGate 或冒充消费者签认。
- **验证 / 环境**：Windows CPython 3.12.10 候选隔离 verify/rebuild venv 各技术20 passed（原11+新9），公共契约48 passed、旧 QA/Run/SSE79 passed；错平台 manifest 预期拒绝、2schema/4正向/49负向、14文档/120链接/29票/内嵌Linux Python语法与ruff/git diff检查 passed。首次 QA 未注入源码路径10 collection errors，按既有 harness 的 PYTHONPATH 规则重跑通过；辅助脚本 E501 已修复。WSL/Bash 0x80070422、无 docker，真实 Linux 验证 blocked；详细命令/静态/回归与签认清单见 [本轮证据](evidence/agent-m03/nd-agent-02-abc-review.md)。不以计划执行单或 Windows resolver 冒充 Linux 锁。
- **审批 / 下一步**：02-A/B/C review；消费者/Owner/安全 pending；2 ready/3 review/24 blocked 不变，02-D～H 继续 blocked。Owner 提供或手动恢复批准 Linux 环境后执行原生验证与独立镜像/供应链审查，逐项签认再发布 Contract/重核 DoR；DR-010/011、生产 TBD-P0 与全部 GATE 不关闭。无正式依赖/CI/镜像/路由/迁移/生产默认变更。

### 2026-10-02 — ND-AGENT-02-C Python 3.12 依赖验证与锁定申请

- **范围 / Accountable**：M03 依赖申请/候选版本与锁策略；M11 `evidence/agent-m03/nd-agent-02-c.md` 及锁/manifest/11 项独立技术探针，M00 工单/计划/契约 README/根入口，M05 消费约束与进度。开场 main `11e8a8c`；六处已有业务源码修改与用户未跟踪文件保留，不纳入本刀。
- **结果**：AGENT-DEPENDENCIES-0.1-draft.1 proposed，02-C review（非 done/发布）；LangGraph 1.2.12、core 1.6.6、可选 openai adapter 1.6.7、checkpoint 4.2.0、PG Saver 3.1.2、psycopg/pool 3.3.6/3.3.3。Windows 候选完整验证闭包 111 wheel ==/SHA-256，62 个重叠旧版本不变；原 `.venv` 64 个捕获版本均未改、无 LangGraph。
- **关键发现**：None 恢复在锁版本中可执行 limit+2 ticks；02-B 的 min 映射必须补独立硬预算签认。预格式化工具字典不被 strict 参数自动硬化，serde 会保留私有 reasoning canary；独立累计/字段白名单/wire schema 检查均是待业务实现门禁，不私改预算或安全策略。
- **验证**（Python 3.12.10 / pip 25.0.1 / pytest 9.1.1 / ruff 0.16.6；PowerShell 5.1）：import Red **1 failed** → 隔离 import passed；两个新 venv 均 hashes/offline 重建、pip check 通过，最终 **11 probes passed**；错误哈希 dry-run 明确 **exit 1**。候选环境按 `ops/run_grouped_tests.py` 的 10 组回归 **661 passed / 19 skipped**，ruff/compileall passed；12 Markdown/92 本地链接/29 票状态与 111 个实际 wheel 哈希检查、artifact ruff/`git diff --check` passed。主动 LSP 12 文档 unavailable、1 Python inconclusive，不宣称 clean；完整命令、初轮假设/文本摘要修正、最终 `checks-20261002-164852/` 日志与限制见证据。全部生成目录/pytest temp 在仓库 `.pi/artifacts/nd-agent-02-c/`。
- **限制 / 下一步**：未改 pyproject/正式锁/CI/镜像/业务源码/路由/迁移/生产默认，未验证 Linux/PG setup或恢复/live/许可证及漏洞全量审核；6 项签认 pending。02-A/B/C review，剩 2 张 ready 仅允许前置，24 张实现/人工票仍 blocked；先补签认/Linux/预算映射，或独立 03-A proposed。DR-010/011、TBD-P0 和所有 GATE 不关闭。

### 2026-10-02 — ND-AGENT-02-B DR-010 预算 Contract 提案

- **范围 / Accountable**：M05 预算/累计用量设计；M00 工单/计划/契约说明与进度同步，M11 证据路径。新增 `progress/changes/20261002-M05-agent-budget-contract.md` 与 `evidence/agent-m05/nd-agent-02-b.md`；开场 main `715e6d5`，已有 6 个业务源码修改及用户未跟踪文件均保留，不纳入本刀。
- **结果**：AGENT-BUDGET-0.1-draft.1 proposed；必需策略/单位、全角色预扣/结算、unknown 保守占用、主备/重试/恢复累计、固定期限、图/观察/历史/context/并发门禁、有限 Fixture、18 组 Red 设计及 7 个 pending 签认项。02-B review（非 done/发布），3 张 ready 只开放前置；02-A/B 待签认，父票/业务实现仍 blocked。
- **验证**（Python 3.12.10 / pytest 9.1.1 / jsonschema 4.26.0 / ruff 0.16.6；PowerShell 5.1）：`.venv/Scripts/python -B .pi/artifacts/nd-agent-02-b/check-proposal.py` → **2 schema / 5 正向 / 175 负向、有限 Fixture 算术、10 Markdown / 71 本地链接 / 29 票（3 ready、2 review、24 blocked）通过**；公共契约 **48 passed**、既有 QA/Run/SSE **79 passed**；artifact 脚本 ruff 与 `git diff --check` passed。pytest basetemp/日志均显式位于仓库 `.pi/artifacts/nd-agent-02-b/`；首轮脚本 E501 已修。主动 Markdown LSP 10 文件 unavailable，artifact 辅助 AST 的 3 项已解释，不宣称 LSP clean；完整命令、版本与限制见证据。
- **限制 / 下一步**：本轮不写业务源码/路由/公开 schema/依赖/迁移或生产默认，不运行新预算/真实图/恢复/并发/live；DR-010/011、TBD-P0 与全部 GATE 保持未关闭。默认下一刀 02-C Python 3.12 依赖验证/锁定申请；消费者/Owner 未批准前 02-D~H 不开工。

### 2026-10-02 — ND-AGENT-02-A 内部 Contract 提案

- **范围 / Accountable**：M05 内部模型/工具/State/EvidenceRegistry 设计；M00 治理追踪。新增 `progress/changes/20261002-M05-agent-internal-contract.md` 与 `evidence/agent-m05/nd-agent-02-a.md`；同步工单/计划、M00/M05、契约 README 与根交接入口。开场 main `cdadc53`；6 个已有业务源码修改及用户未跟踪文件均保留，不纳入本刀。
- **结果**：AGENT-INTERNAL-0.1-draft.1 proposed；原生单工具调用/消息关联、严格参数/控制意图、可信上下文与敏感状态、证据来源/去重/版本/定位、Finalizer/失败分类、11 组 Fake/Red 设计与 7 个消费者 pending 项。02-A 改 review（未签认/未发布/非 done），4 张前置票 ready；父票/业务实现继续 blocked。
- **验证**（Python 3.12.10 / pytest 9.1.1 / jsonschema 4.26.0；PowerShell 5.1）：`.pi/artifacts/nd-agent-02-a/check-proposal.ps1` → **4 schema / 10 正向接受 / 28 负向拒绝**；`.venv/Scripts/python -B -m pytest tests/contract --ignore=tests/contract/stream -q -p no:cacheprovider` → **48 passed**；`.venv/Scripts/python -B -m pytest tests/unit/qa tests/unit/runs tests/contract/stream -q -p no:cacheprovider` → **79 passed**。**10 Markdown / 60 本地链接 / 29 工单（4 ready、1 review、24 blocked）检查与 `git diff --check` 通过**。主动 Markdown LSP 10 文件 unavailable（client 未 ready），不宣称 clean；完整限制见证据。形状检查脚本的 BOM/native 引号错误已修，不属于业务 Red/Green。
- **限制**：只做 proposed Contract 与用例设计，不修改业务源码/公开 schema/路由/依赖/迁移或预算默认值；计划测试未实施，不验收工具运行时/真实图/恢复/live/GATE。未跑全量/Web/Compose。QA 回归使用包含已有源码改动的工作区，不能作为这些改动的独立验收。
- **下一步**：02-A 待消费者/Owner 签认；默认 02-B/DR-010 预算策略与受控 Fixture 提案，然后 02-C 依赖验证/锁定申请；未批准前 02-D~H 不开业务实现。

### 2026-10-02 — 按当前进度将 SPEC 转为 Tickets

- **范围 / Accountable**：M00 文档治理；新增 `progress/tickets/spec-1.1-remaining.md` 与变更 `progress/changes/20261002-M00-spec-to-tickets.md`，同步父票索引、NEXT-DEV-1.18、验收矩阵执行引用、M00 与根进度。已提交实现基线 `8cd4727`；现有 6 个业务源码修改/用户未跟踪文件均未纳入本刀。
- **结果**：29 张细化票（23 Agent、4 跨域缺口、2 人工/环境余量），每票场景/异常、唯一 Accountable、依赖、范围/数据、计划测试、DoD/证据与不做项；SPEC 覆盖和八项 P0 门禁映射齐全。原 ND-AGENT-01 done 与历史完成票不重开；其余 Agent 父票仍 blocked，5 张 ready 只允许 Contract 调研/提案与 Red 设计，不授权业务实现。
- **验证**（Python 3.12.10 / pytest 9.1.1；Windows PowerShell 5.1.22621.4391）：`.venv/Scripts/python -B -m pytest tests/contract --ignore=tests/contract/stream -q -p no:cacheprovider` → **48 passed**；`.pi/artifacts/spec-to-tickets/check-tickets.ps1` 检查本地链接/29 唯一票号/索引/唯一 Owner/5 张前置 ready/显式子票依赖无环/计划测试与 DoD/FR-AGENT 与 P0 映射通过；`git diff --check` 通过。检查脚本保存在仓库 `.pi/artifacts/`，未写 C 盘。
- **限制**：只整理工单/执行计划，不新增业务源码、依赖、迁移、路由或 schema；计划测试未实施/运行，未重跑全量业务/Web/Compose/live。依赖图检查只证明显式子票边无环，人工审批/父票收口仍需 Owner 证据；TBD-P0/DR-010/011 与所有 GATE 未关闭。
- **下一步**：ND-AGENT-02-A → 02-B → 02-C。后台指标/任务、运行时持久审计、密码生命周期/实际签名下载验收分别由 ND-GAP-01~04 追踪；业务复核与 ECS apply 继续人工/环境 blocked。

### 2026-10-02 — ND-AGENT-01 答案安全回归与修复

- **范围 / Accountable**：M05 `qa/**`、Run HTTP 提交/发布接线、RunBundle 注解、QA 测试；M04 `retrieval/providers.py` 兼容响应协议错误子类；M11 pipeline/证据；M00 Contract/工单/矩阵及恢复入口同步。无公开 schema、路由、依赖、迁移或预算默认值变化；ADR-009 既有门禁落地。
- **Red/修复**：考勤证据 + 百万美元奖金原始回归 **1 failed（实际 answered）→ passed**；严格 JSON/全量 Claim 绑定/完整 Chunk 原文支持门禁，任一不通过整份不发布；Final Markdown 只从 verified Claims 渲染并转义主动标记；Verifier 故障/非法决策/修改事实 fail closed；格式/权限错误不切备用模型。HTTP 先 commit 结果再发 token/citation/completed，失败候选无公开正文/Claims/Citation。
- **验证**（Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6；Node v26.8.2 / npm 11.19.1）：`.venv/Scripts/python -B ops/run_grouped_tests.py --skip-web` → **661 passed, 19 skipped**（M05 79；pipeline 272 passed / 18 skipped），ruff/compileall passed；受影响单元额外 ruff passed。Web test **18 passed**，前台/后台 Fake **13/8 passed**，typecheck/lint passed；HTTP/SQL/导出针对组 **31 passed**。
- **证据 / 限制**：`evidence/agent-m05/nd-agent-01.md`；原始日志 `.pi/artifacts/nd-agent-01/grouped-tests.log`。主动 LSP push-only 结果未确认 clean，解释器/SQL execute 误报有 disposition，不把空诊断当验收；Python/Node 既有弃用警告保留。只接受完整原文（DR-004 未关闭），Claims/Citation 仍未事务入库、无跨进程 outbox/租约/checkpoint/live 验收；不宣称 ReAct 或 GATE verified。
- **下一步**：ND-AGENT-02 先冻结工具/模型/预算和锁依赖 Contract；DR-010、恢复 Contract、DR-011 依赖票继续 blocked。用户已有未跟踪文件未纳入本刀。

### 2026-10-02 — ReAct 正式规格与冲突文档迁移

- **范围**：M00 规格/契约说明/场景/矩阵，M05 目标与进度；同步根入口、模块责任、开发计划/工单、历史技术方案地位。SPEC-1.1 + AGENT-SPEC-1.0 + ADR-009；旧 LangGraph 暂缓/ND-W3-09 已 superseded。
- **实现事实**：无业务源码/依赖安装/迁移/路由新增；SSE schema 仅描述更新，结构仍 v0.1；答案漏洞、LangGraph/tool calling/checkpoint 均待实施。历史 Wave 3 证据与用户未跟踪文件未删除。
- **验证**（Python 3.12.10 / pytest 9.1.1）：`.venv/Scripts/python -B -m pytest tests/contract --ignore=tests/contract/stream -q -p no:cacheprovider` → **48 passed**；`.venv/Scripts/python -B -m pytest tests/unit/qa tests/unit/runs tests/contract/stream -q -p no:cacheprovider` → **30 passed**。PowerShell 本地链接检查 **21 Markdown / 73 links passed**；10 个 FR-AGENT ID 在专项/矩阵/场景均可追踪；JSON 结构对比确认只改 SSE stage 描述。
- **静态/限制**：`git diff --check` 在修正新增 Markdown 行尾空格后 **通过**。合并调用 `pytest tests/contract tests/unit/qa tests/unit/runs` 因既有根/stream conftest 同名导入冲突出现 **5 collection errors**，按仓库分组方式分开通过，不改测试绕过。Markdown LSP 未就绪、JSON LSP 探测不确定，不能把空诊断当 clean；Markdown 缓存剩余旧表样式提示不作 Agent 验收。未跑全量/Web/真实供应商/新 Agent 场景，不代表新需求通过。
- **下一步**：ND-AGENT-01 先写安全 Red；DR-010、恢复 Contract、DR-011 未冻结时，对应后续切片保持 blocked；GATE-P0 全部 unverified。

以下日志为当时实现/计划快照，其“暂缓”“下一刀”不覆盖当前顶部目标。

### 2026-09-14 — 企业 Golden Set v0.3 脱敏摘录（ND-P0-01 填写）

- **完成**：批准 `20260914-M11-golden-set-enterprise-fill.md`；由 `Golden Set测试用例/` 生成 `retrieval/v0.3-enterprise.json`（`source=human`，`annotated_desensitized`，120 条，十层各 12）。省略合同编号、银行账号、纳税人号、手机、邮箱、身份证和薪酬。评测入口对非空集做 Fake Keyword 诊断，仍打印 `GATE-P0-002 unverified`。不冻结阈值，不启用 LLM judge。Accountable：M11 评测/证据，M04 fixture 路径。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`.venv/Scripts/python ops/run_grouped_tests.py --skip-web` → **608 passed, 19 skipped**（pipeline 268 passed / 18 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。`python ops/run_golden_set.py --enterprise` → 120/120 诊断通过，stderr 仍为 `GATE-P0-002 unverified`（退出码 0，不是 GATE 通过）。
- **限制**：标注人是会话记录，不是业务部门双人复核；检索器仍是 Fake Keyword；阈值仍 TBD-P0。
- **下一步**：Owner 提供 SSH/安全组/磁盘后实施 ND-STG-04 ECS apply，或 live Embedding/rerank 冒烟。

### 2026-09-14 — 企业 Golden Set 标注规范与空 schema（ND-P0-01 工程前置）

- **完成**：批准 `20260914-M11-golden-set-enterprise-schema.md`；入库 `ANNOTATION.md`（§10.8 十层、100~150、每层 ≥10、禁止改名 v0.2）；空集 `retrieval/v0.3-enterprise.json`（`source=human`，0 条，`awaiting_annotation`）；评测入口 `ops/run_golden_set.py`（默认合成；`--enterprise` 报告空集且非 GATE 通过）。不合成问句，不标 `GATE-P0-002` / `NFR-QUAL-*` verified。Accountable：M11 规范/评测，M04 fixture 路径。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`.venv/Scripts/python ops/run_grouped_tests.py --skip-web` → **608 passed, 19 skipped**（pipeline 268 passed / 18 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。`python ops/run_golden_set.py --enterprise` 报告 `awaiting_annotation` / `gate=unverified`（退出码 2）。
- **限制**：企业集仍 0 条；阈值仍 TBD-P0；空 schema ≠ 人工标注完成。
- **基线**：tag `M11-v0.25.0`（`5d883c4`）。
- **下一步**：Owner 提供低敏规章制度与标注人后填写 v0.3，或提供 SSH/安全组/磁盘后实施 ND-STG-04 ECS apply。

### 2026-09-14 — Playwright 十页 opt-in（ND-W3-10）

- **完成**：批准 `20260914-M11-playwright-ten-pages.md`；同一 `PIVOT_REQUIRE_PLAYWRIGHT=1` 覆盖 SPEC 十页；夹具播种共享文档与普通用户；UserShell sr-only「管理后台」供键盘/客户端跳转（不改 Cookie `Secure`）。CI 默认 skip。不标 `GATE-P0-005 verified`。Accountable：M11 测试/ops，M09 sr-only 入口，M10 只消费既有后台页。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`.venv/Scripts/python ops/run_grouped_tests.py --skip-web` → **603 passed, 19 skipped**（pipeline 263 passed / 18 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。opt-in `python ops/run_playwright_login.py` → **11 passed**（登录 2 + 十页 5 + 常驻 4）。`npx tsx ../tests/e2e/user/test_user_web.mjs` → **13 passed**；web typecheck/lint 通过。
- **限制**：CI 不启动 uvicorn/Next/Chromium；HTTP 本机栈上全页刷新依赖 refresh Cookie，测试走客户端跳转；`/admin/metrics` `/admin/tasks` 仍未挂；Chrome/Edge 版本仍 TBD-P0；GATE-P0 全部 unverified。
- **下一步**：人工标注企业 Golden Set，或 Owner 提供 SSH/安全组/磁盘后实施 ND-STG-04 ECS apply。

### 2026-09-14 — 真实解析库 extra（ND-W3-03）

- **完成**：批准 `20260914-M07-native-parsers.md`；`worker` optional extra `parse`（PyMuPDF / python-docx / python-pptx / openpyxl）；`PIVOT_PARSER=native` 时装配真实库注册表；未装 extra 失败闭环，不静默回退启发式。缺省 `local` 仍为启发式 PDF + stdlib OOXML。错误码沿用 `FR-DOC-004`。扫描件仍本地拒绝（OCR 属 P2）。Dockerfile / CI 安装 `worker[celery,parse]`；Compose example 仍占位 `local`。不冻页数/大小。Accountable：M07 解析器/extra，M11 Dockerfile/CI/bootstrap。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`.venv/Scripts/python ops/run_grouped_tests.py --skip-web` → **601 passed, 14 skipped**（M07 79；M00-M03 96；pipeline 261 passed / 13 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。
- **限制**：CI 用库生成的微型夹具，不是企业文档；缺省仍启发式；不冻页数/大小；OCR 属 P2；GATE-P0 全部 unverified。
- **下一步**：ND-W3-10 Playwright 十页已完成；Owner 提供 SSH/安全组/磁盘后实施 ND-STG-04 ECS apply，或人工标注企业 Golden Set。

### 2026-09-14 — SSE 长连接推送与前端去缓冲（ND-W3-08）

- **完成**：批准 `20260914-M05-sse-long-connection.md`；`POST /runs` 立即返回 `received`，BackgroundTasks 执行编排并 commit；`GET /runs/{id}/events` 按帧推送、keepalive 注释、反缓冲响应头，`Last-Event-ID` 补发保持。M08 `followRunEvents` 非终态断线续订；Next `app/api/v1/runs/[id]/events` 透传上游 body。uvicorn 长连接 opt-in（`PIVOT_REQUIRE_SSE_LIVE=1`，CI 默认 skip）。不冻 SSE 预算，不把 Redis 当事实源。Accountable：M05 SSE 端口，M08 client/Route Handler，M09 对话页消费 follow，M11 pipeline/证据。
- **验证**（main，2026-09-14，Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）：`.venv/Scripts/python ops/run_grouped_tests.py --skip-web` → **577 passed, 14 skipped**（M05 30；M00-M03 96；pipeline 254 passed / 13 skipped；perf 11 passed / 1 skipped）；ruff / compileall 通过。`npm --prefix web test` → **18 passed**；`npx tsx tests/e2e/user/test_user_web.mjs` → **13 passed**；typecheck/lint 通过。
- **限制**：keepalive 轮询不是冻结的 SSE 预算；CI 不启动 uvicorn/Next；Claim/Citation 仍不入库；LangGraph extra 仍暂缓；GATE-P0 全部 unverified。
- **下一步**：ND-W3-03 真实解析库，或 Owner 提供 SSH/安全组/磁盘后实施 ND-STG-04 ECS apply，或人工标注企业 Golden Set。

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
