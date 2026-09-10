# Wave 3 M01 登录限流接到 Redis CacheStore 切片限制

环境：`CacheLoginAttempts` 消费注入的 `CacheStore`；CI 用内存 Redis client 子集。不启动 uvicorn；不冻结失败阈值/窗口。

- 未注入 `PIVOT_LOGIN_MAX_FAILURES` / `PIVOT_LOGIN_WINDOW_SECONDS` 时仍永不锁定（TBD-P0）。
- 同时注入时要求 `PIVOT_CACHE_STORE=redis`，计数写 CacheStore 且带 TTL；缺一或非 redis 失败闭环。
- 锁定后仍返回统一 `AUTH_INVALID_CREDENTIALS`，不泄露用户存在性。
- 无 Celery；不是上线传输验证。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-005 | unverified | 限流计数接到 CacheStore 不是上线 Cookie/传输验证，也未冻结 TBD-P0 阈值 |

`implemented`（可注入 Redis 限流计数）≠ `verified`。
