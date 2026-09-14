# Wave 3 M11 Playwright 十页限制

环境：默认分组 CI **不**启动 uvicorn/Next/Compose，也不安装 Chromium。

- `PIVOT_REQUIRE_PLAYWRIGHT=1` 覆盖 SPEC §1.1 十页：`/login`、`/`、`/library`、`/library/[id]`、`/search?q=`、`/chat`、`/admin`、`/admin/docs`、`/admin/users`、`/admin/audit`。
- opt-in 路径：本机 `127.0.0.1` composition root + Next rewrite，不是生产发布栈。
- 夹具播种一篇共享文档与一名普通用户；不是企业文档，不是上线 RBAC 评测。
- 不冻结 Chrome/Edge 版本（`NFR-UX-005` / `TBD-P0`）。
- Fake fetch 十页 ≠ 浏览器证据；opt-in 十页 ≠ `GATE-P0-005` 通过。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-005 | unverified | opt-in Playwright 十页；CI 不启动 uvicorn；不等于上线传输/RBAC/日志安全验证 |

`implemented`（opt-in 浏览器十页）≠ `verified`。
