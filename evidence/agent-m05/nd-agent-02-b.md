# ND-AGENT-02-B 预算 Contract 提案证据

- **日期 / 基线**：2026-10-02；`E:/AI Project/Pivot`，main `715e6d5`。
- **Accountable / 范围**：M05 DR-010 预算/累计用量提案；M00 治理同步，M11 证据路径。提案 [AGENT-BUDGET-0.1-draft.1](../../progress/changes/20261002-M05-agent-budget-contract.md)。
- **结论**：02-B review（proposed 待消费者/Owner 签认），不是 done/发布或运行许可。02-A/B 未签认、02-C 未锁依赖；DR-010/011、公开恢复 Contract、TBD-P0 与所有 GATE 保持未关闭。

## 交付

- 明确必需预算维度/单位/策略版本、全角色预扣与派发/结算边界、unknown 保守占用、主备/重试/补证共享账本、期限与恢复不重置。
- 明确 rewrite≤2/clarification≤1、累计图 super-steps 与单次 recursion_limit 分工、完整 JSON 观察限长、授权历史窗口/上下文、部署与 principal 并发槽位。
- 2 个内嵌拟议 schema、1 个 unit_fake_only 有限 Fixture 与预期账本、18 组运行时 Red 设计及 7 个 pending 签认项；示例数值不是生产默认或已批准受控配置。
- 记录旧 ProviderCall 内存/浮点成本端口缺预扣、attempt、unknown 和持久对账能力，后续由 02-F/04-A/E 承接，不本轮改业务接口。

## 验证命令与结果

环境：Windows PowerShell 5.1；仓库 `.venv`，Python 3.12.10、pytest 9.1.1、ruff 0.16.6、jsonschema 4.26.0、PyYAML 6.0.3。

| 命令 | 结果 / 能证明什么 |
|---|---|
| `.venv/Scripts/python -B .pi/artifacts/nd-agent-02-b/check-proposal.py` | 2 schema、5 正向接受/175 负向拒绝；有限 Fixture 占用 3 calls/810 tokens/1100 microunits、余量 3/1190/28900 算术通过；10 Markdown/71 本地链接、29 票（3 ready/2 review/24 blocked）通过 |
| `.venv/Scripts/python -B -m pytest tests/contract --ignore=tests/contract/stream -q -p no:cacheprovider --basetemp=.pi/artifacts/nd-agent-02-b/pytest-contract-01` | **48 passed**；既有发布契约，不验收新预算 |
| `.venv/Scripts/python -B -m pytest tests/unit/qa tests/unit/runs tests/contract/stream -q -p no:cacheprovider --basetemp=.pi/artifacts/nd-agent-02-b/pytest-qa-01` | **79 passed**；既有 QA/Run/SSE，不验收新 Agent |
| `.venv/Scripts/python -B -m ruff check --no-cache --config api/pyproject.toml .pi/artifacts/nd-agent-02-b/check-proposal.py` | **passed**；仅 artifact 脚本静态检查，首轮 1 个 E501 行长已修复 |
| `git diff --check` | **passed**；既有 LF/CRLF 提示不影响结果 |

检查脚本/原始日志仅保存在仓库 `.pi/artifacts/nd-agent-02-b/`，不入本切片提交、不写 C 盘。形状与示例算术不执行 BudgetGate/状态机/恢复/真实图，不能算业务 Red→Green。

主动 `lens_diagnostics(source=lsp, scope=paths)` 检查 10 个 Markdown 全部 unavailable（marksman/typos client 未 ready）；0 diagnostics 不代表 clean。artifact 脚本另有 3 个辅助 ast-grep finding：JSON 解析未 try/except 为验证器有意 fail-fast，2 个 yield-from iterable 提示指向显式 Iterator[dict] 递归生成器（正向/负向检查实际执行通过）。这些不是业务问题，未以吞异常或改检查结果消除；LSP 不宣称 clean。

日志：`proposal-check.log`、`contract-tests.log`、`qa-tests.log`、`ruff.log` 位于上述 artifact 目录；pytest 临时产物显式放同目录，不使用 C 盘 TEMP。

## 限制与下一步

- 本轮不实现或运行新的预算/工具/图/interrupt/PG/并发门禁，不修改公开 schema/路由/错误码/状态、依赖、迁移、业务源码或生产默认。
- 提案的运行时测试仅设计，未实施；shape 合法不证明跨字段关系、审批真实性、ID 幂等、授权、计费上界或恢复一致性。
- 未跑全量分组/Web/Compose/live/ECS；没有这些路径变更。既有回归基于包含 6 个已有业务源码改动的组合工作区，不作为这些改动的独立验收；已有源码与用户未跟踪文件均保留且不纳入本提交；收尾 `Get-FileHash -Algorithm SHA256` 确认 6 个源码文件 hash 与开场完全一致。
- 下一刀 02-C Python 3.12 框架/消息/适配/checkpointer 依赖验证与锁定申请；02-A/B 待签认，生产数值须实测/ADR，02-D~H/父票继续 blocked。
