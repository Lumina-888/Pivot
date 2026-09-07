# 变更申请：扩展 /api/v1/documents 详情、版本、重试与删除

- **日期**：2026-09-07
- **申请人**：Wave 3 集成会话（M02 HTTP 适配扩展 + M11 pipeline 测试）
- **背景**：`GET/POST /api/v1/documents` 已合入。管理后台文档页需要详情、版本、重试与 tombstone 删除。领域服务已有 `retry` / `request_delete`，但 HTTP 未挂。预览/下载依赖对象流，不在本切片。
- **原契约/现状**：`contract-v0.1` 已定义 `GET /documents/{id}`、`GET /documents/{id}/versions`、`POST /documents/{id}/retry`、`POST /documents/{id}/delete`；`create_app(documents=..., auth=...)` 已挂载文档 router。
- **拟变更内容**：
  - M02 `DocumentService` 增加详情/版本投影与按文档重试（失败版本 `parse_failed`/`embed_failed` → `queued`）；
  - M02 `documents/http.py` 扩展上述四条路由：Bearer；用户读共享未删文档；管理员读含 tombstone；重试/删除仅管理员；响应不含 `storage_key`；
  - M11 pipeline HTTP 测试覆盖授权、404 猜测 ID、删除立即从列表消失；
  - 不挂预览/下载、搜索、SSE、导出；不改 `create_app` 挂载条件；不冻结分页 `TBD-P0`。
- **影响模块**：M02（router 与投影）；M11（pipeline 测试）。M00 契约已存在。
- **兼容方案**：既有上传/列表行为不变；默认 `create_app()` 仍不挂 `/api/v1`。
- **测试 ID**：`test_FR_DOC_007_http_delete_*`、`test_FR_DOC_006_http_retry_*`、`test_FR_RBAC_003_http_document_detail_*`、`test_FR_DOC_007_detail_*`。
- **是否触发 ADR**：否。
- **审核结果**：2026-09-07 Wave 3 集成会话 **批准**。
