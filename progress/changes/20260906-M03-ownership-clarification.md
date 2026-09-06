# 变更申请：M03 依赖配置与 shared 路径所有权澄清

- **日期**：2026-09-06
- **申请人**：M03 数据基础与持久化会话
- **背景**：M03 需要声明 SQLAlchemy/Alembic/pytest 依赖并实现不透明 ID、UTC 工具。`MODULE_SPEC §5.1` 将 `api/pyproject.toml`、`api/src/pivot/shared/**` 列为 M03 Owner；`§3 M03 允许修改` 仅显式列出 `api/src/pivot/shared/ids.py`、`time.py`，未列出 pyproject 或 shared 包初始化文件。
- **原契约**：M03 允许路径以 `MODULE_SPEC §3` 为准；共享路径 Owner 表（§5.1）补充 M03 拥有 `api/pyproject.toml` 与全部 `api/src/pivot/shared/**`。
- **拟变更内容**：本模块在自身分支创建 `api/pyproject.toml`、`api/src/pivot/shared/__init__.py`，并只实现允许列出的 `ids.py`、`time.py`；不修改公共错误码、契约或其他模块源码。
- **影响模块**：M03（写入）；M01/M02/M04/M05/M06/M07（以后通过包依赖与 shared 工具消费）。
- **兼容方案**：`api/pyproject.toml` 只声明可安装依赖和 pytest 配置，不改变公开 API；shared 工具保持独立、无外部服务依赖。若治理会话要求调整所有权，后续仅迁移文件位置，不改变接口。
- **测试 ID**：`test_M03_opaque_ids_are_non_sequential_strings`、`test_M03_utc_helpers_return_timezone_aware_utc` 及 M03 数据集成测试。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置）；ID 具体编码仍为实现内部细节，不升级为公共契约。
- **审核结果**：2026-09-06 Wave 0 退出评审 **批准**。已写入 `MODULE_SPEC.md` §3 M03 允许路径，与 §5.1 的 `api/pyproject.toml`、`api/src/pivot/shared/**` Owner 对齐。
