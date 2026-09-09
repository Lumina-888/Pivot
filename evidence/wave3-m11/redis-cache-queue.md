# Wave 3 M03 Redis CacheStore / QueueStore 客户端限制

环境：`RedisCacheStore` / `RedisQueueStore` 默认 CI 用注入的内存 client 子集；Compose Redis 为 opt-in（`PIVOT_REQUIRE_COMPOSE=1` 且安装 `api[redis]`）。不启动 uvicorn/Celery；不把内存 client 标成生产队列。

- `PIVOT_CACHE_STORE=redis` / `PIVOT_QUEUE_STORE=redis` 将缓存与队列端口接到 Redis 适配；endpoint 必须注入，禁止写死生产地址。
- Redis 不是业务事实源；cache `set` 必须带正 TTL；queue 丢失不得使 PostgreSQL 事实不可恢复。
- 登录限流仍为 `InMemoryAttempts`（阈值 TBD-P0）；无 Celery broker。
- `/readyz` 在仅接通 redis 探测时仍因 postgres/minio/qdrant 失败闭环。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | 缓存/队列客户端不等于状态一致性、幂等、删除与索引原子发布已通过 |

`implemented`（redis cache/queue）≠ `verified`。
