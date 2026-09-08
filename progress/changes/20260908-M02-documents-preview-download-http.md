# 变更申请：扩展 /api/v1/documents 预览与下载

- **日期**：2026-09-08
- **申请人**：Wave 3 主线会话（M02 领域 + HTTP 适配；M11 pipeline 测试）
- **背景**：文档上传/列表/详情/版本/重试/删除 HTTP 已合入。OpenAPI 仍缺预览/下载实现。管理后台与员工文档页需要授权后的原文流；对象存储端口目前只有 `put/exists/delete`，无法读回字节。
- **原契约/现状**：`contract-v0.1` 已定义 `GET /documents/{id}/preview`、`GET /documents/{id}/download`（`application/octet-stream`）；`create_app(documents=..., auth=...)` 已挂载文档 router。领域 `get_detail` 已按角色隐藏 tombstone/非共享。导出 HTTP 走短时 URL，不代理原文。
- **拟变更内容**：
  - M02 `ObjectStore` 增加 `get(key) -> bytes | None`；内存 Fake 同步实现；
  - M02 `DocumentService.open_content`：按 `get_detail` 同等可见性重新授权（猜测 ID / 非共享 / 用户看 tombstone → `RESOURCE_NOT_FOUND`）；代理当前或仍有对象的版本字节；清洗文件名；不返回 `storage_key` / MinIO 地址；
  - M02 `documents/http.py` 增加 preview（`inline`）与 download（`attachment`）路由；Bearer；`Cache-Control: private, no-store`；错误仍走统一错误包；
  - M11 pipeline HTTP 测试覆盖未认证、猜测 ID、共享可读、内部/tombstone 对用户 404、下载头与原文一致、清理后 404；
  - 不改 `create_app` 挂载条件；不接真实 MinIO；不冻结分页/文件大小 `TBD-P0`；不标 `GATE-P0 verified`。
- **影响模块**：M02（端口、领域、router）；M11（pipeline 测试与进度）。M00 契约已存在。
- **兼容方案**：既有上传/列表/详情行为不变；默认 `create_app()` 仍不挂 `/api/v1`；缺少对象字节时 404，不泄露存储键。
- **测试 ID**：`test_FR_RBAC_003_preview_*`、`test_FR_RBAC_003_http_preview_*`、`test_FR_RBAC_003_http_download_*`、`test_FR_DOC_007_download_unavailable_after_cleanup`、`test_FR_DOC_007_http_user_cannot_preview_tombstone`、`test_NFR_SEC_015_download_filename_is_sanitized`。
- **是否触发 ADR**：否。
- **审核结果**：2026-09-08 Wave 3 主线会话 **批准**。
