# 问枢 Pivot 会话交接清单

> **日期**：2026-09-10  
> **HEAD**：`69b856a`（`main`，tag `M11-v0.16.0`）  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**人工标注企业 Golden Set**（人才能做），或 **worker 接 Qdrant**，或 **Compose api 注入 `PIVOT_INGEST=celery`**。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / eager Celery / Compose Celery fixture / Fake MinIO worker ingest / Compose api 共享存储注入 标成 `GATE-P0 verified`。

## 1. 产品现状

Python **445 passed / 12 skipped**（Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）。

- Compose `api` 与 `worker` 注入同一套 `PIVOT_STORAGE` / `PIVOT_DATABASE_URL` / `PIVOT_OBJECT_STORE` / MinIO 变量（`${:?}`，不写死 URL，不静默 memory）。
- example 占位为 `postgres` + `minio`（fixture，不是冻结 TBD-P0）。
- HTTP 缺省仍进程内 ingest；`PIVOT_INGEST=celery` 可 eager。worker 装配共享 MinIO/PG runner，拒绝 memory 对象。
- Compose api **尚未**注入 `PIVOT_INGEST=celery`；worker **尚未**必选接 Qdrant。
- Golden Set 仍为 v0.2-synthetic 120 条。GATE-P0 全部 unverified。未打 `wave-3-integrated`。

## 2. 本会话完成的一刀

1. Compose api 注入共享 PG + MinIO（本切片）
   - 变更：`progress/changes/20260910-M11-compose-api-shared-storage.md`
   - 入口：`docker-compose.yml` api 环境、`ops/compose.env.example`、`tests/integration/pipeline/test_FR_DOC_001_http_shared_minio.py`

## 3. 已知缺口（按优先级）

1. Compose api 未注入 celery ingest；worker 未必选接 Qdrant；HTTP 缺省仍请求内同步；导出任务仍内存
2. Golden Set 120 条仍为合成；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank 冒烟
3. PATCH `/admin/users/{id}` 只改 status；`must_change_password` 不入库；version.idempotency_key 未入库

## 4. 下一刀建议（技术刀）

**worker 接 Qdrant**：ingest 发布写入与 API 检索同一 VectorStore。

或 **Compose api 注入 `PIVOT_INGEST=celery`**，使 HTTP 上传入队、worker 消费（仍不改进程外缺省 sync；CI 不 up）。

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
