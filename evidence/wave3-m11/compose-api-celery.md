# Wave 3 M11 Compose api celery ingest 切片限制

环境：Compose `api` 注入 `PIVOT_INGEST` / 队列名 / concurrency / `PIVOT_CELERY_BROKER`；根 Dockerfile 安装 `./worker[celery,parse]` 以便 `CeleryIngestSubmitter` 入队。CI 不 `docker build` / `docker compose up`；本机未强制拉起容器。

- Compose yml 不写死 `redis://`；不静默 `:-sync`；不注入 `PIVOT_CELERY_EAGER=1`。
- example 占位 `PIVOT_INGEST=celery` 是 fixture，不是冻结的 TBD-P0。
- 进程外 `assemble_runtime` 缺省仍 `sync`；CI HTTP celery 测试仍为 eager + memory broker，不是 Compose 上的真实 Redis worker。
- 本切片不把 api 必选接到 Qdrant/Redis 业务端口。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | Compose api celery ingest 为 opt-in fixture 注入，不是真实 Redis/Celery worker 与 Qdrant 原子发布环境；eager 不是生产队列 |

`implemented`（Compose api celery 注入）≠ `verified`。
