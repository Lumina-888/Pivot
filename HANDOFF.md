# 问枢 Pivot 会话交接清单

> **日期**：2026-10-02\
> **ND-AGENT-01 修改前基线**：`7ed2748`（`main`；旧 `M11-v0.25.0` 为历史 tag）。\
> **性质**：当前规格迁移与历史实现交接。需求以 SPEC-1.1 / `spec/AGENT_SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 MODULE-SPEC-1.2 / `AGENTS.md` 为准。\
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `SPEC.md` → `spec/AGENT_SPEC.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. ND-AGENT-01 已完成；后续下一刀 **ND-AGENT-02：内部模型/工具/预算 Contract 前置**（业务实现仍 blocked）。本会话按 Owner 指示仅收尾 01 后停止，不继续后续票。目标已改为 LangGraph 受控 ReAct，旧固定主图/暂缓申请/ND-W3-09 已由 ADR-009 取代；工具、预算、恢复与 checkpoint 按新 Contract 逐刀实施。旧 ECS apply/live 检索票不再是默认路径。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / **企业 Golden Set 脱敏摘录** / Fake embedder / stdlib BM25 / 进程内 5 并发或备份 roundtrip / Dockerfile fixture / opt-in 100k Fake retrieve / HTTP Embedding·bge Fake transport / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / sqlite 导出任务 / sqlite refresh/会话 / sqlite Run/EventLog / eager Celery / Compose Celery fixture / Fake MinIO worker ingest / Compose api 共享存储注入 / Fake worker Qdrant upsert / Compose api celery 注入 / Compose Qdrant·Redis 注入 / Compose 登录限流注入 / **Wave 3 夹具收口** / PATCH 角色 HTTP / **ingest 共用 HTTP Embedding** / **Fake HTTP Writer** / **Fake MinerU 解析器** / **staging Compose overlay** / **sqlite refresh/Conversation** / **sqlite Run/EventLog** / **SSE 长连接夹具** / **真实解析库 extra** / **opt-in Playwright 十页** 标成 `GATE-P0 verified`。`wave-3-integrated` **不等于** P0 通过。

## 1. 产品现状

### 当前目标与未完成项

- SPEC-1.1 / AGENT-SPEC-1.0 / ADR-009 已接受；FR-AGENT-005 的 ND-AGENT-01 安全子集已实现，完整 FR-AGENT 仍未验收。
- 当前仍为纯 Python 线性 RAG，无 LangGraph/tool calling/checkpoint；自由 Markdown 背书漏洞、引用绑定/支持门禁与校验前草稿泄漏已修复。
- 本刀采用严格 JSON + 完整 Chunk 原文支持门禁 + 受控渲染 + HTTP 提交后发布；Verifier/非法格式/权限拒绝不放行、不切备用供应商。未安装新依赖或新增恢复路由。
- 预算 DR-010、恢复接口/错误映射 Contract、checkpoint DR-011 仍阻断对应后续票。
- 本轮 Python **661 passed / 19 skipped**；M05 **79 passed**；Web **18/13/8 passed**，typecheck/lint、ruff/compileall passed；证据 `evidence/agent-m05/nd-agent-01.md`。完整事务/outbox/语义 Judge/跨进程恢复仍待后续票；以下数字为 2026-09-14 历史记录。

### 历史 Wave 3 实现

Python **608 passed / 19 skipped**（Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6）。Web **18 passed**（M08）+ **13 passed**（M09 Fake）。opt-in Playwright **11 passed**。

- Wave 3 夹具已收口：Compose api/web/worker（profile `app`）共享 PG/MinIO/Qdrant/Redis；api 注入 celery ingest 与登录限流阈值/窗口；worker 可接 Qdrant。
- `PIVOT_STORAGE=postgres` 时用户目录、文档事实、导出任务、hashed refresh、Conversation 与 Run/EventLog 可跨装配（CI sqlite）；Claim/Citation 仍不入库。
- `POST /runs` 立即返回 `received`；`GET /runs/{id}/events` 按帧长连接推送；Next SSE Route Handler 去缓冲；uvicorn 长连接 opt-in（`PIVOT_REQUIRE_SSE_LIVE=1`，CI 默认 skip）。
- HTTP 缺省仍进程内 ingest。
- `PATCH /admin/users/{id}` 已处理 `status` / `role` / `reset_password`。
- `PIVOT_PARSER=local|mineru|native`；缺省 local 启发式/stdlib；`native` 需 `worker[parse]`；扫描件 OCR 属 P2。
- `PIVOT_REQUIRE_PLAYWRIGHT=1` 覆盖 SPEC 十页；CI 默认 skip。
- Golden Set 默认仍为 v0.2-synthetic 120 条；v0.3-enterprise 为 120 条脱敏摘录（Fake Keyword 诊断）。GATE-P0 全部 unverified。
- tag `wave-3-integrated` 仅表示夹具收口，不等于 P0 通过，不得宣称 production-ready。
- ND-STG-04 overlay：`docker-compose.staging.yml` + nginx 默认 `127.0.0.1:80` 反代 web；8GiB limits fixture；未 SSH。

## 2. 历史 2026-09-14 切片

1. ND-P0-01 填写：120 条脱敏项目摘录（十层各 12）
   - 变更：`progress/changes/20260914-M11-golden-set-enterprise-fill.md`
   - 证据：`evidence/wave3-m11/golden-set-enterprise.md`
   - 测试：`tests/integration/pipeline/test_NFR_QUAL_golden_set_enterprise.py`
   - 生成：`ops/golden_set_enterprise.py`（源目录不入库原文）

## 3. 已知缺口（按优先级）

1. HTTP 缺省仍请求内 ingest；无对象字节下载 HTTP（契约如此）；Claim/Citation 仍不入库；`/admin/metrics` `/admin/tasks` HTTP 仍未挂
2. 企业 Golden Set 仍是脱敏摘录 + Fake Keyword，不是业务复核或 live 检索；无 Qdrant 100k 索引峰值；无新 ECS 备份恢复；无 live Embedding/rerank/Writer/MinerU 冒烟；staging ECS 未 apply
3. `must_change_password` 不入库；version.idempotency_key 未入库；初始密码传递机制仍 TBD-P0；OCR 属 P2

## 4. 当前下一刀

ND-AGENT-01 done；后续 ND-AGENT-02 Contract 前置 → ND-AGENT-03 → ND-AGENT-04 → ND-AGENT-05。预算/锁依赖/恢复/checkpoint/live 环境不满足时保持 blocked。本会话在 01 收尾后停止。

不要把脱敏摘录或合成 120 条标成 GATE-P0-002 通过。

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
