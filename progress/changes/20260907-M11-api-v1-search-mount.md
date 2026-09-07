# 变更申请：M11 挂载注入的 /api/v1/search

- **日期**：2026-09-07
- **申请人**：Wave 3 集成会话（M04 HTTP 适配 + M11 create_app 挂载）
- **背景**：文档 HTTP 已合入。M04 领域服务已有 `search_documents`（仅 ready/current/未删/有权）。员工前台搜索页需要 `GET /api/v1/search`。MODULE_SPEC 规定 `http/**` 不得实现检索业务。
- **原契约/现状**：`contract-v0.1` 已定义 `GET /search`；`create_app` 仅挂认证与文档。
- **拟变更内容**：
  - M04 新增 `api/src/pivot/retrieval/http.py`：`build_search_router(service, auth)`，只做 Bearer、查询参数与 `SearchResponse` 投影；分页参数忽略并返回 `pagination: null`（`TBD-P0`）；
  - M11 `create_app(retrieval=..., auth=...)`：仅当同时注入 `RetrievalService` 与 `AuthService` 时挂载；缺任一则不挂；
  - MODULE_SPEC 注明检索 HTTP 适配位于 `api/src/pivot/retrieval/http.py`（M04）；
  - 不挂问答 SSE、导出、预览/下载；不冻结检索 k/RRF/分页。
- **影响模块**：M04（router）；M11（挂载与 pipeline 测试）；M00 契约已存在。
- **兼容方案**：默认 `create_app()` 行为不变；领域单测不依赖 FastAPI。
- **测试 ID**：`test_FR_SEARCH_001_http_*`、`test_FR_RBAC_001_http_search_require_bearer`、`test_NFR_OBS_auth_only_app_does_not_mount_search`。
- **是否触发 ADR**：否。
- **审核结果**：2026-09-07 Wave 3 集成会话 **批准**。
