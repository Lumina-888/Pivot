# 变更申请：M06 观测审计包初始化文件

- **日期**：2026-09-06
- **申请人**：M06 导出、审计与成本元数据会话
- **背景**：`MODULE_SPEC §3 M06` 允许修改 `api/src/pivot/observability/audit/**`，作为 M01 `AuditSink` 的持久化适配。Python 包需要父级 `api/src/pivot/observability/__init__.py` 才能导入子包。
- **原契约**：M06 允许路径显式列出 `api/src/pivot/observability/audit/**`，未列出父包 `__init__.py`。
- **拟变更内容**：新增空的包标记文件 `api/src/pivot/observability/__init__.py`，不声明公共 API、不引入依赖、不修改其他模块。
- **影响模块**：M06（写入）；M01 可通过 `pivot.observability.audit.AuditLogSink` 接入，无需改 M01 路径。
- **兼容方案**：仅包初始化；若治理要求观测根包改 Owner，可迁移文件位置而不改 sink 接口。
- **测试 ID**：`test_FR_AUDIT_001_accepts_m01_audit_sink_drafts`
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置）。
- **审核结果**：待集成会话审核。
