# Compose 意图（Wave 3 依赖 fixture）

> **状态**：依赖服务（postgres / minio / qdrant / redis）已写成可本地启动的 `docker-compose.yml` fixture。  
> **不是**生产 ECS 发布栈，**不是** `GATE-P0-008` 通过证据。

## 服务

| 服务 | 用途 | 健康检查 | 本切片 |
|---|---|---|---|
| postgres | 业务事实源 | `pg_isready` | fixture 已钉镜像 |
| minio | 对象存储 | HTTP `/minio/health/live` | fixture 已钉镜像 |
| qdrant | 向量索引 | HTTP `/readyz` | fixture 已钉镜像 |
| redis | 缓存/队列辅助，**不是**业务事实源 | `redis-cli ping` | fixture 已钉镜像 |
| api | FastAPI `/api/v1` + `/healthz` `/readyz` | HTTP | **未启用**（无 FastAPI） |
| worker | Celery 解析队列与在线队列隔离 | worker ping | **未启用**（非 Celery） |
| web | Next.js | HTTP | **未启用**（无运行中 API） |

## 明确约束

- CI **不得**调用 `docker compose up`，也不得在 workflow 中启动容器；
- 不把 `latest` 写成镜像约定；镜像 tag 只是 fixture pin，不等于 GATE-P0-008 verified；
- 应用进程 `/healthz` `/readyz` 仍不存在；
- 不得将本文件或 compose 文件解释为任一 `GATE-P0-*` 已通过。
