# 问枢 Pivot 会话交接清单

日期是 2026-10-12。当前入口按 `17ac93a` 同步。第 4 节之后是历史轮次，不是待办。

本文件不是规范源。需求以 SPEC-1.1 和 `spec/AGENT_SPEC.md` 为准。进度以 `PROGRESS.md` 为准。协作以 MODULE-SPEC-1.2 和 `AGENTS.md` 为准。

## 新会话恢复

本机环境见 [Linux runbook](ops/runbook-local-linux.md) 和 [2026-10-03 证据](evidence/local-linux-20261003.md)。Python 3.12.10、Node、npm、现有 extras、Playwright，以及 loopback 上的 Web 和 API，已经配置。当时记录是 Python 661 passed、19 skipped，Web 18、13、8 passed，浏览器 11 passed。

Docker daemon 和组权限可用。代理授权和四容器镜像仍为 blocked。memory 模式的 readyz 是 503，搜索为空。这不表示真实 RAG 就绪，也不代表任何 GATE 通过。

1. 工作区是 `/home/lumina888/Projects/Pivot`，分支是 `main`。`E:/AI Project/Pivot` 是历史 Windows 路径。不要新建 worktree。
2. 阅读顺序是 `AGENTS.md`、`SPEC.md`、`spec/AGENT_SPEC.md`、`MODULE_SPEC.md`、`PROGRESS.md`，然后是本文件的当前入口。
3. 当前基线是 `17ac93a`。02-A、02-B、02-C、03-A 的 contract-v0.2，以及 04-A，已经发布。02-D 至 02-H、03-B、03-C、03-D、03-E，以及 04-B 和 04-C 的框架，已经提交。它们不构成运行批准，也不等于跨进程恢复。
4. 下一刀是 04-C 的后续，以及 04-D 至 04-F。`POST /runs/{id}/resume` 已在 contract-v0.2 发布。单元测试不能标成跨进程恢复或 GATE。
5. 不要冻结 `TBD-P0`。Fake HTTP、存储客户端、合成 Golden Set、企业脱敏摘录、进程内夹具、Compose 文件和 opt-in 测试，都不能标成 `GATE-P0 verified`。`wave-3-integrated` 不等于 P0 通过。

02-C 的 Windows 候选、Linux 候选和 Ubuntu Hosted CI 已有技术验证。证据见 [2026-10-06 CI](evidence/agent-m03/nd-agent-02-c/ubuntu-ci-20261006.md)。Run `37420501217` 已在 `7958feb` 上 success。不要重复安排这次候选 CI。正式角色锁、构建和安全审核仍然 pending。

## 产品现状

SPEC-1.1、AGENT-SPEC-1.0 和 ADR-009 已经接受。ND-AGENT-01 实现了 FR-AGENT-005 的安全子集。完整 FR-AGENT 尚未验收。

LangGraph 工具循环已有开发实现。自由 Markdown 背书、引用绑定、支持门禁和校验前草稿泄漏已经修复。DR-010 的生产数值尚未关闭。04-D 至 04-F 和真实 PostgreSQL 恢复尚未完成。

ND-AGENT-01 的历史证据是 Python 661 passed、19 skipped，M05 为 79 passed，Web 为 18、13、8 passed。证据见 `evidence/agent-m05/nd-agent-01.md`。完整事务、outbox、语义 Judge 和跨进程恢复仍待后续票。

### 已知缺口

1. HTTP 默认仍在请求内 ingest。对象字节下载 HTTP 按契约不新增。04-B 的提交框架已入库，跨进程恢复未完成。`/admin/metrics` 和 `/admin/tasks` 已挂接。指标仍不是持久统计，任务列表仍为空。
2. 企业 Golden Set 仍是脱敏摘录加 Fake Keyword。它不是业务复核，也不是 live 检索。Qdrant 的 100k 索引峰值、新 ECS 备份恢复、live 冒烟和 staging ECS apply 尚未完成。
3. `must_change_password` 不入库。`version.idempotency_key` 尚未入库。初始密码传递机制仍是 `TBD-P0`。OCR 属于 P2。

### 历史 Wave 3

Wave 3 的历史记录是 Python 608 passed、19 skipped。Web 有 M08 的 18 passed，以及 M09 Fake 的 13 passed。opt-in Playwright 为 11 passed。

Compose 的 api、web 和 worker 共享 PostgreSQL、MinIO、Qdrant 和 Redis。`PIVOT_STORAGE=postgres` 时，用户目录、文档事实、导出任务、refresh、Conversation 和 Run 可以跨装配。CI 使用 sqlite。

`POST /runs` 立即返回 `received`。SSE 按帧推送。Playwright 十页、真实解析库 extra 和 100k 检索都是 opt-in，CI 默认 skip。Golden Set 默认是 v0.2-synthetic 的 120 条。v0.3-enterprise 是 120 条脱敏摘录。GATE-P0 全部 unverified。

`wave-3-integrated` 只表示夹具收口。它不等于 P0 通过，也不能称为 production-ready。

## 当前下一刀

以 `17ac93a` 为准。继续 04-C 的恢复逻辑，以及 04-D 至 04-F 的租约、用量对账和故障测试。DR-010 的生产数值尚未关闭。Fake 闭环和单元测试不能标成 GATE。

第 4 节之后的历史记录保留原表述。其中的“待签认”和“0 ready / 5 review / 24 blocked”只描述对应轮次，不是当前待办。

## 恢复命令

```bash
cd /home/lumina888/Projects/Pivot
source .venv/bin/activate
git switch main
git log --oneline --decorate -8
python ops/run_grouped_tests.py --skip-web
python ops/run_golden_set.py --enterprise
```

opt-in 十页使用 `python ops/run_playwright_login.py`。它需要 `api[playwright]` 和 Chromium。

## 纪律

聊天记录不是项目事实。以 commit、tag、`PROGRESS.md` 和测试证据为准。

## 历史轮次

以下段落保留原记录。它们不是当前入口。

> **本轮修改前基线**：`60a6455`（`main`；02-C隐藏目录证据归档修正）；`4fb1693`（`main`；02-C Ubuntu 手动候选 CI 入口准备）；`b84670a`为02-C压缩wheel错误脱敏修正前基线；`fa291b2`为02-C离线候选一致性工具前基线；`497c15c`为02-C公开供应链诊断前基线；`75cf0aa`为M11私有配置回归修正前基线；`3460a2f`为Ubuntu独立候选锁/双重建前基线；`93c24fe`为清华源Ubuntu源码构建/候选解析前基线；`8009841`为02-C离线供应链材料前基线；`93f7e50`为Debian bookworm runtime候选锁前基线；`d613318`为04-A前基线；`20e8f15`为03-A前基线；`8782c7c`为本机Linux环境配置前基线；`bfe8971` 是此前技术审核基线；ND-AGENT-01 前基线 `7ed2748` 和旧 `M11-v0.25.0` 为历史记录。

此前[02-C隐藏目录证据上传修正](evidence/agent-m03/nd-agent-02-c/hidden-artifacts.md)：固定upload-artifact默认排除`.pi/`中的文件，本轮显式允许隐藏目录读取，仍只归档本次trial顶层JSON/log/txt，不上传配置/wheel/venv。既有上传契约Red1 failed→安全组128 passed；完整Python重跑1031 passed/19 skipped/0 failed、harness exit0、ruff/compileall与Python/YAML主动LSP clean。首次180秒工具等待超时已确认无遗留，420秒上限重跑完整通过；已有YAML长行风格限制如实记录。未推送/dispatch/验证Hosted上传，未重跑目标候选/Web/PG/live/镜像；02-C review、0 ready/5 review/24 blocked与所有签认/DR/GATE不变。

此前[02-C Ubuntu 手动候选 CI 入口准备](evidence/agent-m03/nd-agent-02-c/ubuntu-ci-preparation.md)：新增仅workflow_dispatch/确认默认false的Ubuntu24.04/Python3.12.10流程，三Actions固定commit、隔离hash driver/native report/独立候选锁/wheel核验/双离线重建/各20探针/错误hash负向/旧回归。准备工具严格拒绝漂移/非官方URL/畸形JSON/重复项/越界/旧输出。新增61项检查，原环境安全组128 passed、完整Python1031 passed/19 skipped/0 failed、harness exit0、ruff/compileall与工具/测试/YAML主动LSP clean；本机Arch正确拒绝且无输出，主.venv无LangGraph。未推送或dispatch、未跑Hosted CI/目标候选/Web/PG/live/镜像，默认CI/正式依赖/既有候选/业务未改。入口准备不是正式CI passed。

此前[02-C压缩wheel错误脱敏回归](evidence/agent-m03/nd-agent-02-c/compression-errors.md)：修复离线工具未捕获DEFLATE/LZMA解压异常、CLI输出traceback/路径的问题；新增三种压缩格式9项正负向回归，Red4 failed/5 passed→安全组67 passed。原环境完整Python970 passed/19 skipped/0 failed、harness exit0、ruff/compileall与两Python文件主动LSP clean。Windows111项材料、bookworm/Ubuntu各109个缓存wheel复核通过；未改业务/依赖/锁/CI/用户配置。

此前[02-C离线候选一致性工具](evidence/agent-m03/nd-agent-02-c/integrity-tool.md)：新增版本化 `ops/check_candidate_integrity.py` 与56项安全测试；严格核验JSON/锁集合/摘要/固定项目输入/可选wheel字节与METADATA，拒绝重复项/越界路径，错误脱敏。原环境Python961 passed/19 skipped/0 failed。输出明确不等于依赖批准。

此前[02-C公开供应链诊断](evidence/agent-m03/nd-agent-02-c/supply-chain-public-check.md)：109个Linux候选公开包名/版本OSV查询无命中、已知漏洞正/负对照通过；不等于零漏洞、完整覆盖或签认。本机完整Python905 passed/19 skipped/0 failed。正式Ubuntu CI、角色锁、来源签名、许可证兼容、CVE、遥测和内嵌库签认当时仍pending。

此前[M11私有配置回归修正](evidence/wave3-m11/private-env-regression.md)：原`.env`存在性误报已修，改为Git索引与仓库真实忽略来源检查。本机Python分组905 passed/19 skipped/0 failed。未读删用户配置。

此前 [Ubuntu独立候选锁](evidence/agent-m03/nd-agent-02-c/linux-ubuntu.md)：2026-10-04新Ubuntu容器原生重新解析109 wheel。双venv离线hashes安装、错误哈希dry-run exit1、技术探针各20 passed。完整Python分组895 passed/1 failed/19 skipped。失败是根`.env`存在性断言。manifest记录source-built diagnostic，不是Hosted CI。

此前 [清华源Ubuntu诊断](evidence/agent-m03/nd-agent-02-c/linux-ubuntu-tuna.md)：Python3.12.10源码摘要与官方HTTPS Sigstore bundle相符，未验完整签名链。清华pip原生dry-run解析109个wheel，与bookworm候选差异0。源码构建不等于Hosted CI。

2026-10-03 [02-C供应链材料](evidence/agent-m03/nd-agent-02-c/supply-chain.md)：109个bookworm wheel哈希相符，107检出随包许可证文本。Ubuntu固定Python构建两次下载超时，当时未生成Ubuntu锁。许可证兼容性、CVE和遥测当时pending。

2026-10-03 [bookworm 候选锁](evidence/agent-m03/nd-agent-02-c/linux-bookworm.md)：109 个 wheel 与 Windows 候选版本差 0，仅少 colorama 和 pywin32。双 venv 离线重建、哈希负向 exit 1、技术探针各 20 passed。分组 895 passed、1 failed、19 skipped。

2026-10-03 [04-A证据](evidence/agent-m03/nd-agent-04-a.md)：当时 AGENT-PERSISTENCE-0.1-draft.1 为 proposed。173项shape通过。真实PG、Saver和恢复当时未验收，7项签认pending。该状态已被后续发布取代。

2026-10-03 [03-A证据](evidence/agent-m00/nd-agent-03-a.md)：当时恢复Contract为提案。schema62与旧公共契约48、QA、Run和SSE79 passed。无业务路由变更。该状态已被 contract-v0.2 取代。

2026-10-03 当轮结论已被 `17ac93a` 取代。当时 02-A、02-B、02-C、03-A 和 04-A 仍为 review，计数是 0 ready、5 review、24 blocked。不要把这段当作当前待办。

不要把脱敏摘录或合成 120 条标成 GATE-P0-002 通过。
