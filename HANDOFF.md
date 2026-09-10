# 问枢 Pivot 会话交接清单

> **日期**：2026-09-10  
> **HEAD**：待提交（`main`，上一 tag `M11-v0.17.0` / `M07-v0.7.0`）  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**ND-W3-12** Compose api/worker 注入 Qdrant/Redis。staging：硅基仅 embedding/rerank；DeepSeek 官方 `deepseek-flash`；小米官方 `mimo-v2.5`；MinerU 官方云。见 `progress/changes/20260910-M00-dev-staging-vendors.md`。阿里云 OS 等 ND-STG-04 再确认。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / eager Celery / Compose Celery fixture / Fake MinIO worker ingest / Compose api 共享存储注入 / Fake worker Qdrant upsert / Compose api celery 注入 标成 `GATE-P0 verified`。

## 1. 产品现状

Python **457 passed / 12 skipped**（Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）。

- Compose `api` 与 `worker` 注入同一套 `PIVOT_STORAGE` / `PIVOT_DATABASE_URL` / `PIVOT_OBJECT_STORE` / MinIO 变量（`${:?}`，不写死 URL，不静默 memory）。
- worker `assemble_ingest_runtime` 在 `PIVOT_VECTOR_STORE=qdrant` 时装配 `IndexPublisher` + 注入维数；Compose worker 注入 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*`。
- HTTP 缺省仍进程内 ingest；`PIVOT_INGEST=celery` 可 eager。worker 装配共享 MinIO/PG runner，拒绝 memory 对象。
- Compose api **已**注入 `PIVOT_INGEST` / 队列 / concurrency / `PIVOT_CELERY_BROKER`（`${:?}`，不写死 `redis://`，不注入 eager）。Dockerfile 安装 `worker[celery]`。
- Compose api **尚未**必选接 Qdrant/Redis（属 ND-W3-12）。
- Golden Set 仍为 v0.2-synthetic 120 条。GATE-P0 全部 unverified。未打 `wave-3-integrated`。

## 2. 本会话完成的一刀

1. Compose api 注入 `PIVOT_INGEST=celery`（ND-W3-02）
   - 变更：`progress/changes/20260910-M11-compose-api-celery-ingest.md`
   - 入口：`Dockerfile`、`docker-compose.yml` api 环境、`ops/compose.env.example`、`tests/integration/pipeline/test_NFR_OBS_compose_api.py`

## 3. 已知缺口（按优先级）

1. Compose api/worker 未把 Qdrant/Redis 写成 app profile 必选；HTTP 缺省仍请求内同步；导出任务仍内存
2. Golden Set 120 条仍为合成；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank 冒烟
3. PATCH `/admin/users/{id}` 只改 status；`must_change_password` 不入库；version.idempotency_key 未入库

## 4. 下一刀建议（技术刀）

**Compose api/worker 注入 Qdrant/Redis**（ND-W3-12）：让 app profile 默认指向同一 VectorStore / 缓存端口（仍不冻距离/TTL；CI 不 up）。

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
