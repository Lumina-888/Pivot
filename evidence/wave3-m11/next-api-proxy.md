# Wave 3 M08/M11 Next `/api/v1` 反代限制

环境：检查 `next.config.mjs` 与 `apiProxyRewrites`；不启动 Next/uvicorn/Compose。

- 浏览器仍请求同源 `/api/v1`；Next 把 `/api/v1/:path*` 转到注入的 `PIVOT_API_ORIGIN`。
- 未设置 origin 时不挂 rewrite，登录仍 404（失败闭环）。
- 无 Playwright 浏览器登录；无 Dockerfile / Compose web 服务。
- Cookie 仍为 HttpOnly/Secure/SameSite；本切片不改 Cookie 语义。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-005 | unverified | Next rewrite 只是同源转发配置；不等于上线传输层与浏览器登录已通过 |

`implemented`（Next rewrite）≠ `verified`。
