# 问枢 Pivot 会话交接清单

> **日期**：2026-09-10  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**人工标注企业 Golden Set**，或 Compose/Redis broker 上的 Celery worker（对象字节仍需共享 MinIO）。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / eager Celery 标成 `GATE-P0 verified`。

## 1. 产品现状

Python **426 passed / 12 skipped**。`PIVOT_STORAGE=postgres` 可装配用户目录与文档事实。`PIVOT_INGEST=celery` 时 eager 任务可跨装配看见 PG version/task。缺省 HTTP ingest 仍进程内。Compose worker 仍 ping。对象字节仍 memory/MinIO。

## 2. 已知缺口（按优先级）

1. Compose/Redis broker 上无 Celery worker；导出任务仍内存；HTTP 缺省仍请求内同步
2. Golden Set 120 条仍为合成；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank 冒烟
3. PATCH `/admin/users/{id}` 只改 status；`must_change_password` 不入库；version.idempotency_key 未入库

## 3. 下一刀建议

Celery 任务已能看见 PG version/task（eager + sqlite）。真实 worker 还需要 Redis broker 与共享 MinIO 对象字节。企业 Golden Set 仍需人工标注。

## 4. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。
