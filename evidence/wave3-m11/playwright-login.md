# Wave 3 M11 Playwright 浏览器登录限制

环境：默认分组 CI **不**启动 uvicorn/Next/Compose，也不安装 Chromium。

- `test_FR_AUTH_001_browser_login_reaches_home` 仅在 `PIVOT_REQUIRE_PLAYWRIGHT=1` 时运行。
- opt-in 路径：本机 `127.0.0.1` composition root + Next rewrite，不是生产发布栈。
- 不冻结 Chrome/Edge 版本（`NFR-UX-005` / `TBD-P0`）。
- 一次本机登录 ≠ 上线传输层与 RBAC 门禁通过。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-005 | unverified | opt-in Playwright 登录；CI 不启动 uvicorn；不等于上线传输验证 |

`implemented`（opt-in 浏览器登录）≠ `verified`。
