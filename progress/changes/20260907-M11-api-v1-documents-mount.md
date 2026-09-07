# 变更申请：M11 挂载注入的 /api/v1 文档上传与列表路由

- **日期**：2026-09-07
- **申请人**：Wave 3 集成会话（M02 HTTP 适配 + M11 create_app 挂载）
- **背景**：`/api/v1/auth/login|refresh|logout` 已合入。M02 领域服务已实现上传校验、幂等、tombstone 与隔离存储，但无 HTTP。MODULE_SPEC 规定 `api/src/pivot/http/**` 不得实现业务路由。需要把 OpenAPI `GET/POST /api/v1/documents` 接到 `DocumentService`，并保持未注入时 fail-closed。
- **原契约/现状**：`contract-v0.1` 已定义 `/documents` 列表与上传；`create_app(auth=...)` 仅挂认证；默认 `create_app()` 不挂 `/api/v1`。FastAPI extra `http` 尚未包含 `python-multipart`，无法解析 multipart 上传。
- **拟变更内容**：
  - M02 新增 `api/src/pivot/documents/http.py`：`build_documents_router(service, auth)`，只做 HTTP 适配（Bearer、管理员上传、错误包、multipart），不改状态机；领域服务增加列表投影（非 tombstone、共享库准入），`DocumentRecord` 补 `created_at`/`tags` 供 OpenAPI `DocumentSummary` 使用；
  - M11 `create_app(documents=..., auth=...)`：仅当同时注入 `DocumentService` 与 `AuthService` 时 `include_router`；缺任一则不挂文档路由；
  - M03 `api/pyproject.toml` optional extra `http` 增加 `python-multipart`（multipart 解析，不作为默认依赖）；
  - MODULE_SPEC 注明文档 HTTP 适配位于 `api/src/pivot/documents/http.py`（M02）；
  - 不在本切片挂详情/版本/重试/删除/预览/下载、搜索、问答 SSE 或导出；不冻结分页与文件大小 `TBD-P0`。
- **影响模块**：M02（router 与列表投影）；M11（挂载与 pipeline HTTP 测试）；M03（pyproject extra）；M00（契约已存在，无需改字段）。
- **兼容方案**：默认 `create_app()` 行为不变；领域单测不依赖 FastAPI；未注入文档服务时 `/api/v1/documents` 仍 404。
- **测试 ID**：`test_FR_DOC_001_http_admin_upload_*`、`test_FR_DOC_001_http_user_upload_forbidden`、`test_FR_DOC_002_http_legacy_office_rejected`、`test_FR_DOC_005_http_duplicate_sha_idempotent`、`test_FR_DOC_007_http_list_excludes_tombstone`、`test_FR_RBAC_001_http_documents_require_bearer`、`test_NFR_OBS_health_app_does_not_mount_api_v1_routes`（默认仍成立）。
- **是否触发 ADR**：否。
- **审核结果**：2026-09-07 Wave 3 集成会话 **批准**。
