# Wave 3 M11 Compose Celery worker 切片限制

环境：根 `Dockerfile.worker` + Compose `worker`（profile `app`）；CI 不 `docker build` / `docker compose up`；本机未强制拉起容器。

- Dockerfile.worker 钉 `python:3.12.10-slim-bookworm`，安装 `./worker[celery]`，`CMD` 为 `python -m pivot_worker`（healthz + Celery worker）。
- Compose `worker` 镜像 tag `pivot-worker:0.1.0`，端口 `127.0.0.1:8001`，healthcheck `/healthz`，依赖四存储 `service_healthy`。
- `PIVOT_CELERY_BROKER` / 队列名 / concurrency 由环境注入，fixture 占位不是冻结的 `TBD-P0`；compose.yml 不写死 `redis://`；只监听 parse 队列。
- HTTP 缺省仍为进程内 ingest；worker 进程未装配共享 MinIO 对象字节；无固定生产发布；无回滚演练。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-008 | unverified | Dockerfile.worker/Compose Celery worker 为 opt-in fixture，不是固定版本发布、健康门禁和回滚演练；CI 不启动 Redis broker |

`implemented`（Compose Celery worker 文件）≠ `verified`。
