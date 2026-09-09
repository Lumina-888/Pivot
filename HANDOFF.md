# 问枢 Pivot 会话交接清单

> **日期**：2026-09-09  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**真实 BM25/rerank**，或 100k Chunk / Compose api。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / Fake embedder / 进程内 5 并发或备份 roundtrip 标成 `GATE-P0 verified`。

## 1. 产品现状

Python **323 passed / 8 skipped**；web foundation **15**。四类存储可注入客户端；导出字节可走 MinIO；dense 检索可消费 Qdrant；5 并发与备份恢复为进程内夹具。

- `PIVOT_OBJECT_STORE=minio` 装配文档 **与导出** 对象；`presign` 不做公开下载
- `PIVOT_VECTOR_STORE=qdrant` 时 dense 为 `VectorStoreRetriever`（Fake `HashingQueryEmbedder`）；BM25 仍 Keyword；Golden Set 仅 10 条合成样本
- 5 路 Fake `retrieve` 可并发完成；`ops/fact_backup.py` 可 roundtrip 用户/对象/向量/审计；非新 ECS / 非加密 OSS
- GATE-P0 全部 unverified；未打 `wave-3-integrated`

## 2. 已知缺口（按优先级）

1. 登录限流未接 Redis；无 Celery；导出任务仍内存；无 ingest→Qdrant
2. Golden Set 未达 100~150；无 100k Chunk 峰值；无新 ECS 备份恢复；BM25/rerank 仍 Fake
3. PATCH `/admin/users/{id}` 只改 status；`must_change_password` 不入库
4. 无 Dockerfile / Compose api·web·worker

## 3. 下一刀建议

5 并发与进程内备份夹具已落地（不冻结 P95/RPO/RTO）。下一刀真实 BM25/rerank，或 100k Chunk / Compose api。

## 4. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。
