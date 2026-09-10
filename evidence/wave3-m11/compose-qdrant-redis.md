# Wave 3 M11 Compose api/worker 注入 Qdrant/Redis 切片限制

环境：Compose `api` 与 `worker` 注入同一套 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*` / `PIVOT_CACHE_STORE` / `PIVOT_QUEUE_STORE` / `PIVOT_REDIS_ENDPOINT`；CI 不 `docker build` / `docker compose up`；本机未强制拉起容器。

- Compose yml 不写死 Qdrant/Redis URL、维数或距离；store 选择不静默 `:-memory`；值仍允许 `memory`。
- example 占位 `qdrant` / `redis` 是 fixture，不是冻结的 TBD-P0。
- Redis 不是业务事实源；丢失不得使 PostgreSQL 事实不可恢复。
- 进程外 `assemble_runtime` 缺省仍 memory；选中 qdrant/redis 缺 endpoint 时运行时失败闭环。
- 本切片不注入登录失败阈值，不把 fixture 当真实原子发布环境。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-002 | unverified | Compose 注入 Qdrant 变量不是 dense+BM25 真实供应商闭环；CI Fake embedder |
| GATE-P0-003 | unverified | Compose api/worker Qdrant/Redis 为 opt-in fixture 注入，不是真实 Redis/Celery worker 与 Qdrant 原子发布环境 |
| GATE-P0-008 | unverified | Dockerfile/Compose 为 opt-in fixture，不是固定版本发布、健康门禁和回滚演练 |

`implemented`（Compose api/worker 注入 Qdrant/Redis）≠ `verified`。
