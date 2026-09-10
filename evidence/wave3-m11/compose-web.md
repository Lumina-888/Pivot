# Wave 3 M11 Compose web 切片限制

环境：根 `Dockerfile.web` + Compose `web`（profile `app`）；CI 不 `docker build` / `docker compose up`；本机未强制拉起容器。

- Dockerfile.web 钉 `node:20.19.0-bookworm-slim`，`CMD` 为 `next start --hostname 0.0.0.0 --port 3000`。
- Compose `web` 镜像 tag `pivot-web:0.1.0`，端口 `127.0.0.1:3000`，healthcheck `/login`，依赖 `api` `service_healthy`。
- 默认 `docker compose up` 仍只起依赖；`docker compose --profile app up` 才起 api+web。
- `PIVOT_API_ORIGIN` 由环境注入，fixture 占位不是生产 URL、不是冻结的 `TBD-P0`；未写 ECS 4C8G。
- worker Compose 服务见 `compose-worker.md`（非 Celery）；无固定生产发布；无回滚演练。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-008 | unverified | Dockerfile.web/Compose web 为 opt-in fixture，不是固定版本发布、健康门禁和回滚演练 |

`implemented`（Dockerfile.web / Compose web 文件）≠ `verified`。
