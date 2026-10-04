# ND-AGENT-02-C：压缩候选 wheel 错误脱敏回归

- **日期 / 基线**：2026-10-04 / main `b84670a`，开场 clean。
- **Accountable / 范围**：M11；`ops/check_candidate_integrity.py`、`tests/security/ops/test_FR_AGENT_009_candidate_integrity.py`、证据与进度；M03 同步候选验证进度。
- **状态**：现有验证工具修正，不发布依赖、公开 Contract 或 Agent 业务能力。
- **来源**：SPEC §0.4/§10/§11.4；[原工具接口记录](20261004-M11-candidate-integrity-tool.md)。

## 范围与接口

沿用已登记的 `check_candidate(manifest, project_root, wheelhouse)` 与 CLI 接口：材料不可读或非法时必须抛出脱敏 `IntegrityError`，CLI 返回 `invalid` JSON、exit 1，不输出 traceback、原始材料或路径。

当前 wheel METADATA 读取依赖标准库 ZIP 解压。损坏的压缩流可能抛出未被捕获的底层异常。先用合成压缩 wheel 复现，在重新计算测试材料摘要后测试解压错误路径，避免测试提前停在 hash mismatch。只补齐异常处理与正负向回归，不放宽哈希/身份检查，不安装、提取或执行 wheel。

测试边界保持原工具的两个公开接口；测试 ID 沿用 `test_FR_AGENT_009_candidate_*`。真实候选材料只作只读复核，不代表来源可信、压缩资源安全、依赖审批或 Agent 验收。没有新增资源阈值或生产默认。

## 兼容与门禁

沿用 `unreadable_or_invalid_material` 分类，无新 CLI 字段、公开错误码、业务状态或接口。不改锁、manifest、pyproject、CI、业务、用户配置或主环境。无需新增 ADR；02-C review、消费者/Owner/安全签认、DR-010/011、TBD-P0 与所有 GATE 均不变。

## 验证

新增9项合成压缩流用例，Red4 failed/5 passed（DEFLATE/LZMA函数与CLI失败）→Green安全组67 passed。原环境Python970 passed/19 skipped/0 failed、harness exit0、ruff/compileall通过，两Python文件主动LSP clean；Windows111项材料、bookworm/Ubuntu各109个缓存wheel复核通过。未重跑候选容器/正式CI/Web/真实PG/live，签认/业务DoR/DR/GATE不变。完整命令与限制见[切片证据](../../evidence/agent-m03/nd-agent-02-c/compression-errors.md)。
