# 变更申请：M11 挂载注入的 /api/v1 认证路由

- **日期**：2026-09-07
- **申请人**：Wave 3 集成会话（M01 HTTP 装配 + M11 create_app 挂载）
- **背景**：`/healthz` `/readyz` 已合入。M01 领域服务已实现登录/刷新/退出，但无 HTTP。MODULE_SPEC 规定 `api/src/pivot/http/**` 不得实现业务路由。需要把 OpenAPI `/api/v1/auth/*` 接到 `AuthService`，同时保持健康装配不包含业务逻辑。
- **原契约/现状**：`contract-v0.1` 已定义 `/auth/login|refresh|logout`；`create_app()` 默认不挂 `/api/v1`。
- **拟变更内容**：
  - M01 新增 `api/src/pivot/auth/http.py`：`build_auth_router(service)`，只做 HTTP 适配（Cookie、错误包、Bearer），不改状态机；
  - M11 `create_app(auth=...)` 在注入 `AuthService` 时 `include_router`；未注入时仍不挂 `/api/v1`；
  - 不在本切片挂文档/搜索/问答/SSE/导出。
- **影响模块**：M01（router）；M11（挂载）；M00（契约已存在，无需改字段）。
- **兼容方案**：默认 `create_app()` 行为不变；领域单测不依赖 FastAPI。
- **测试 ID**：`test_FR_AUTH_001_http_login_*`、`test_FR_AUTH_002_http_invalid_credentials_uniform`、`test_FR_AUTH_003_http_refresh_and_logout`、`test_NFR_OBS_health_app_does_not_mount_api_v1_routes`（默认仍成立）。
- **是否触发 ADR**：否。
- **审核结果**：2026-09-07 Wave 3 集成会话 **批准**。
