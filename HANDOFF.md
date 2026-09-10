# 问枢 Pivot 会话交接清单

> **日期**：2026-09-10  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**人工标注企业 Golden Set**，或 Celery 队列。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 标成 `GATE-P0 verified`。

## 1. 产品现状

Python **408 passed / 12 skipped**；web foundation **15**。四类存储可注入客户端；导出字节可走 MinIO；dense 检索可消费 Qdrant；ingest 可写入同一 VectorStore；HTTP 上传后进程内 ingest（信封仍 `uploaded`）；BM25 为 stdlib；Compose `api`+`web`+`worker` 为 profile `app`（worker 非 Celery）；100k 为 opt-in 夹具；query Embedding / bge rerank 可注入 HTTP（CI Fake）；Golden Set v0.2 为 120 条合成样本；登录失败限流计数可注入 Redis CacheStore（缺省不锁定）。

- `PIVOT_LOGIN_MAX_FAILURES` + `PIVOT_LOGIN_WINDOW_SECONDS` 同时注入且 `PIVOT_CACHE_STORE=redis` 才锁定
- GATE-P0 全部 unverified；未打 `wave-3-integrated`

## 2. 已知缺口（按优先级）

1. 无 Celery；导出任务仍内存；HTTP ingest 仍请求内同步
2. Golden Set 120 条仍为合成，非企业人工标注；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank 冒烟
3. PATCH `/admin/users/{id}` 只改 status；`must_change_password` 不入库

## 3. 下一刀建议

登录限流已接到 CacheStore（阈值仍 TBD-P0）。下一刀人工标注企业 Golden Set，或按暂缓依赖引入 Celery。Celery 若要跨进程消费上传，还需文档事实进 PostgreSQL。

## 4. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。
