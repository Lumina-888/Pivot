# 问枢 Pivot 会话交接清单

> **日期**：2026-09-10  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**人工标注企业 Golden Set**，或 worker 装配共享 MinIO/PG ingest runner。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / eager Celery / Compose Celery fixture 标成 `GATE-P0 verified`。

## 1. 产品现状

Python **431 passed / 12 skipped**。`PIVOT_INGEST=celery` eager 可看见 PG version/task。Compose worker 安装 `worker[celery]`，注入 `PIVOT_CELERY_BROKER`，只监听 parse 队列。CI 不 build/up。HTTP 缺省仍进程内 ingest。worker 进程尚未装配共享 MinIO 对象字节。

## 2. 已知缺口（按优先级）

1. worker 未装配共享 MinIO/PG ingest runner；导出任务仍内存；HTTP 缺省仍请求内同步
2. Golden Set 120 条仍为合成；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank 冒烟
3. PATCH `/admin/users/{id}` 只改 status；`must_change_password` 不入库；version.idempotency_key 未入库

## 3. 下一刀建议

Compose Celery worker 已声明 Redis broker。真正跨进程 ingest 还要把 worker 接到共享 MinIO + PG。企业 Golden Set 仍需人工标注。

## 4. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。
