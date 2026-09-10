# 变更申请：登录失败限流计数接到 Redis CacheStore

- **日期**：2026-09-10
- **申请人**：Wave 3 主线会话（M01 限流端口 + M11 composition root 接线）
- **背景**：Redis 缓存/队列客户端已装配，但登录失败限流仍为 `InMemoryAttempts` 且默认永不锁定。SPEC §2.1 规定 Redis 保存限流计数；`FR-AUTH-002` 要求失败登录触发限流，阈值/窗口/解锁为 `TBD-P0`。不得把限流接线标成 GATE verified，不得冻结数值。
- **原契约/现状**：
  - `LoginAttemptLimiter` 已冻结；`InMemoryAttempts.is_blocked` 恒为 False；
  - `PIVOT_CACHE_STORE=redis` 只把 CacheStore 接到 `/readyz`，AuthService 不消费；
  - 无 `PIVOT_LOGIN_MAX_FAILURES` / `PIVOT_LOGIN_WINDOW_SECONDS`。
- **拟变更内容**（本切片）：
  - M01 `CacheLoginAttempts`：用注入的 `CacheStore` 记录失败次数，TTL 为注入窗口；达到注入阈值后 `is_blocked`；成功登录 `reset`；被锁与错误密码仍返回统一 `AUTH_INVALID_CREDENTIALS`；
  - M11：`PIVOT_LOGIN_MAX_FAILURES` 与 `PIVOT_LOGIN_WINDOW_SECONDS` 必须同时注入或同时缺省；缺省时行为不变（永不锁定）；注入时要求 `PIVOT_CACHE_STORE=redis`，否则失败闭环，不回退 memory、不写死默认阈值；
  - `ops/compose.env.example` 以注释占位标明不是冻结的 `TBD-P0`；
  - **不** 引入 Celery；**不** 改 Cookie/登录成功语义；**不** 冻结阈值/窗口；**不** 把 `GATE-P0-005` 标 verified。
- **影响模块**：M01（attempts 适配）；M11（settings/bootstrap、pipeline 测试、证据）；M03 只被消费既有 CacheStore；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：未注入阈值时既有登录单测与 HTTP 不变；CI 默认 memory + 不锁定。
- **测试 ID**：`test_FR_AUTH_002_cache_attempts_block_after_injected_threshold`、`test_FR_AUTH_002_cache_attempts_reset_on_success`、`test_FR_AUTH_002_blocked_login_uses_uniform_error`、`test_FR_AUTH_002_missing_threshold_never_blocks`、`test_NFR_OBS_runtime_login_limit_requires_redis_cache`、`test_NFR_OBS_runtime_redis_login_limiter_uses_cache`、`test_FR_AUTH_002_http_runtime_lockout_same_error`、`test_GATE_P0_005_not_verified_by_login_rate_limit`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置；不冻结 TBD-P0 限流阈值）。
- **审核结果**：2026-09-10 Wave 3 主线会话 **批准**。
