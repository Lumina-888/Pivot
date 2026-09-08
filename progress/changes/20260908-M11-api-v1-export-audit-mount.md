# 变更申请：M11 挂载注入的 /api/v1/exports 与 /admin/audit-events

- **日期**：2026-09-08
- **申请人**：Wave 3 集成会话（M06 HTTP 适配 + M11 create_app 挂载）
- **背景**：Run/SSE HTTP 已合入。M06 领域已有 ExportService / AuditService（内存存储、短时公开下载地址、脱敏列表）。前台导出入口与后台审计页需要 `POST /exports`、`GET /exports/{id}`、`GET /admin/audit-events`。MODULE_SPEC 规定 `http/**` 不得实现导出/审计业务。
- **原契约/现状**：`contract-v0.1` 已定义上述三条路由；`create_app` 仅挂认证、文档、搜索与 Run/SSE。导出创建响应 `state=requested`（202）；GET 返回状态与短时 `download_url`；审计分页为 `TBD-P0`。
- **拟变更内容**：
  - M06 `api/src/pivot/exports/http.py`：`build_exports_router(exports, auth)`，Bearer 后把 Principal 投影为 Actor，只做 HTTP 适配；创建 202；GET 不含 `storage_key` / Prompt / MinIO 内部地址；不挂对象字节下载（契约仅状态+短时 URL）；
  - M06 `api/src/pivot/audit/http.py`：`build_audit_router(audits, auth)`，管理员只读列表；忽略 `page`/`page_size` 并返回 `pagination: null`；非管理员 `AUTH_FORBIDDEN`；
  - M11 `create_app(exports=..., auth=...)` 与 `create_app(audits=..., auth=...)`：各自与 AuthService 同时注入才挂载，缺任一 fail-closed；
  - MODULE_SPEC 注明导出/审计 HTTP 适配位于 `exports/http.py`、`audit/http.py`（M06）；
  - 不挂预览/下载、改密、会话 CRUD；不冻结导出 TTL / 审计分页。
- **影响模块**：M06（router）；M11（挂载与 pipeline 测试）；M00 契约已存在。
- **兼容方案**：默认 `create_app()` 不变；领域单测不依赖 FastAPI。
- **测试 ID**：`test_FR_EXPORT_001_http_*`、`test_FR_EXPORT_002_http_*`、`test_FR_EXPORT_003_http_*`、`test_FR_AUDIT_002_http_*`、`test_FR_RBAC_001_http_exports_*`、`test_NFR_OBS_auth_only_app_does_not_mount_exports`。
- **是否触发 ADR**：否。
- **审核结果**：2026-09-08 Wave 3 集成会话 **批准**。
