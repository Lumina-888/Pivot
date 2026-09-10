# Wave 3 M11 Compose api 切片限制

环境：根 `Dockerfile` + Compose `api`（profile `app`）；CI 不 `docker build` / `docker compose up`；本机未强制拉起容器。

- Dockerfile 钉 `python:3.12.10-slim-bookworm`，`CMD` 为 `uvicorn pivot.http.main:app --factory`。
- Compose `api` 镜像 tag `pivot-api:0.1.0`，端口 `127.0.0.1:8000`，healthcheck `/healthz`，依赖四存储 `service_healthy`。
- 默认 `docker compose up` 仍只起依赖；`docker compose --profile app up` 才起 api。
- TTL/检索 k、共享 PG/MinIO/Qdrant/Redis 与 celery ingest 变量由环境注入，fixture 占位不是冻结的 `TBD-P0`；未写 ECS 4C8G。Qdrant/Redis 切片限制见 `compose-qdrant-redis.md`。
- Dockerfile 安装 `./worker[celery]` 以便入队；不注入 `PIVOT_CELERY_EAGER`。celery 切片限制见 `compose-api-celery.md`。
- worker Compose 服务见 `compose-worker.md`；无固定生产发布；无回滚演练。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-008 | unverified | Dockerfile/Compose api 为 opt-in fixture，不是固定版本发布、健康门禁和回滚演练 |

`implemented`（Dockerfile / Compose api 文件）≠ `verified`。
