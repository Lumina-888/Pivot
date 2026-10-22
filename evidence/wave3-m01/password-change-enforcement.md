# ND-GAP-03 证据：首次改密落库与服务端强制

日期：2026-10-22。基线：GAP-02 合并后的 main。契约记录：`progress/changes/20261022-M01-password-change-persistence-enforcement.md`。本证据为 sqlite 替身验证；迁移在真实 PG 上的执行由 CI 的 db_pg 套件覆盖。非 GATE-P0 verified。

## 侦察结论（改前事实）

1. 领域层标志齐全：创建用户与管理员重置时置真、改密轮换时置假（auth/service.py 的 create_user、reset_password、_rotate_password）。
2. PG 适配不落库：`db/users.py` 文件头自述该标志「is not a persisted User column」，读出恒假、写入丢弃；`users` 表无此列。PG 装配下首次改密强制不存在。
3. 强制咽喉为 `AuthService.authenticate()`：各业务路由均经它换 Principal；改密流程内部也调它，可单点加检查并给改密留显式放行参数。
4. 登录响应此前不含该标志，前端无从据此跳转。

## 实现摘要

1. 迁移 `45f1c8bda305`（接 `14fcf89c4926`）：users 表加 `must_change_password` 布尔列，非空、服务端默认 false；模型同步加列。
2. `db/users.py`：读映射改读真实列；写路径两处都补齐——更新走 `_apply`、新建走 save 的逐字段构造（侦察时只改 _apply 会漏掉新建路径，验收测试首跑即抓到并已修复）。
3. `auth/errors.py` 新增 `AUTH_PASSWORD_CHANGE_REQUIRED`（HTTP 403，auth/http.py 状态表已登记）。
4. `AuthService.authenticate()` 新增关键字参数 `allow_password_change`（默认 False）：标志置真且未放行时抛上述错误；`change_password` 内部调用显式放行。
5. `LoginResult` 新增 `must_change_password` 字段，登录与刷新响应体同步输出。

## 验证

1. 新增 `tests/integration/db/test_M01_password_change_lifecycle.py` 两项：`test_FR_AUTH_004_first_change_required_after_restart`（管理员建号后以新目录与新服务实例读回标志为真；登录响应标志为真且 authenticate 被专用错误码拦截；改密路径可达且改后标志落库为假、重新登录放行；管理员重置后标志复置、拦截复现）与 `test_FR_AUTH_003_reset_revokes_existing_sessions`（重置后旧访问令牌因版本不一致被拒、已存刷新会话被吊销）。
2. 全量分组回归、ruff 与 compileall 全绿（本地执行 `ops/run_grouped_tests.py --skip-web`）。
