# 变更申请：opt-in Playwright 浏览器登录

- **日期**：2026-09-09
- **申请人**：Wave 3 主线会话（M11 E2E + M03 可选依赖）
- **背景**：composition root 与 Next `/api/v1` rewrite 已合入。员工登录页仍无真实浏览器证据。MODULE_SPEC / CI 禁止默认启动 Compose/uvicorn。Postgres Alembic 冒烟已用 `PIVOT_REQUIRE_COMPOSE=1` 做 opt-in。
- **原契约/现状**：登录 Fake fetch E2E 已绿；无 Playwright；`GATE-P0-005` unverified。
- **拟变更内容**：
  - M11 增加 `test_FR_AUTH_001_browser_login_reaches_home`：Chromium 打开 `/login`，提交 bootstrap 管理员，进入首页；错误密码统一「账号或密码错误」；
  - 默认 **skip**；仅 `PIVOT_REQUIRE_PLAYWRIGHT=1` 时拉起本机 `127.0.0.1` uvicorn factory + `next dev`（不 Compose）；
  - `ops/run_playwright_login.py` 设置该环境变量并跑上述测试；
  - M03 增加 optional extra `playwright`，不写入默认/`http` extra；CI **不**安装浏览器、**不**启动 uvicorn；
  - **不**冻结 Chrome/Edge 版本（`NFR-UX-005` / `TBD-P0`）；**不**标 `GATE-P0-005 verified`。
- **影响模块**：M11（测试、ops、证据）；M03（pyproject extra）；M08/M09（只消费既有登录页与 rewrite，本切片不改页面）。
- **兼容方案**：分组 CI 行为不变（多 2 个 skip）；Fake fetch E2E 不变。
- **测试 ID**：`test_FR_AUTH_001_browser_login_reaches_home`、`test_FR_AUTH_002_browser_invalid_credentials_are_generic`、`test_NFR_OBS_playwright_login_runner_is_opt_in`、`test_GATE_P0_005_not_verified_by_playwright_login`。
- **是否触发 ADR**：否。
- **审核结果**：2026-09-09 Wave 3 主线会话 **批准**。
