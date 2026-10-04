# ND-AGENT-02-C：离线候选材料一致性工具

- **日期 / 基线**：2026-10-04 / main `fa291b2`，开场 clean。
- **Accountable / 范围**：M11；`ops/`、`tests/security/ops/`、证据；M03 只同步候选进度，根进度与交接同步。
- **状态**：验证工具切片，不发布依赖或 Contract；02-C 仍 review，消费者/Owner/安全签认 pending。
- **来源**：SPEC §0.4/§9.1/§10、[02-C 申请](20261002-M03-agent-dependencies-lock.md)。

## 背景与接口

已有候选锁和 manifest 的复核依赖 `.pi/` 临时脚本，缺少版本化离线入口。本刀只提供只读的一致性检查，不安装、导入或执行候选 wheel，不解析新依赖，不访问网络，不修改 CI、业务、生产配置或正式依赖。

`python ops/check_candidate_integrity.py --manifest <path> --project-root <root> [--wheelhouse <directory>]`：

- 严格读取 JSON，拒绝重复键与 NaN/Infinity 非 JSON 常量；只接受 `proposed/pending` 候选材料。
- 验证锁文本 UTF-8/LF 摘要、严格单版本单哈希条目与 manifest 全量集合一致，拒绝额外 pip 指令、URL、marker、重复规范化包名。
- 使用现有测试工具链的 `packaging` 验证 wheel 文件名的包名/版本；拒绝路径分隔符或非 wheel。
- 只读取已登记的三个项目输入（api/worker pyproject、公共测试 requirements）；拒绝缺项/额外路径/越界 symlink，核验规范化文本摘要。
- 可选 wheelhouse 逐文件只读核验原始字节哈希及唯一 METADATA 包名/版本；不提取 ZIP、不执行代码，不把随包元数据当来源签名。
- 成功返回 JSON/exit 0，明确 `not_dependency_approval`、是否核验 wheel 字节；错误返回脱敏分类/exit 1，不回显原始内容或异常路径。

不检查宿主与候选平台一致性：这是跨平台离线材料检查，不是安装/运行探针。平台、依赖闭包正确性、许可证、CVE、签名、构建来源、Hosted CI、角色锁、预算/恢复与消费者签认仍由原门禁负责。

## TDD 与兼容边界

测试 ID：`test_FR_AGENT_009_candidate_*`；合成临时 wheel/manifest/锁的正向、篡改、遗漏、重复、路径和 CLI 脱敏负向测试，另对三份版本化候选做只读回归。Red 先记录工具缺失，Green 后运行 M11 安全组/完整 Python 分组和静态检查。

不改公开 contract-v0.1、SPEC、状态机、错误码、业务依赖、迁移或 CI。不触发新的 ADR，不关闭 DR-010/011、TBD-P0 或任一 GATE。作者不等于审核批准；工具成功只说明给定材料一致。

## 完成证据

Windows manifest 原缺 `candidate_lock_file`，补齐真实锁文件名；版本和全部wheel/锁哈希不变。新增56项测试通过（含非 JSON 常量3 failed→passed），M11安全组58 passed；Windows111项材料与bookworm/Ubuntu各109个缓存wheel字节/身份复核通过。原环境Python961 passed/19 skipped/0 failed、ruff/compileall及两Python文件主动LSP clean。完整命令/Red/限制见[证据](../../evidence/agent-m03/nd-agent-02-c/integrity-tool.md)。未重跑目标候选/正式CI/Web/真实PG/live，不代签、不解锁业务DoR。
