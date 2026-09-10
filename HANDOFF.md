# 问枢 Pivot 会话交接清单

> **日期**：2026-09-10  
> **HEAD**：`85776e6`（feat，`main`；目标 tag `M07-v0.6.0` / `M11-v0.15.0`）  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**人工标注企业 Golden Set**（人才能做），或 **Compose api 注入共享 PG/MinIO**，或 **worker 接 Qdrant**。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / eager Celery / Compose Celery fixture / Fake MinIO worker ingest 标成 `GATE-P0 verified`。

## 1. 产品现状

Python **441 passed / 12 skipped**（Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）。

- `PIVOT_STORAGE=postgres`：用户目录 + Document/Version/Chunk/Task 可跨装配存活（CI sqlite URL）。
- `PIVOT_INGEST=celery`：eager 任务可看见 PG version/task；缺省 HTTP 仍进程内 ingest。
- Compose `worker`（profile `app`）：Celery 只听 parse；注入 broker 与共享 PG/MinIO 变量；`python -m pivot_worker` 装配 `DocumentIngestRunner` 后再听队列。
- worker 拒绝 `storage=memory` / `object_store=memory`；CI 用 sqlite + Fake MinIO client。
- Compose api **尚未**注入 `PIVOT_DATABASE_URL` / MinIO 变量，因此 Compose 端到端仍不能让 HTTP 上传与 worker 共享字节。
- Golden Set 仍为 v0.2-synthetic 120 条。GATE-P0 全部 unverified。未打 `wave-3-integrated`。

## 2. 本会话完成的一刀

1. worker 装配共享 MinIO + PG ingest runner（本切片）
   - 变更：`progress/changes/20260910-M07-worker-minio-ingest.md`
   - 入口：`worker/src/pivot_worker/assembly.py`、`__main__.py`、`docker-compose.yml` worker 环境、`tests/integration/pipeline/test_FR_DOC_006_worker_minio_ingest.py`

## 3. 已知缺口（按优先级）

1. Compose api 未注入共享 PG/MinIO；HTTP 缺省仍请求内同步；worker 未必选接 Qdrant；导出任务仍内存
2. Golden Set 120 条仍为合成；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank 冒烟
3. PATCH `/admin/users/{id}` 只改 status；`must_change_password` 不入库；version.idempotency_key 未入库

## 4. 下一刀建议（技术刀）

**Compose api 注入共享 PG + MinIO**，使 profile `app` 的 HTTP 上传与 worker ingest 读同一事实/对象：

- Compose `api` 注入 `PIVOT_STORAGE` / `PIVOT_DATABASE_URL` / `PIVOT_OBJECT_STORE` / MinIO 变量（`${}`，不写死 URL）
- **不** 在 CI `docker compose up`；**不** 改 HTTP 缺省 sync；**不** 冻结 TBD-P0；**不** 标 GATE verified
- 对象字节跨进程必须共享 ObjectStore；内存对象不能当跨进程事实

或 **worker 接 Qdrant**：ingest 发布写入与 API 检索同一 VectorStore。

企业 Golden Set 仍需人工标注，会话内不要合成更多假样本并标成企业集。

先写 `progress/changes/` 再写业务代码。

## 5. 恢复命令

```bash
cd "E:/AI Project/Pivot"
git switch main
git log --oneline --decorate -8
python ops/run_grouped_tests.py --skip-web
```

## 6. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。
