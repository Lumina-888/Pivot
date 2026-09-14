# Wave 3 M01 PATCH 角色 / 重置密码 HTTP 切片限制

环境：FastAPI TestClient + 进程内 `AuthService` / 内存 UserDirectory。不启动 Compose；不把 Fake HTTP 标成 GATE verified。

- `PATCH /api/v1/admin/users/{id}` 处理契约已有 `role` / `status` / `reset_password`；仅管理员。
- 角色变更抬升 `token_version`、撤销 refresh，并审计 `auth.role_change`（metadata 仅 `from`/`to`）。
- `reset_password=true` 生成一次性初始密码，经 HTTPS JSON `initial_password` 返回；GET/POST 不回显；审计不含口令。
- 未知用户 `RESOURCE_NOT_FOUND`；普通用户 `AUTH_FORBIDDEN`。
- `must_change_password` 仍不入库；初始密码传递机制仍为 `TBD-P0`（本切片未冻结通道）。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-005 | unverified | Fake HTTP 管理员 PATCH 不是上线传输/审计/密钥安全验证 |

`implemented`（PATCH 角色/重置 HTTP）≠ `verified`。
