# Wave 3 M11 Compose worker 切片限制

环境：根 `Dockerfile.worker` + Compose `worker`（profile `app`）；CI 不 `docker build` / `docker compose up`；本机未强制拉起容器。

- Dockerfile.worker 钉 `python:3.12.10-slim-bookworm`，`CMD` 为 `python -m pivot_worker`；非 Celery。
- Compose `worker` 镜像 tag `pivot-worker:0.1.0`，端口 `127.0.0.1:8001`，healthcheck `/healthz`，依赖四存储 `service_healthy`。
- 默认 `docker compose up` 仍只起依赖；`docker compose --profile app up` 才起 api+web+worker。
- `PIVOT_PARSE_QUEUE` / `PIVOT_ONLINE_QUEUE` / `PIVOT_WORKER_CONCURRENCY` 由环境注入，fixture 占位不是冻结的 `TBD-P0`；解析队列与在线队列隔离；未写 ECS 4C8G。
- HTTP 上传仍为进程内 ingest；无固定生产发布；无回滚演练。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-008 | unverified | Dockerfile.worker/Compose worker 为 opt-in fixture，不是固定版本发布、健康门禁和回滚演练；也不是 Celery |

`implemented`（Dockerfile.worker / Compose worker 文件）≠ `verified`。
