# 问枢 Pivot 会话交接清单

> **日期**：2026-09-14  
> **HEAD**：本切片提交前为 `aa2794c`（`main`，tag `wave-3-integrated` / `M11-v0.21.0`）；合入后以 `git log` 为准。  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**ND-W3-07** PATCH 角色 / 重置密码 HTTP，或 **ND-STG-01** ingest/检索共用 HTTP Embedding。staging：硅基仅 embedding/rerank；DeepSeek 官方 `deepseek-flash`；小米官方 `mimo-v2.5`；MinerU 官方云。见 `progress/changes/20260910-M00-dev-staging-vendors.md`。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / sqlite 导出任务 / eager Celery / Compose Celery fixture / Fake MinIO worker ingest / Compose api 共享存储注入 / Fake worker Qdrant upsert / Compose api celery 注入 / Compose Qdrant·Redis 注入 / Compose 登录限流注入 / **Wave 3 夹具收口** 标成 `GATE-P0 verified`。`wave-3-integrated` **不等于** P0 通过。

## 1. 产品现状

Python **475 passed / 12 skipped**（Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）。

- Wave 3 夹具已收口：Compose api/web/worker（profile `app`）共享 PG/MinIO/Qdrant/Redis；api 注入 celery ingest 与登录限流阈值/窗口；worker 可接 Qdrant。
- `PIVOT_STORAGE=postgres` 时导出任务可跨装配存活（CI sqlite）；公开 URL 仍 `PublicDownloadSigner`。
- HTTP 缺省仍进程内 ingest。
- Golden Set 仍为 v0.2-synthetic 120 条。GATE-P0 全部 unverified。
- tag `wave-3-integrated` 仅表示夹具收口，不等于 P0 通过，不得宣称 production-ready。

## 2. 本会话完成的一刀

1. ND-W3-04 导出任务 PostgreSQL 持久化
   - 变更：`progress/changes/20260914-M06-postgres-export-tasks.md`
   - 证据：`evidence/wave3-m11/postgres-export-tasks.md`
   - 测试：`tests/integration/db/test_M03_export_store.py`、`tests/integration/pipeline/test_FR_EXPORT_001_http_postgres_tasks.py`

## 3. 已知缺口（按优先级）

1. HTTP 缺省仍请求内同步；PATCH `/admin/users/{id}` 只改 status；无对象字节下载 HTTP（契约如此）
2. Golden Set 120 条仍为合成；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank 冒烟
3. `must_change_password` 不入库；version.idempotency_key 未入库

## 4. 下一刀建议（技术刀）

**ND-W3-07** PATCH 角色 / 重置密码 HTTP，或 **ND-STG-01** ingest 与检索共用注入 HTTP Embedding。

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
