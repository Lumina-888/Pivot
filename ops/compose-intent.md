# Compose 意图（Wave 3 依赖 fixture + opt-in api/web/worker）

> **状态**：依赖服务（postgres / minio / qdrant / redis）已写成可本地启动的 `docker-compose.yml` fixture。`api`、`web` 与 `worker` 为 Compose profile `app`，默认 `docker compose up` **不**拉起。  
> **不是**生产 ECS 发布栈，**不是** `GATE-P0-008` 通过证据。api 与 worker 注入共享 PG/MinIO；api 注入 `PIVOT_INGEST` / 队列 / concurrency / Celery broker；worker 可注入 Qdrant；worker 为注入 broker 的 Celery fixture；CI 不启动。

## 服务

| 服务 | 用途 | 健康检查 | 本切片 |
|---|---|---|---|
| postgres | 业务事实源 | `pg_isready` | fixture 已钉镜像 |
| minio | 对象存储 | HTTP `/minio/health/live` | fixture 已钉镜像 |
| qdrant | 向量索引 | HTTP `/readyz` | fixture 已钉镜像 |
| redis | 缓存/队列辅助，**不是**业务事实源 | `redis-cli ping` | fixture 已钉镜像 |
| api | FastAPI composition root `/healthz` `/readyz` `/api/v1`；注入共享 PG/MinIO 与 celery ingest | HTTP `/healthz` | Dockerfile + profile `app`；存储/ingest 注入；CI 不 build/up |
| web | Next.js（`/api/v1` rewrite 到注入的 `PIVOT_API_ORIGIN`） | HTTP `/login` | Dockerfile.web + profile `app`；CI 不 build/up |
| worker | Celery 只消费 parse 队列；装配共享 PG 事实、MinIO 对象，可选 Qdrant IndexPublisher | HTTP `/healthz` | Dockerfile.worker + profile `app`；broker/存储/Qdrant 注入；CI 不 build/up |

## 明确约束

- CI **不得**调用 `docker compose up` / `docker build`，也不得在 workflow 中启动容器；
- 不把 `latest` 写成镜像约定；镜像 tag 只是 fixture pin，不等于 GATE-P0-008 verified；
- 默认 `docker compose up` 只起四依赖；`docker compose --profile app up` 才起 api、web 与 worker；
- api 的 TTL/检索 k、共享 PG/MinIO、`PIVOT_INGEST` / 队列 / concurrency / Celery broker、web 的 `PIVOT_API_ORIGIN`、worker 的解析/在线队列名、concurrency、Celery broker、共享 PG/MinIO 与可选 Qdrant 变量由环境注入，缺变量失败闭环，不冻结 `TBD-P0`，不写生产供应商 URL；不把 eager 当生产队列；
- 解析队列与在线队列必须隔离；worker 只消费 parse 队列；内存对象不得作为跨进程事实；
- 对真实 PostgreSQL 的 Alembic 冒烟是 opt-in（`PIVOT_REQUIRE_COMPOSE=1` 或 `ops/smoke_postgres_alembic.py`），CI 不启动容器；
- api 冒烟是 opt-in（`PIVOT_REQUIRE_COMPOSE_API=1` 探测 `127.0.0.1:8000/healthz`），CI 默认 skip；
- web 冒烟是 opt-in（`PIVOT_REQUIRE_COMPOSE_WEB=1` 探测 `127.0.0.1:3000/login`），CI 默认 skip；
- worker 冒烟是 opt-in（`PIVOT_REQUIRE_COMPOSE_WORKER=1` 探测 `127.0.0.1:8001/healthz`），CI 默认 skip；
- 不得将本文件或 compose 文件解释为任一 `GATE-P0-*` 已通过。
