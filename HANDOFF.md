# 问枢 Pivot 会话交接清单

> **日期**：2026-10-04\
> **本轮修改前基线**：`497c15c`（`main`；02-C公开供应链诊断）；`75cf0aa`为M11私有配置回归修正前基线；`3460a2f`为Ubuntu独立候选锁/双重建前基线；`93c24fe`为清华源Ubuntu源码构建/候选解析前基线；`8009841`为02-C离线供应链材料前基线；`93f7e50`为Debian bookworm runtime候选锁前基线；`d613318`为04-A前基线；`20e8f15`为03-A前基线；`8782c7c`为本机Linux环境配置前基线；`bfe8971` 是此前技术审核基线；ND-AGENT-01 前基线 `7ed2748` 和旧 `M11-v0.25.0` 为历史记录。\
> **性质**：当前规格迁移与历史实现交接。需求以 SPEC-1.1 / `spec/AGENT_SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 MODULE-SPEC-1.2 / `AGENTS.md` 为准。\
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

本机环境见 [Linux runbook](ops/runbook-local-linux.md) 和 [2026-10-03 证据](evidence/local-linux-20261003.md)：独立 Python 3.12.10/.venv、Node/npm、现有 extras/Playwright 与 loopback Web/API 已配置；Python661/19skip、Web18/13/8、浏览器11 passed。Docker daemon/组权限可用，但代理授权与四容器镜像仍 blocked；memory readyz=503、搜索为空，不宣称真实 RAG 就绪，不代签 02-C 或任何 GATE。

1. 工作区：`/home/lumina888/Projects/Pivot`，分支：`main`。`E:/AI Project/Pivot` 是历史 Windows 路径；不要新建 worktree。02-C 的 Debian bookworm runtime 与 Ubuntu 源码诊断候选已有独立锁/双重建/20 probes，**正式 Ubuntu CI 与签认未完成**，见 [bookworm 证据](evidence/agent-m03/nd-agent-02-c/linux-bookworm.md)与 [Ubuntu 证据](evidence/agent-m03/nd-agent-02-c/linux-ubuntu.md)。
2. 读：`AGENTS.md` → `SPEC.md` → `spec/AGENT_SPEC.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. ND-AGENT-01 已完成；02-A [内部提案](progress/changes/20261002-M05-agent-internal-contract.md)、02-B [预算提案](progress/changes/20261002-M05-agent-budget-contract.md)、02-C [依赖/锁定申请](progress/changes/20261002-M03-agent-dependencies-lock.md)均 review 待签认、未发布。02-C Windows 双隔离环境/候选哈希锁验证完成，原环境与业务未接入。下一步优先 **02-A/B/C 签认、Linux 锁验证及预算映射确认**，业务仍 blocked；03-A [恢复提案](progress/changes/20261003-M00-agent-resume-contract.md)与独立proposed schema/62项shape检查已提交、review待签认，未发布API；04-A [持久化提案](progress/changes/20261003-M03-agent-persistence-contract.md)与独立schema/173项shape检查也已提交、review待7项签认；前置提案已全部提交，0 ready/5 review/24 blocked，下一步签认/目标平台锁/批准PG环境。目标已改为 LangGraph 受控 ReAct，旧固定主图/暂缓申请/ND-W3-09 已由 ADR-009 取代。旧 ECS apply/live 检索票不再是默认路径。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / **企业 Golden Set 脱敏摘录** / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / sqlite 导出任务 / sqlite refresh/会话 / sqlite Run/EventLog / eager Celery / Compose Celery fixture / Fake MinIO worker ingest / Compose api 共享存储注入 / Fake worker Qdrant upsert / Compose api celery 注入 / Compose Qdrant·Redis 注入 / Compose 登录限流注入 / **Wave 3 夹具收口** / PATCH 角色 HTTP / **ingest 共用 HTTP Embedding** / **Fake HTTP Writer** / **Fake MinerU 解析器** / **staging Compose overlay** / **sqlite refresh/Conversation** / **sqlite Run/EventLog** / **SSE 长连接夹具** / **真实解析库 extra** / **opt-in Playwright 十页** 标成 `GATE-P0 verified`。`wave-3-integrated` **不等于** P0 通过。

## 1. 产品现状

### 当前目标与未完成项

- SPEC-1.1 / AGENT-SPEC-1.0 / ADR-009 已接受；FR-AGENT-005 的 ND-AGENT-01 安全子集已实现，完整 FR-AGENT 仍未验收。
- 当前仍为纯 Python 线性 RAG，无 LangGraph/tool calling/checkpoint；自由 Markdown 背书漏洞、引用绑定/支持门禁与校验前草稿泄漏已修复。
- 本刀采用严格 JSON + 完整 Chunk 原文支持门禁 + 受控渲染 + HTTP 提交后发布；Verifier/非法格式/权限拒绝不放行、不切备用供应商。未安装新依赖或新增恢复路由。
- 预算 DR-010、恢复接口/错误映射 Contract、checkpoint DR-011 仍阻断对应后续票。
- ND-AGENT-01 Python **661 passed / 19 skipped**；M05 **79 passed**；Web **18/13/8 passed**，typecheck/lint、ruff/compileall passed；证据 `evidence/agent-m05/nd-agent-01.md`。完整事务/outbox/语义 Judge/跨进程恢复仍待后续票。
- 02-A 只交付 proposed 设计：4 个内嵌 schema 的 **10 正向/28 负向形状检查**，公共契约 **48 passed**、既有 QA/Run/SSE **79 passed**；11 组运行时 Fake/Red 尚未实施，7 个消费者均 pending；证据 `evidence/agent-m05/nd-agent-02-a.md`。
- 02-B 只交付 proposed 预算设计：2 个内嵌 schema、有限 unit_fake_only Fixture/预期账本、18 组未实施 Red 与 7 个 pending 签认项；证据 `evidence/agent-m05/nd-agent-02-b.md`。
- 本轮 02-C：Windows CPython 3.12.10 候选 LangGraph 1.2.12/core 1.6.6/openai adapter 1.6.7/checkpoint 4.2.0/PG Saver 3.1.2；111 个 wheel 精确哈希、双 venv offline 重建与 **11 技术探针**，候选环境旧回归 **661 passed/19 skipped**。None 恢复 limit+2、strict 字典 passthrough、serde 不脱敏须由业务 gate 承接；证据 `evidence/agent-m03/nd-agent-02-c.md`。六项审核 pending，未改 pyproject/正式锁/CI/镜像，Linux/真实 PG/live 未验收；原 `.venv` 与六处已有源码/用户未跟踪文件保留，不纳入提交。以下数字为 2026-09-14 历史记录。

### 历史 Wave 3 实现

Python **608 passed / 19 skipped**（Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）。Web **18 passed**（M08）+ **13 passed**（M09 Fake）。opt-in Playwright **11 passed**。

- Wave 3 夹具已收口：Compose api/web/worker（profile `app`）共享 PG/MinIO/Qdrant/Redis；api 注入 celery ingest 与登录限流阈值/窗口；worker 可接 Qdrant。
- `PIVOT_STORAGE=postgres` 时用户目录、文档事实、导出任务、hashed refresh、Conversation 与 Run/EventLog 可跨装配（CI sqlite）；Claim/Citation 仍不入库。
- `POST /runs` 立即返回 `received`；`GET /runs/{id}/events` 按帧长连接推送；Next SSE Route Handler 去缓冲；uvicorn 长连接 opt-in（`PIVOT_REQUIRE_SSE_LIVE=1`，CI 默认 skip）。
- HTTP 缺省仍进程内 ingest。
- `PATCH /admin/users/{id}` 已处理 `status` / `role` / `reset_password`。
- `PIVOT_PARSER=local|mineru|native`；缺省 local 启发式/stdlib；`native` 需 `worker[parse]`；扫描件 OCR 属 P2。
- `PIVOT_REQUIRE_PLAYWRIGHT=1` 覆盖 SPEC 十页；CI 默认 skip。
- Golden Set 默认仍为 v0.2-synthetic 120 条；v0.3-enterprise 为 120 条脱敏摘录（Fake Keyword 诊断）。GATE-P0 全部 unverified。
- tag `wave-3-integrated` 仅表示夹具收口，不等于 P0 通过，不得宣称 production-ready。
- ND-STG-04 overlay：`docker-compose.staging.yml` + nginx 默认 `127.0.0.1:80` 反代 web；8GiB limits fixture；未 SSH。

## 2. 历史 2026-09-14 切片

1. ND-P0-01 填写：120 条脱敏项目摘录（十层各 12）
   - 变更：`progress/changes/20260914-M11-golden-set-enterprise-fill.md`
   - 证据：`evidence/wave3-m11/golden-set-enterprise.md`
   - 测试：`tests/integration/pipeline/test_NFR_QUAL_golden_set_enterprise.py`
   - 生成：`ops/golden_set_enterprise.py`（源目录不入库原文）

## 3. 已知缺口（按优先级）

1. HTTP 缺省仍请求内 ingest；无对象字节下载 HTTP（契约如此）；Claim/Citation 仍不入库；`/admin/metrics` `/admin/tasks` HTTP 仍未挂
2. 企业 Golden Set 仍是脱敏摘录 + Fake Keyword，不是业务复核或 live 检索；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank/Writer/MinerU 冒烟；staging ECS 未 apply
3. `must_change_password` 不入库；version.idempotency_key 未入库；初始密码传递机制仍 TBD-P0；OCR 属 P2

## 4. 当前下一刀

最新[02-C公开供应链诊断](evidence/agent-m03/nd-agent-02-c/supply-chain-public-check.md)：109个Linux候选公开包名/版本OSV查询无命中、已知漏洞正/负对照通过；不等于零漏洞/完整覆盖或签认。补充grpcio-tools/langsmith对应上游标签主LICENSE全文、固定commit/blob及静态版本绑定，sdist hash/PKG-INFO核验，wheel缺文本事实保留；官方不完整下载未采用，清华完整字节hash匹配。本机完整Python**905 passed/19 skipped/0 failed**、ruff/compileall与离线报告复核通过；未安装包、改业务/锁/CI或发送项目数据。正式Ubuntu CI/角色锁/来源签名/许可证兼容/CVE/遥测/内嵌库与消费者/Owner签认仍pending，不解锁业务/DR/TBD-P0/GATE。

此前[M11私有配置回归修正](evidence/wave3-m11/private-env-regression.md)：原`.env`存在性误报已修，改为Git索引与仓库真实忽略来源检查；新增9项临时仓库用例，强制暂存/规则缺失/注释/本地或全局排除不能放行。本机Python分组**905 passed/19 skipped/0 failed**、harness exit0、ruff/compileall通过，未读删用户配置。测试要求Git可执行文件和工作区元数据；未重跑目标候选/正式Ubuntu CI/Web/真实PG/live，不解除Agent签认或GATE。历史下文失败数字保持原事实记录，不能作为本轮结果。

此前 [Ubuntu独立候选锁](evidence/agent-m03/nd-agent-02-c/linux-ubuntu.md)：2026-10-04新Ubuntu容器/目录原生重新解析109 wheel、独立生成proposed锁；bookworm缓存字节按本轮report逐个hash核验后复用，两个全新venv离线hashes安装/pip check通过、错误哈希dry-run exit1、技术探针各20 passed。完整Python分组895 passed/1 failed/19 skipped、ruff/compileall通过；唯一失败仍是根`.env`存在性断言，未读删配置或放宽测试。工具等待600秒超时后容器继续执行，最终wait/inspect exit1/running=false。manifest显式记录source-built diagnostic/not-hosted-ci；正式Ubuntu CI/Actions工具链/角色锁/供应链/消费者与Owner签认仍pending，02-C review、0 ready/5 review/24 blocked及DR/GATE不变。

上轮 [清华源Ubuntu诊断](evidence/agent-m03/nd-agent-02-c/linux-ubuntu-tuna.md)：Python3.12.10源码20.5MB/3.4秒下载，摘要与官方HTTPS Sigstore bundle相符（未验完整签名链）；Ubuntu源码构建/运行库/stdlib/pip25.0.1验证通过，清华pip原生dry-run解析109个wheel，与bookworm候选包集合/版本/报告哈希差异0。清华源只用于临时容器，宿主/主.venv/业务不变。源码构建不等于Actions artifact或Hosted CI；未做独立Ubuntu锁/双重建/探针/分组，仍待工具链/供应链/消费者与Owner审核，02-C review与0 ready/5 review/24 blocked不变。

2026-10-03 [02-C供应链材料](evidence/agent-m03/nd-agent-02-c/supply-chain.md)：109个bookworm wheel哈希/身份相符，107检出随包许可证文本，grpcio-tools/langsmith 2项待补齐；PyMuPDF双许可/psycopg LGPL等仅记录声明，不代签安全/法律结论。Ubuntu24.04镜像检查通过，Actions Python3.12.10构建两次240秒下载超时，未生成Ubuntu锁/CI证据。bookworm verify既有探针20 passed；其余受影响回归见证据收尾。许可证兼容性/CVE/遥测/原生库/消费者与Owner签认仍pending，0 ready/5 review/24 blocked不变，不写blocked业务实现。

2026-10-03 [bookworm 候选锁](evidence/agent-m03/nd-agent-02-c/linux-bookworm.md)：`python:3.12.10-slim-bookworm` digest `sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db`。109 个 wheel 与 Windows 候选版本差 0，仅少 colorama/pywin32；双 venv 离线重建、哈希负向 exit 1、技术探针各 20 passed。分组 895 passed/1 failed/19 skipped，失败仍是根 `.env` 存在性断言。未发布依赖，Ubuntu CI/供应链/镜像构建未做，02-C 仍 review。

2026-10-03 [04-A证据](evidence/agent-m03/nd-agent-04-a.md)：AGENT-PERSISTENCE-0.1-draft.1 proposed/review；Saver写入fencing、已确认checkpoint/版本/累计账本、原Message事实事务/outbox、unknown尝试/敏感治理/回滚候选均待审核。173项shape通过，分组895 passed/**1 failed**/19 skipped；已有staging本机`.env`存在性断言失败保留，不读取/删除配置或修宽测试。ruff/compileall通过；LSP Python导入home/venv错配记录，不冒称整体clean。未改业务/公开Contract/依赖/迁移，真实PG/Saver/恢复未验收，7项签认pending。

2026-10-03 [03-A证据](evidence/agent-m00/nd-agent-03-a.md)：M00已提交恢复公开Contract提案，schema62与旧公共契约48、QA/Run/SSE79 passed；全量分组724 passed/**1 failed**/17 skipped（已有staging测试要求根`.env`不存在，与gitignored本地配置冲突），静态ruff/compileall通过。未读取/删除用户配置或改无关测试；不宣称全量通过。LSP导入为home/项目venv错配，Markdown不可用限制如实记录。无业务路由/客户端/依赖/迁移变更。

本轮 [02-A/B/C 技术审核](evidence/agent-m03/nd-agent-02-abc-review.md)完成映射修订：02-B AGENT-BUDGET-0.1-draft.2 proposed，独立累计执行前门禁；Windows 技术 probes20 passed（原11+新9），不代表 BudgetGate/业务图通过。旧 Windows 环境当时无 Docker。2026-10-03 已在 Debian bookworm 容器完成 runtime 候选，Ubuntu CI、供应链、镜像构建与签认仍未完成；[原生执行单](evidence/agent-m03/nd-agent-02-c/linux-validation.md)因此只是部分执行。没有代签/发布/生产数值冻结，D～H 保持 blocked。

ND-AGENT-01 done；02-A/B/C review（proposed 未签认/未发布）。优先 **签认、Linux 锁验证与预算映射确认**；不要因形状/Fixture 算术/依赖探针或旧回归通过变 done。03-A恢复与04-A持久化Contract均proposed/review，各7项消费者/Owner签认pending；0张ready、5张review/24张blocked，没有业务实现解锁。全部前置 Contract/DR-010/锁依赖批准后才推进 02-D~H，随后 03 → 04 → 05。预算/恢复/checkpoint/live 环境不满足时保持 blocked。

不要把脱敏摘录或合成 120 条标成 GATE-P0-002 通过。

## 5. 恢复命令

```bash
cd /home/lumina888/Projects/Pivot
source .venv/bin/activate
git switch main
git log --oneline --decorate -8
python ops/run_grouped_tests.py --skip-web
python ops/run_golden_set.py --enterprise
```

opt-in 十页：`python ops/run_playwright_login.py`（需 `api[playwright]` 与 Chromium）。

## 6. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。
