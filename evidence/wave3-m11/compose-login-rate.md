# Wave 3 M01/M11 Compose api 注入登录限流切片限制

环境：Compose `api` 同时注入 `PIVOT_LOGIN_MAX_FAILURES` / `PIVOT_LOGIN_WINDOW_SECONDS`（`${:?}`）；计数写既有 Redis CacheStore；CI 不 `docker build` / `docker compose up`；本机未强制拉起容器。

- Compose yml 不写死失败次数或窗口；禁止写死次数。
- example 占位是 fixture，不是冻结的 TBD-P0。两者一起出现。
- worker 不注入登录阈值（登录只在 HTTP）。
- 进程外 `assemble_runtime` 两者都缺时仍永不锁定。
- 锁定后仍统一 `AUTH_INVALID_CREDENTIALS`。Redis 不是业务事实源。
- 本切片不是上线 Cookie/传输验证。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-005 | unverified | Compose 注入登录限流阈值不是上线传输/Cookie 验证，也未冻结 TBD-P0 阈值 |

`implemented`（Compose api 注入登录限流接到 Redis）≠ `verified`。
