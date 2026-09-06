# 变更申请：Wave 0 期间 `tests/contract/**` 根级文件由 M00 承载

- **日期**：2026-09-06
- **申请人**：M00 契约治理会话
- **背景**：M00 模块规格（MODULE_SPEC §3 M00「首批 Red/契约测试」与 DoD「至少一个消费者契约测试通过」）要求契约验证测试，但 §5.1 文件所有权表未把 `tests/contract/**` 显式授予任何模块（M05 仅拥有 `tests/contract/stream/**` 子路径）。
- **原契约/现状**：`tests/contract/` 仅有 `.gitkeep` 骨架，无所有者声明。
- **拟变更内容**：
  - Wave 0 期间，`tests/contract/` 根级（conftest.py、requirements.txt、test_contract_*.py）由 **M00** 承载，用于验证 `spec/contracts/**` 与 SPEC 的一致性；
  - 保留 `tests/contract/stream/**` 等既有模块子路径所有权不变（M05 等）；
  - 后续 M11 集成会话可追加消费者级契约测试（命名避免与现有文件冲突）。
- **影响模块**：M00（写入）、M05/M11（消费者，只读引用）。
- **兼容方案**：M00 测试文件命名以 `test_contract_*` 为前缀并位于根级，与模块子目录不重叠；不改变任何公共 schema/字段。
- **测试 ID**：`tests/contract/` 48 项（2026-09-06 全部通过）。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置，仅澄清测试路径所有权）。
- **审核结果**：待 M00/集成维护者审核后归档（保留本文件在 `progress/changes/` 中作为事实记录）。
