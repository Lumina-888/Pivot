# ND-AGENT-02-A/B/C 技术审核与签认跟进

- **日期 / 基线**：2026-10-02；main `bfe8971`。
- **状态**：技术自审/预算映射修订完成；Linux 验证 blocked，消费者/Owner 签认 pending；02-A/B/C 仍 review，02-D～H/父票仍 blocked。
- **责任 / 路径**：M05 内部/预算提案，M03 依赖及候选 probe，M11 技术证据/环境执行单，M00 治理/进度同步。本次没有修改业务源码、正式依赖、CI/镜像、公开契约、生产策略或迁移。
- **工作区**：保留开场六处源码修改（qa draft/orchestrator/verifier/writer、retrieval providers、runs http）与全部既有未跟踪文件，均不纳入本次提交。旧 QA 回归在含这些改动的工作区执行，不单独验收它们。

## 1. Linux 环境核查：未通过执行前置

| 本机命令 / 检查 | 实际结果 | 判定 |
|---|---|---|
| `Get-Command docker,wsl,uv,bash,python -ErrorAction SilentlyContinue` | 无 docker；存在 wsl.exe/bash.exe；uv 存在但不是 Linux 运行时 | 没有可用 Docker 路径，不执行安装或 build/up |
| `wsl --list --verbose` | exit 1；`Wsl/0x80070422` | WSL 不可用，不能生成原生 Linux 证据 |
| Bash `uname -a` | exit 1；`Bash/0x80070422` | 没有可用 Linux shell |

没有尝试启用 Windows 服务、安装 WSL/Docker、SSH/ECS 或远程 CI；没有提供/批准远程目标。本次**未生成 Linux 锁，也没有 Linux passed 声明**。[原生 Linux 执行单](nd-agent-02-c/linux-validation.md)补齐平台预检、版本约束/native markers、独立 wheel report/哈希、双离线重建、错误哈希、技术 probes 与旧回归/镜像/安全审查。命令仅计划，Python 内嵌片段可本地做语法检查，不等于 Linux 执行成功。

现有锁一致性 probe 增加平台检查：Linux 必须显式提供原生 manifest；Windows 默认仍消费原 111 项候选锁。拒绝用 Windows manifest 冒充 Linux，不跳过锁一致性测试。

## 2. 预算与内部 Contract 技术审核

[02-B](../../progress/changes/20261002-M05-agent-budget-contract.md)升为 **AGENT-BUDGET-0.1-draft.2**（仍 proposed）；§4.1 明确独立累计图账本、执行 epoch/步身份、节点体前预扣、同一步多节点与 provider 独立计量、interrupt/未知执行保留消费、只读重放与实际重执行区分、同步/异步/恢复/取消边界。`min(技术上限, 剩余量)` 仅是技术熔断提示，`limit-2` 或事后统计不得代替硬门禁。

[新增技术探针](nd-agent-02-c/test_budget_mapping_probe.py)使用公开 StateGraph 接口和合成 InMemorySaver，不运行 Pivot Agent/预算实现：

- 同步/异步 × limit=1/2/3：新输入各执行 limit 个 tick；None 恢复均额外执行 limit+2 个 tick（6 项）。
- 同步/异步 Command：节点 interrupt 前缀各进入两次，合成 state 消费只从 7 提交到 8 一次；证明“返回时更新 state”不能计量实际进入次数（2 项）。
- 同一 super-step=1 同时执行两个节点；图步数不是模型/工具调用数。debug 仅观察结果，不是派发前接缝（1 项）。

[02-A](../../progress/changes/20261002-M05-agent-internal-contract.md)保留服务端单工具/严格参数/调用 ID、白名单 State 与全角色外发/发布要求；补充最终 wire schema 必须验明 strict/additionalProperties，serde 不是脱敏器、遥测必须关闭。版本仍 AGENT-INTERNAL-0.1-draft.1（不变更字段/接口）。02-G 仍须证明锁定框架的执行前门禁接缝，或走另案审核；本轮不预写 BudgetGate/真实业务图来制造 Green。

## 3. 签认清单（无代签，无批准）

本主线会话只记录技术自审，**不冒充各模块 Owner/业务/运维或独立审查人**。用户要求完成签认工作不等于各 pending 条目已得到批准，特别是未完成的 Linux 与安全证据。最终签认应引用提案版本、输入 commit、证据及明确许可范围；只有 `approval_ref` 字符串不构成授权。

| 提案 | 技术审核结果 | 仍需签认 / 阻断 | 当前状态 |
|---|---|---|---|
| 02-A INTERNAL draft.1 | 严格最终 wire schema/消息关联/state 白名单与完整原文支持策略兼容；有探针及旧回归，不是消费者运行时验收 | M00/M01/M03/M04/M05/M06/M11 确认 Interface 与安全/字段来源责任；Owner 确认实施范围 | review，全部消费者仍 pending，未发布 |
| 02-B BUDGET draft.2 | min-only 映射不充分，§4.1 已修订；所有收费 attempt/unknown/恢复共享账本，无新默认 | M05/M11 确认可实现前置接缝；M00/M06/M03/M01 确认兼容/账本/授权；Owner/业务/运维确认许可及成本/期限语义 | review，未签认；DR-010 未关闭 |
| 02-C DEPENDENCIES draft.1 | Windows 候选/strict/serde/同步异步 canary 与离线重建证据可供审查 | Linux runtime/CI 原生验证、镜像/角色/build 工具链、许可证/CVE/遥测/反序列化、artifact 来源/保留与回滚；M03/M05/M11/M01/M00/Owner 审核 | review，Linux blocked，未发布正式锁 |

**放行条件**：上述审批与证据齐备 → M00 发布明确内部 Contract/依赖版本 → 对应受控执行策略范围获批准 → 逐票重新核 DoR/Red。不能一次性把 D～H 改 ready；DR-011/恢复/持久化/live 各有独立门禁。生产预算数值仍 TBD-P0，全部 GATE 未关闭。

## 4. 本轮验证与限制

环境：Windows AMD64 CPython 3.12.10；候选 verify/rebuild venv，pip 25.0.1、pytest 9.1.1、ruff 0.16.6。TEMP/TMP/pytest/缓存/日志均放仓库 `.pi/artifacts/nd-agent-02-c/`；关闭 tracing，无真实模型、密钥、文档或 PG。

命令（仓库根；两项 probe 不进入默认业务分组）：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TEMP = "$PWD/.pi/artifacts/nd-agent-02-c/tmp"
$env:TMP = $env:TEMP
$env:LANGCHAIN_TRACING_V2 = 'false'
$env:LANGSMITH_TRACING = 'false'
$py = '.pi/artifacts/nd-agent-02-c/verify-venv/Scripts/python.exe'
& $py -B -m pytest evidence/agent-m03/nd-agent-02-c/test_dependency_probe.py evidence/agent-m03/nd-agent-02-c/test_budget_mapping_probe.py -q -p no:cacheprovider --basetemp=.pi/artifacts/nd-agent-02-c/pytest-mapping-review-2
```

初次与平台校验变更后的 verify 技术探针均 **20 passed**（原11+新增9），rebuild 解释器重跑也 **20 passed**，无 skips。不得把技术 canary 标作运行时 Red/Green 或预算验收。

其余本轮命令/实际结果：

| 命令（`$py` 同上；仓库根） | 实际结果 |
|---|---|
| `& $py -B -m pytest tests/contract --ignore=tests/contract/stream -q -p no:cacheprovider --basetemp=.pi/artifacts/nd-agent-02-abc-review/pytest-contract` | 公共契约 **48 passed**；contract.log |
| `$env:PYTHONPATH="$PWD/api/src;$PWD/worker/src"` 后 `& $py -B -m pytest tests/unit/qa tests/unit/runs tests/contract/stream -q -p no:cacheprovider --basetemp=.pi/artifacts/nd-agent-02-abc-review/pytest-qa-source` | 旧 QA/Run/SSE **79 passed**；qa-source.log |
| `& .pi/artifacts/nd-agent-02-c/rebuild-venv/Scripts/python.exe -B -m pytest evidence/agent-m03/nd-agent-02-c/test_dependency_probe.py evidence/agent-m03/nd-agent-02-c/test_budget_mapping_probe.py -q -p no:cacheprovider --basetemp=.pi/artifacts/nd-agent-02-abc-review/pytest-rebuilt` | 第二隔离环境 **20 passed**；rebuilt-probe.log |
| `& $py -B .pi/artifacts/nd-agent-02-abc-review/check_wrong_platform.py` | 合成错平台 manifest 被平台 assertion 拒绝，预期 **exit 1 / 1 failed**；wrong-platform.log；不是 Linux 测试 |
| `& $py -B .pi/artifacts/nd-agent-02-abc-review/check_review.py` | **2 schema / 4 正向 / 49 缺字段负向**；14 Markdown/120本地链接/2 Linux内嵌 Python 片段语法；29票状态/版本边界 passed |
| `& $py -B -m ruff check --no-cache --config api/pyproject.toml evidence/agent-m03/nd-agent-02-c/test_dependency_probe.py evidence/agent-m03/nd-agent-02-c/test_budget_mapping_probe.py .pi/artifacts/nd-agent-02-abc-review` | **All checks passed** |
| `git diff --check` | passed；仅现有 autocrlf 提示，不改换行策略 |

辅助检查脚本/日志位于本仓 `.pi/artifacts/nd-agent-02-abc-review/`，不提交。首次 QA 直接调用遗漏 PYTHONPATH，**10 collection errors（No module named pivot）**；按既有分组 harness 的源码注入规则重跑通过，不 editable 安装、不改业务。首次 artifact ruff 仅辅助脚本超长行 E501，已修复后通过。没有全量分组/Web/live/PG/容器/Linux/镜像运行，也没有依赖安全全量结论。

LSP：主动 probe 为 push-only **inconclusive**，不能确认 clean；主环境未批准安装 langgraph/core/openai adapter/psycopg-pool 导致导入诊断。32 条 MissingImports 经隔离解释器实际 import/20 probes 核实为解释器选择限制，使用 session false-positive disposition（无 ignore 注释、无生产依赖变更）；不声称 LSP 全量 clean。静态依据是候选解释器的 ruff 与语法检查。

## 5. 下一步需要的输入

1. Owner 提供/批准原生 Linux 环境（本机 WSL/Docker 恢复需 Owner 手动操作，或提供受控 Linux 执行目标/CI 许可）。先完成执行单，不用交叉解析替代。
2. 审核人逐项填写签认：姓名/角色、准确版本、证据链接、准许范围、残余风险、结论/时间。拒绝或附条件时继续 review；不能签认不存在的证据。
3. 未满足前不修改正式依赖/运行配置或 02-D～H 业务源码；02-A/B/C review、父票 blocked、DR-010/011 与所有 TBD/GATE 保持未关闭。
