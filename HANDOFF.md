# 问枢 Pivot 会话交接清单

> **日期**：2026-09-14  
> **HEAD**：本切片提交前为 `479f706`（`main`，tag `M07-v0.8.0`）；合入后以 `git log` 为准。  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**ND-STG-03** MinerU 云解析器，或 **ND-W3-05** 会话/refresh 跨进程。staging：硅基仅 embedding/rerank；DeepSeek 官方 `deepseek-flash`；小米官方 `mimo-v2.5`；MinerU 官方云。见 `progress/changes/20260910-M00-dev-staging-vendors.md`。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / sqlite 导出任务 / eager Celery / Compose Celery fixture / Fake MinIO worker ingest / Compose api 共享存储注入 / Fake worker Qdrant upsert / Compose api celery 注入 / Compose Qdrant·Redis 注入 / Compose 登录限流注入 / **Wave 3 夹具收口** / PATCH 角色 HTTP / **ingest 共用 HTTP Embedding** / **Fake HTTP Writer** 标成 `GATE-P0 verified`。`wave-3-integrated` **不等于** P0 通过。

## 1. 产品现状

Python **519 passed / 12 skipped**（Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）。

- Wave 3 夹具已收口：Compose api/web/worker（profile `app`）共享 PG/MinIO/Qdrant/Redis；api 注入 celery ingest 与登录限流阈值/窗口；worker 可接 Qdrant。
- `PIVOT_EMBEDDING=http` 时 ingest 与检索共用注入 `HttpQueryEmbedder`；Compose api/worker 注入同一套 `PIVOT_EMBEDDING*`；缺省仍 hash。
- `PIVOT_LLM=http` 时装配注入 OpenAI 兼容 Draft Writer；主失败才切 `PIVOT_LLM_FALLBACK_*`；`external_llm_allowed=false` 不得外发；Compose 仅 api 注入 `PIVOT_LLM*`；缺省仍 local 证据拼接。
- `PIVOT_STORAGE=postgres` 时导出任务可跨装配存活（CI sqlite）；公开 URL 仍 `PublicDownloadSigner`。
- HTTP 缺省仍进程内 ingest。
- `PATCH /admin/users/{id}` 已处理 `status` / `role` / `reset_password`。
- Golden Set 仍为 v0.2-synthetic 120 条。GATE-P0 全部 unverified。
- tag `wave-3-integrated` 仅表示夹具收口，不等于 P0 通过，不得宣称 production-ready。

## 2. 本会话完成的一刀

1. ND-STG-02 Deepseek-Flash Draft Writer
   - 变更：`progress/changes/20260914-M05-http-draft-writer.md`
   - 证据：`evidence/wave3-m11/http-draft-writer.md`
   - 测试：`tests/unit/qa/test_FR_QA_001_http_writer.py`、`tests/integration/pipeline/test_FR_QA_001_http_writer.py`、`tests/integration/pipeline/test_NFR_OBS_compose_api.py`

## 3. 已知缺口（按优先级）

1. HTTP 缺省仍请求内同步；无对象字节下载 HTTP（契约如此）；refresh/会话仍 memory
2. Golden Set 120 条仍为合成；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank/Writer 冒烟；无 MinerU
3. `must_change_password` 不入库；version.idempotency_key 未入库；初始密码传递机制仍 TBD-P0

## 4. 下一刀建议（技术刀）

**ND-STG-03** MinerU 云 API 解析器，或 **ND-W3-05** 会话/refresh 跨进程存储。

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
