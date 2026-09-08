# 变更申请：M11 挂载注入的 /api/v1/runs 与 SSE

- **日期**：2026-09-07
- **申请人**：Wave 3 集成会话（M05 HTTP 适配 + M01 会话认领 + M11 create_app 挂载）
- **背景**：搜索 HTTP 已合入。M05 领域已有 Run 幂等、QaOrchestrator 与内存 EventLog。前台对话需要 `POST /runs` 与 `GET /runs/{id}/events`。MODULE_SPEC 规定 `http/**` 不得实现问答/SSE 业务。本切片不挂 `POST /conversations`。
- **原契约/现状**：`contract-v0.1` 已定义 Run 创建/详情/SSE/取消；`create_app` 仅挂认证、文档与搜索。首次问答时会话目录尚无 owner，`authorize_conversation` 会 404。
- **拟变更内容**：
  - M01 `AuthService.ensure_conversation_owner`：目录无会话则认领当前用户，已有则走既有会话授权（用户 404 / 管理员 403）；
  - M05 `api/src/pivot/runs/http.py`：`build_runs_router(runs, qa, auth)`，同步执行编排后返回 Run；SSE 按 EventLog 补发（含 Last-Event-ID）；取消幂等；响应不含思考链/系统 Prompt；`initial_state` 仅回传 `{"state": ...}`，不冻结 TBD 字段；
  - M11 `create_app(runs=..., qa=..., auth=...)`：三者齐备才挂载，缺任一 fail-closed；
  - MODULE_SPEC 注明问答 HTTP 适配位于 `api/src/pivot/runs/http.py`（M05）；
  - 不挂会话 CRUD、预览/下载、导出；不冻结超时/重试预算。
- **影响模块**：M01（认领）；M05（router）；M11（挂载与 pipeline 测试）；M00 契约已存在。
- **兼容方案**：默认 `create_app()` 不变；领域单测不依赖 FastAPI。
- **测试 ID**：`test_FR_STREAM_001_http_*`、`test_FR_STREAM_002_003_http_sse_*`、`test_FR_STREAM_004_http_cancel_*`、`test_FR_RBAC_002_http_run_owner_isolation`。
- **是否触发 ADR**：否。
- **审核结果**：2026-09-07 Wave 3 集成会话 **批准**。
