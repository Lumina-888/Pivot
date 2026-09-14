# Compose 意图（Wave 3 依赖 fixture + opt-in api/web/worker）

> **状态**：依赖服务（postgres / minio / qdrant / redis）已写成可本地启动的 `docker-compose.yml` fixture。`api`、`web` 与 `worker` 为 Compose profile `app`，默认 `docker compose up` **不**拉起。dev-staging overlay 为 `docker-compose.staging.yml`（nginx 只反代 web，默认绑 127.0.0.1:80）。  
> **不是**生产 ECS 发布栈，**不是** `GATE-P0-008` 通过证据。api 与 worker 注入共享 PG/MinIO/Qdrant/Redis、HTTP Embedding（`PIVOT_EMBEDDING*`）与解析器（`PIVOT_PARSER*`：local 启发式、native 真实库 extra、mineru 云）；api 注入 `PIVOT_INGEST` / 队列 / concurrency / Celery broker 与登录限流 `PIVOT_LOGIN_MAX_FAILURES` / `PIVOT_LOGIN_WINDOW_SECONDS`（不写死次数）；api 注入 Draft Writer `PIVOT_LLM*`（worker 不写作）；worker 为注入 broker 的 Celery fixture；Redis 不是业务事实源；CI 不启动。MinerU / LLM / Embedding / Rerank **不自建**，只走外部 API。Dockerfile 安装 `worker[celery,parse]`。

## 服务

| 服务 | 用途 | 健康检查 | 本切片 |
|---|---|---|---|
| postgres | 业务事实源 | `pg_isready` | fixture 已钉镜像 |
| minio | 对象存储 | HTTP `/minio/health/live` | fixture 已钉镜像 |
| qdrant | 向量索引 | HTTP `/readyz` | fixture 已钉镜像 |
| redis | 缓存/队列辅助，**不是**业务事实源 | `redis-cli ping` | fixture 已钉镜像 |
| api | FastAPI composition root `/healthz` `/readyz` `/api/v1`；注入共享 PG/MinIO/Qdrant/Redis、celery ingest、登录限流阈值/窗口、HTTP Embedding、Draft Writer 与解析器 | HTTP `/healthz` | Dockerfile + profile `app`（`worker[celery,parse]`）；存储/向量/缓存/ingest/限流/Embedding/LLM/Parser 注入；CI 不 build/up |
| web | Next.js（`/api/v1` rewrite 到注入的 `PIVOT_API_ORIGIN`） | HTTP `/login` | Dockerfile.web + profile `app`；CI 不 build/up |
| worker | Celery 只消费 parse 队列；装配共享 PG 事实、MinIO 对象、Qdrant IndexPublisher；注入 Redis cache/queue、同一套 HTTP Embedding 与解析器 | HTTP `/healthz` | Dockerfile.worker + profile `app`（`worker[celery,parse]`）；broker/存储/Qdrant/Redis/Embedding/Parser 注入；CI 不 build/up |
| nginx | staging 反代 `web:3000`；默认 loopback :80（SSH 隧道） | HTTP `/login` | overlay `docker-compose.staging.yml`；不挂 443；CI 不 build/up |

## 明确约束

- CI **不得**调用 `docker compose up` / `docker build`，也不得在 workflow 中启动容器；
- 不把 `latest` 写成镜像约定；镜像 tag 只是 fixture pin，不等于 GATE-P0-008 verified；
- 默认 `docker compose up` 只起四依赖；`docker compose --profile app up` 才起 api、web 与 worker；
- api 的 TTL/检索 k、共享 PG/MinIO/Qdrant/Redis、`PIVOT_INGEST` / 队列 / concurrency / Celery broker、登录限流 `PIVOT_LOGIN_MAX_FAILURES` / `PIVOT_LOGIN_WINDOW_SECONDS`、HTTP Embedding `PIVOT_EMBEDDING*`、Draft Writer `PIVOT_LLM*`、解析器 `PIVOT_PARSER*`（local / native / mineru）、web 的 `PIVOT_API_ORIGIN`、worker 的解析/在线队列名、concurrency、Celery broker、共享 PG/MinIO/Qdrant/Redis/Embedding/Parser 变量由环境注入，缺 store 选择或缺登录阈值/窗口失败闭环，不冻结 `TBD-P0`，不写死失败次数，不写生产供应商 URL/模型名；不把 eager 当生产队列；Redis 不是业务事实源；进程外 `assemble_runtime` 两者都缺时仍永不锁定；默认 Embedding 仍为 hash；默认 Writer 仍为 local；默认 Parser 仍为 local 启发式/stdlib；`native` 需 `worker[parse]`；worker 不注入 `PIVOT_LLM*`；
- 解析队列与在线队列必须隔离；worker 只消费 parse 队列；内存对象不得作为跨进程事实；
- 对真实 PostgreSQL 的 Alembic 冒烟是 opt-in（`PIVOT_REQUIRE_COMPOSE=1` 或 `ops/smoke_postgres_alembic.py`），CI 不启动容器；
- api 冒烟是 opt-in（`PIVOT_REQUIRE_COMPOSE_API=1` 探测 `127.0.0.1:8000/healthz`），CI 默认 skip；
- web 冒烟是 opt-in（`PIVOT_REQUIRE_COMPOSE_WEB=1` 探测 `127.0.0.1:3000/login`），CI 默认 skip；
- worker 冒烟是 opt-in（`PIVOT_REQUIRE_COMPOSE_WORKER=1` 探测 `127.0.0.1:8001/healthz`），CI 默认 skip；
- staging overlay 是 opt-in 第二份 compose 文件；默认 `PIVOT_STAGING_HTTP_BIND=127.0.0.1`；nginx 冒烟是 opt-in（`PIVOT_REQUIRE_COMPOSE_STAGING=1` 探测 `127.0.0.1:80/login`），CI 默认 skip；ECS apply 需要 Owner SSH/安全组/磁盘/域名，编码会话不得冒充上机；
- 8GiB limits 为 staging fixture，不是冻结的 `TBD-P0`，不是 `GATE-P0-007` 峰值；yml 不写死 4C8G；
- 不得将本文件或 compose 文件解释为任一 `GATE-P0-*` 已通过。
