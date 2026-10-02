# ND-AGENT-01 答案安全回归与修复证据

- 日期：2026-10-02；工作区 `E:/AI Project/Pivot`、`main`；修改前 HEAD `7ed2748`。
- Accountable M05；M00 Contract/追踪、M04 HTTP transport 分类、M11 集成/回归贡献。
- 来源：SPEC-1.1 FR-QA-002/004、AGENT-SPEC §7、ADR-009；实施 Contract：`progress/changes/20261002-M05-answer-safety.md`。
- 结论：**ND-AGENT-01 done（旧线性迁移基线的安全修复）**；不是 LangGraph/ReAct、语义 Judge 或完整结果持久化验收，GATE-P0 全部 unverified。

## Red → Contract → Green

首个命令：

```text
.venv/Scripts/python -B -m pytest tests/unit/qa/test_FR_AGENT_005_answer_safety.py -q -p no:cacheprovider
```

原负向复现为考勤证据 + “Every employee receives a million-dollar bonus.”：**1 failed / 0.73s**，失败点 `assert bundle.run.state != "answered"`，实际状态 answered、answer_markdown 为无关奖金。修复后首个用例 **1 passed / 0.12s**。

后续分别观察到：非法结构 **7 failed**；数字/金额/日期/条件/否定/版本/限定语截断 **7 failed**；完整引用绑定 **9 failed / 2 passed**；自由 Markdown 渲染及辅助 Verifier **6 failed / 16 passed**；主动 HTML/链接标记渲染 **1 failed**；真实 Stdlib transport 的非 JSON/非对象响应 **2 failed**；非临时 HTTP/未知故障错误 **5 failed**。均先锁定失败再修复，最终全部通过。

根因：Writer 用证据另造 Claims 背书自由 Markdown；Verifier 只判断候选 Chunk 集合；草稿 token/citation 在校验前发送。额外发现 transport 将响应协议错误与权限/格式拒绝当临时故障，触发备用供应商。

## 实现门禁

- 严格 JSON Claims + 服务端候选序号；非法成员、空 Claims、额外字段、重复 JSON key、bool 索引、代码围栏和自由文本整份拒绝，不跳过或补造 Claims。
- 旧可选 markdown 字符串只作兼容输入，永不成为答案；Claim/Citation ID 及定位由服务端生成，同 Chunk 多 Claim 各自完整绑定。
- 验证悬空/候选外引用、唯一 ID、双向绑定、文档/版本/locator 一致性和无孤儿引用。
- 默认只接受与候选完整 Chunk 正文逐字相等的 Claim（忽略首尾空白）；不接受片段截取、数字/否定等改写。任一不通过，整份不发布。
- 辅助 Verifier 不能绕过主门禁、修改事实或返回非法决策；故障/非法格式使用既有 VERIFICATION_UNAVAILABLE、Run uncertain。
- 最终 Markdown 仅由通过的 Claims 渲染，HTML/主动 Markdown 标记转义；失败候选不写入 RunBundle 的公开 Claims/Citation/答案。
- HTTP 显式注入 `persist_result=runs.commit`：结果成功提交后才发送 token/citation/completed；提交失败清空待发布事实，不发送正式答案事件。直接领域调用保留 memory fixture 用法。
- 格式、权限和未知非临时故障不切备用供应商；超时、429、临时 5xx/网络故障保留原受控 failover。M04 增加兼容 JsonHttpError 子类标明无效 HTTP 响应，不改检索策略。

## 验证环境与命令

Python 3.12.10、pytest 9.1.1、ruff 0.16.6、FastAPI 0.141.1；Node v26.8.2、npm 11.19.1。

| 验证 | 命令 | 结果 |
|---|---|---|
| M05 QA/Run/SSE | `.venv/Scripts/python -B -m pytest tests/unit/qa tests/unit/runs tests/contract/stream -q -p no:cacheprovider` | 79 passed |
| 针对 HTTP/SQL/导出 | `.venv/Scripts/python -B -m pytest tests/integration/pipeline/test_FR_AGENT_005_answer_publication.py tests/integration/pipeline/test_FR_QA_001_http_writer.py tests/integration/pipeline/test_FR_STREAM_001_http_runs.py tests/integration/pipeline/test_FR_STREAM_001_http_postgres_runs.py tests/integration/pipeline/test_FR_EXPORT_001_http_exports.py -q -p no:cacheprovider --tb=short` | 31 passed |
| 全量 Python 分组 | `.venv/Scripts/python -B ops/run_grouped_tests.py --skip-web` | **661 passed, 19 skipped**；ruff/compileall passed |
| 受影响单元静态 | `.venv/Scripts/python -B -m ruff check --config api/pyproject.toml api/src/pivot/qa api/src/pivot/runs/http.py api/src/pivot/runs/models.py api/src/pivot/retrieval/providers.py tests/unit/qa tests/integration/pipeline/test_FR_AGENT_005_answer_publication.py tests/integration/pipeline/test_FR_QA_001_http_writer.py` | passed |
| Web 基础 | `npm --prefix web test` | 18 passed |
| Web 前台（cwd web） | `npx --no-install tsx ../tests/e2e/user/test_user_web.mjs` | 13 passed |
| Web 后台（cwd web） | `npx --no-install tsx ../tests/e2e/admin/test_admin_web.mjs` | 8 passed |
| Web 静态 | `npm --prefix web run typecheck`、`npm --prefix web run lint` | passed |
| 差异与文档 | `git diff --check`；Python 本地链接检查 | passed；15 Markdown / 50 relative links |

全量分组：M01 37、M02 28、M04 31、M05 79、M06 26、M07 79、M00/M03 96、pipeline 272、ops 2、perf 11；共新增 **53** 项（M05 +49，pipeline +4）。

原始回归日志：`.pi/artifacts/nd-agent-01/grouped-tests.log`（本机、非入库）；分组执行使用仓库 `.pi/artifacts/nd-agent-01/test-tmp` 为 TEMP/TMP，无真实供应商/密钥/企业原文。Web 使用已安装依赖，不执行会清理 node_modules 的 npm ci。

## 限制与下一步

Owner 最新指令：本部分做完就停止。本会话仅收尾/提交 ND-AGENT-01，不进入 ND-AGENT-02。

- LSP 主动探测未返回错误，但 push-only/silent server 无法确认 clean；其错误解释器导致 FastAPI 导入误报，仓库 .venv 实测可导入。SQL injection 规则误将 QA.execute 当 SQL，已记录 false-positive，不添加源码 suppression。正式静态结论基于 ruff 和编译检查，不以空 LSP 缓存为绿灯。
- 两项 Python TestClient 弃用警告、Node module.register 弃用警告保留；19 个 skip 为既有 opt-in Compose/真实依赖、Playwright/SSE-live/100k 场景，不是本刀绕过测试。
- 只证明当前合法候选内容与发布事实一致；不证明检索质量、跨 Chunk 语义完整性、语义改写支持率或真实供应商能力。DR-004 保持开放，保守门禁可能导致更多 uncertain。
- Claims/Citation 仍未独立事务入库；Run/Message 与公开事件之间的跨进程 outbox/崩溃恢复、租约、取消竞态、历史结果清理未验收。不把一次 commit 回调宣称完整 exactly-once。
- LangGraph/tools/checkpoint 未安装或实现。下一刀 ND-AGENT-02 **先冻结内部工具/模型/预算 Contract、DR-010 Fixture/运行策略与锁依赖**；未满足前业务实现 blocked。ND-AGENT-03/04/05 仍按恢复/DR-011/live 前置阻断。
