# Wave 3 M07 Celery ingest 切片限制

环境：`PIVOT_INGEST=celery` 时 `CeleryIngestSubmitter` 把既有 `DocumentIngestRunner` 注册为 parse 队列任务。CI 用 `task_always_eager` 与注入的 `memory://` broker，不启动 Redis/Celery worker 进程。sqlite 测试 URL 不是生产 PostgreSQL。

- 缺省 `PIVOT_INGEST=sync`，HTTP 上传仍为进程内 ingest。
- Celery 任务按 `version_id` 读取 DocumentService；`PIVOT_STORAGE=postgres` 时第二装配可看见 version，ingest 后 `celery_tasks` 有对应 task。
- 对象字节仍依赖共享 ObjectStore（本切片测试注入同一 memory store，不是跨进程 MinIO）。
- Compose worker 仍为 ping fixture，CMD 不是 `celery worker`。
- 本切片不是 `GATE-P0-003` 闭环。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | eager Celery + sqlite/memory broker 不是真实 Redis broker、Celery worker 与 Qdrant 原子发布 |

`implemented`（Celery 任务可看见 PG version/task）≠ `verified`。
