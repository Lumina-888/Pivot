# 问枢 Pivot 会话交接清单

> **日期**：2026-09-14  
> **HEAD**：`5d883c4`（`main`，tag `M11-v0.25.0`）。  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：Owner 提供低敏规章制度与标注人后填写企业 Golden Set（v0.3 仍 0 条），或提供 SSH/安全组/磁盘/域名后实施 **ND-STG-04 ECS apply**。ND-P0-01 规范/空 schema/评测入口已入库。staging：硅基仅 embedding/rerank；DeepSeek 官方 `deepseek-flash`；小米官方 `mimo-v2.5`；MinerU 官方云。见 `progress/changes/20260910-M00-dev-staging-vendors.md`。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / **企业 Golden Set 空 schema** / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / sqlite 导出任务 / sqlite refresh/会话 / sqlite Run/EventLog / eager Celery / Compose Celery fixture / Fake MinIO worker ingest / Compose api 共享存储注入 / Fake worker Qdrant upsert / Compose api celery 注入 / Compose Qdrant·Redis 注入 / Compose 登录限流注入 / **Wave 3 夹具收口** / PATCH 角色 HTTP / **ingest 共用 HTTP Embedding** / **Fake HTTP Writer** / **Fake MinerU 解析器** / **staging Compose overlay** / **sqlite refresh/Conversation** / **sqlite Run/EventLog** / **SSE 长连接夹具** / **真实解析库 extra** / **opt-in Playwright 十页** 标成 `GATE-P0 verified`。`wave-3-integrated` **不等于** P0 通过。

## 1. 产品现状

Python **608 passed / 19 skipped**（Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）。Web **18 passed**（M08）+ **13 passed**（M09 Fake）。opt-in Playwright **11 passed**。

- Wave 3 夹具已收口：Compose api/web/worker（profile `app`）共享 PG/MinIO/Qdrant/Redis；api 注入 celery ingest 与登录限流阈值/窗口；worker 可接 Qdrant。
- `PIVOT_STORAGE=postgres` 时用户目录、文档事实、导出任务、hashed refresh、Conversation 与 Run/EventLog 可跨装配（CI sqlite）；Claim/Citation 仍不入库。
- `POST /runs` 立即返回 `received`；`GET /runs/{id}/events` 按帧长连接推送；Next SSE Route Handler 去缓冲；uvicorn 长连接 opt-in（`PIVOT_REQUIRE_SSE_LIVE=1`，CI 默认 skip）。
- HTTP 缺省仍进程内 ingest。
- `PATCH /admin/users/{id}` 已处理 `status` / `role` / `reset_password`。
- `PIVOT_PARSER=local|mineru|native`；缺省 local 启发式/stdlib；`native` 需 `worker[parse]`；扫描件 OCR 属 P2。
- `PIVOT_REQUIRE_PLAYWRIGHT=1` 覆盖 SPEC 十页；CI 默认 skip。
- Golden Set 默认仍为 v0.2-synthetic 120 条；v0.3-enterprise 为空 schema（`awaiting_annotation`）。GATE-P0 全部 unverified。
- tag `wave-3-integrated` 仅表示夹具收口，不等于 P0 通过，不得宣称 production-ready。
- ND-STG-04 overlay：`docker-compose.staging.yml` + nginx 默认 `127.0.0.1:80` 反代 web；8GiB limits fixture；未 SSH。

## 2. 本会话完成的一刀

1. ND-P0-01 工程前置：标注规范 + 空企业 schema + 评测入口
   - 变更：`progress/changes/20260914-M11-golden-set-enterprise-schema.md`
   - 证据：`evidence/wave3-m11/golden-set-enterprise.md`
   - 测试：`tests/integration/pipeline/test_NFR_QUAL_golden_set_enterprise.py`

## 3. 已知缺口（按优先级）

1. HTTP 缺省仍请求内 ingest；无对象字节下载 HTTP（契约如此）；Claim/Citation 仍不入库；`/admin/metrics` `/admin/tasks` HTTP 仍未挂
2. 企业 Golden Set 仍 0 条；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank/Writer/MinerU 冒烟；staging ECS 未 apply
3. `must_change_password` 不入库；version.idempotency_key 未入库；初始密码传递机制仍 TBD-P0；OCR 属 P2

## 4. 下一刀建议（技术刀）

Owner 提供低敏规章制度后填写 v0.3（100~150，十层每层 ≥10），或提供 SSH/安全组/磁盘/域名后实施 ND-STG-04 ECS apply（不得把 overlay 文件当成已部署）。

不要把空 schema 或合成 120 条标成企业集。

## 5. 恢复命令

```bash
cd "E:/AI Project/Pivot"
git switch main
git log --oneline --decorate -8
python ops/run_grouped_tests.py --skip-web
python ops/run_golden_set.py --enterprise
```

opt-in 十页：`python ops/run_playwright_login.py`（需 `api[playwright]` 与 Chromium）。

## 6. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。
