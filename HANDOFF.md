# 问枢 Pivot 会话交接清单

> **日期**：2026-09-10  
> **HEAD**：`325fcfc`（`main`，tag 目标 `M11-v0.20.0` / `M01-v0.4.0`）  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**ND-W3-13** Wave 3 收口评审，或 **ND-W3-04** 导出任务 PG，或 **ND-W3-07** PATCH 角色。staging：硅基仅 embedding/rerank；DeepSeek 官方 `deepseek-flash`；小米官方 `mimo-v2.5`；MinerU 官方云。见 `progress/changes/20260910-M00-dev-staging-vendors.md`。阿里云 OS 等 ND-STG-04 再确认。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / eager Celery / Compose Celery fixture / Fake MinIO worker ingest / Compose api 共享存储注入 / Fake worker Qdrant upsert / Compose api celery 注入 / Compose Qdrant·Redis 注入 / Compose 登录限流注入 标成 `GATE-P0 verified`。

## 1. 产品现状

Python **463 passed / 12 skipped**（Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / celery 5.5.3）。

- Compose `api` 注入 `PIVOT_LOGIN_MAX_FAILURES` / `PIVOT_LOGIN_WINDOW_SECONDS`（`${:?}`，不写死次数）；example fixture 占位，不是冻结 TBD-P0。
- 进程外 `assemble_runtime` 两者都缺时仍永不锁定。锁定后仍统一 `AUTH_INVALID_CREDENTIALS`。
- Compose `api` 与 `worker` 注入同一套 `PIVOT_STORAGE` / `PIVOT_DATABASE_URL` / `PIVOT_OBJECT_STORE` / MinIO / `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*` / `PIVOT_CACHE_STORE` / `PIVOT_QUEUE_STORE` / `PIVOT_REDIS_ENDPOINT`（store 选择 `${:?}`，不写死 URL，不静默 memory）。
- HTTP 缺省仍进程内 ingest；`PIVOT_INGEST=celery` 可 eager。worker 装配共享 MinIO/PG runner，拒绝 memory 对象。
- Golden Set 仍为 v0.2-synthetic 120 条。GATE-P0 全部 unverified。未打 `wave-3-integrated`。

## 2. 本会话完成的一刀

1. 登录限流缺省接到 Redis（ND-W3-06）
   - 变更：`progress/changes/20260910-M01-compose-login-rate.md`
   - 入口：`docker-compose.yml` api 环境、`ops/compose.env.example`、`ops/compose-intent.md`、`tests/integration/pipeline/test_FR_AUTH_002_http_login_rate.py`、`evidence/wave3-m11/compose-login-rate.md`

## 3. 已知缺口（按优先级）

1. HTTP 缺省仍请求内同步；导出任务仍内存；PATCH `/admin/users/{id}` 只改 status
2. Golden Set 120 条仍为合成；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank 冒烟
3. `must_change_password` 不入库；version.idempotency_key 未入库

## 4. 下一刀建议（技术刀）

**ND-W3-13** Wave 3 收口评审（A1 已齐；ND-W3-06 已完成；GATE-P0 仍全部 unverified；tag `wave-3-integrated` 不等于 P0 通过）。

或 **ND-W3-04** 导出任务 PostgreSQL 持久化，或 **ND-W3-07** PATCH 角色 / 重置密码 HTTP。

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
