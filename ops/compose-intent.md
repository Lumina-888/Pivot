# Compose 意图（Wave 2 草稿，默认不启用）

> **状态**：intent only。本文件不是可启动的 Compose 栈。  
> **约束**：PROGRESS 禁止本波次静默加 Compose/FastAPI/Celery；真实容器属于 Wave 3 / `GATE-P0-008`。

## 计划中的服务（Wave 3 才允许默认拉起）

| 服务 | 用途 | 健康检查意图 | 本波次 |
|---|---|---|---|
| postgres | 业务事实源 | TCP 5432 / `pg_isready` | 未启用 |
| minio | 对象存储 | HTTP ready | 未启用 |
| qdrant | 向量索引 | HTTP ready | 未启用 |
| redis | 缓存/队列辅助，**不是**业务事实源 | TCP 6379 | 未启用 |
| api | FastAPI `/api/v1` + `/healthz` `/readyz` | HTTP | **无 FastAPI，未挂路由** |
| worker | Celery 解析队列与在线队列隔离 | worker ping | **非 Celery** |
| web | Next.js | HTTP | 仅有工程骨架；M09/M10 尚未合入本基线 |

## 明确不做

- 不提交默认可 `docker compose up` 的运行栈；
- 不把 `latest` 写成生产镜像约定；
- CI **不得**调用 compose；
- 不得将本文件解释为 `GATE-P0-008` 已通过。
