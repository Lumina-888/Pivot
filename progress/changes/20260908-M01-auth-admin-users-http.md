# 变更申请：扩展 /api/v1/auth/change-password 与 /admin/users

- **日期**：2026-09-08
- **申请人**：Wave 3 集成会话（M01 HTTP 适配扩展 + M11 pipeline 测试）
- **背景**：登录/刷新/退出已合入。管理后台用户页与首次改密需要 `POST /auth/change-password`、`GET/POST /admin/users`、`PATCH /admin/users/{id}`。领域已有改密、创建、停用/启用；列表投影与 HTTP 未挂。
- **原契约/现状**：`contract-v0.1` 已定义上述路由；`create_app(auth=...)` 已挂载 `build_auth_router`。AdminUser 需要 `created_at`；初始密码传递机制仍为 `TBD-P0`。
- **拟变更内容**：
  - M01 `AuthService` 增加管理员用户列表投影；创建时写入 `created_at`；HTTP 响应不含 `password_hash` / `initial_password`；
  - M01 `auth/http.py` 扩展：`POST /auth/change-password`（Bearer，204）；`GET/POST /admin/users`、`PATCH /admin/users/{id}`（仅管理员；PATCH 本切片只接受 `status`，对齐前台停用/启用）；`pagination: null`；
  - M11 pipeline HTTP 测试覆盖改密失效旧会话、普通用户 403、创建用户不回显口令、停用后不可登录；
  - 不挂 metrics/tasks、会话 CRUD、预览/下载；不冻结限流阈值；不把 `argon2-cffi` 写入 pyproject。
- **影响模块**：M01（router 与投影）；M11（pipeline 测试）。M00 契约已存在。
- **兼容方案**：既有登录/刷新/退出不变；默认 `create_app()` 仍不挂 `/api/v1`。
- **测试 ID**：`test_FR_AUTH_004_http_change_password_*`、`test_FR_AUTH_004_http_admin_create_user_*`、`test_FR_AUTH_003_http_disable_user_*`、`test_FR_RBAC_001_http_admin_users_*`。
- **是否触发 ADR**：否。
- **审核结果**：2026-09-08 Wave 3 集成会话 **批准**。
