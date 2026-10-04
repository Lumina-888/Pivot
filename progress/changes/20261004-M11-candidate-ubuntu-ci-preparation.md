# ND-AGENT-02-C：Ubuntu 手动候选 CI 验证入口准备

- **日期 / 状态**：2026-10-04 / 本轮实施范围记录；候选验证入口，不是 Contract 或依赖发布。
- **授权 / 基线**：用户在恢复核查后确认继续「02-C 正式 Ubuntu CI 验证准备」；main `4fb1693`，开场 clean。仅授权准备代码与本地检查，本轮不推送或触发远端工作流。
- **Accountable / 路径**：M11：独立 `.github/workflows/candidate-ubuntu.yml`、`ops/prepare_candidate_ci.py`、安全测试及证据；M03：候选材料边界与进度同步。默认 `ci.yml`、业务源码、pyproject、既有锁、迁移、公开 Contract、用户配置和主 `.venv` 不变。
- **来源**：SPEC §0.4/§9/§10，AGENT_SPEC §10，02-C 依赖提案与 [Linux 执行单](../../evidence/agent-m03/nd-agent-02-c/linux-validation.md)。

## 输入、输出与安全边界

沿用现有只读候选核验接口 `check_candidate`。新增准备工具的公共边界是 `prepare_inputs(trial, project_root, environment)`、`write_native_candidate(trial, project_root)` 及 CLI 的 prepare/resolved 阶段；测试通过合成文件与显式环境 Fixture 覆盖这些边界，不运行 Pivot Agent 或供应商。

- prepare：核验已提交 Windows/Ubuntu proposed 材料；只导出版本约束与 roots，不复制 Windows wheel 哈希。实际 CLI 先要求原生 Ubuntu 24.04/x86_64/glibc 2.39/CPython 3.12.10/pip 25.0.1；不符合则拒绝，且不创建目录或访问网络。输出目录必须是仓库 `.pi/artifacts/nd-agent-02-c/` 下的新目录。
- resolved：读取本次原生 pip report，拒绝错平台、包/版本/artifact 漂移、非官方 HTTPS wheel、yanked、重复包或非法摘要；生成本轮独立 proposed/pending manifest 与哈希锁，以及错误哈希的单包 dry-run Fixture。通过现有 checker 再核验生成材料，失败不进入安装。
- 新工作流只支持 workflow_dispatch，需显式确认候选验证；无 push/PR 自动触发，contents:read，不持久化 checkout 凭证，Actions 固定 commit。驱动/验证/重建环境均新建，无 editable 安装、自由升级、模型/PG/Compose/镜像调用。
- 包闭包沿用候选用于技术验证，不是角色/生产锁；原生解析差异必须失败并供审查，不自动换版本修绿。bootstrap 只安装现有候选中固定哈希的 packaging，pip 由 CPython 3.12.10 ensurepip 提供并检查 25.0.1。
- artifact 只收集候选清单/锁/report/有限环境元数据与测试日志，不上传 wheelhouse/venv/用户配置；失败时也保留已有证据。Hosted runner 系统镜像仍会变动，记录实际版本，不宣称完整系统库/来源签名或供应链审批完成。

## 验收与状态

首批测试：`test_FR_AGENT_009_ci_preparation_*`、`test_FR_AGENT_009_ci_report_*`、`test_FR_AGENT_009_ci_workflow_*`。验证实际输入/输出与错误分类、无写入失败、CLI 脱敏、手动触发/固定工具链/隔离安装及 artifact 范围。

本地 Red/Green、分组回归、静态与主动 LSP 结果归档到 [证据](../../evidence/agent-m03/nd-agent-02-c/ubuntu-ci-preparation.md)。本地合成报告通过不等于 Hosted CI 执行成功；不标正式 Ubuntu CI passed。02-A/B/C/03-A/04-A 签认、角色锁、许可证/CVE/遥测/来源与 Owner 审核仍 pending；0 ready/5 review/24 blocked、02-D～H、DR-010/011、TBD-P0 和全部 GATE 不变。无状态机/权限/模型配置变更，不新增 ADR。
