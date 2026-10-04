# ND-AGENT-02-C 隐藏目录证据上传修正

- 日期：2026-10-04
- 状态：既有候选验证流程缺陷修正；不发布依赖或改变业务 DoR
- Accountable / 申请人：M11 主线会话；M03 同步依赖验证进度
- 修改前基线：`60a6455`，`main`，工作区 clean
- 原契约：既有 `candidate-ubuntu.yml` 手动候选验证入口；公开 contract-v0.1 不变

## 背景与范围

固定的 actions/upload-artifact v4.6.2 默认排除隐藏文件及隐藏目录中的文件。候选流程将全部材料写入 `.pi/artifacts/nd-agent-02-c/ubuntu-ci-*`，但未设置 `include-hidden-files`，因此即使验证通过，上传步骤仍可能无文件可归档，仅产生 warning。

在已有非递归上传白名单上增加 `include-hidden-files: true`。保持本次 trial 的 `*.json` / `*.log` / `*.txt` 三个路径、7 天保留、always 失败归档、手动确认、只读权限及固定 Actions commit 不变。不上传整个 `.pi`、wheel、venv、用户配置或项目私有资料，不增加联网业务、依赖、迁移或 API。

## 测试与兼容

沿用已存在的 `test_FR_AGENT_009_ci_workflow_artifacts_exclude_environments_and_wheels` 契约边界，增加隐藏目录选项断言；既有路径白名单/非递归/保留期断言继续执行。Red 为选项缺失，Green 为明确启用隐藏目录读取。无需新增或修改公共契约、状态机、安全政策或 ADR。

受影响路径：`.github/workflows/candidate-ubuntu.yml`、`tests/security/ops/test_FR_AGENT_009_candidate_ci.py`、M03/M11 进度、根进度/交接和证据。验证见 [证据](../../evidence/agent-m03/nd-agent-02-c/hidden-artifacts.md)。

## 审核与限制

本轮只修正已记录的归档意图，不代签任何消费者/Owner/安全结论。未推送或 dispatch，未验证真实 Hosted artifact 上传。02-C 仍 review，0 ready / 5 review / 24 blocked；DR-010/011、TBD-P0 与 GATE 不变。下一步仍须 Owner 审查待验证 ref，然后批准远端手动验证并归档真实 run 和 artifact。
