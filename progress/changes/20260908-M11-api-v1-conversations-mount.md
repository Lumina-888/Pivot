# 变更申请：M11 挂载注入的 /api/v1/conversations

- **日期**：2026-09-08
- **申请人**：Wave 3 集成会话（M05 会话领域 + HTTP 适配 + M11 create_app 挂载）
- **背景**：改密/管理用户 HTTP 已合入。前台对话页需要会话列表、创建、详情、删除与消息。当前仅在 `POST /runs` 时 `ensure_conversation_owner` 认领 owner，没有会话实体。MODULE_SPEC 规定 `http/**` 不得实现问答业务。
- **原契约/现状**：`contract-v0.1` 已定义 `GET/POST /conversations`、`GET/DELETE /conversations/{id}`、`GET /conversations/{id}/messages`；`create_app` 已挂认证、文档、搜索、Run/SSE、导出/审计。
- **拟变更内容**：
  - M05 `ConversationService`：内存会话（title/scope/owner、隐藏删除）；`scope_type=document` 时 `scope_document_id` 必填；列表只返回当前用户未隐藏会话；消息由已持久化 Run 合成（user 问题 + assistant 终态答案），不含 Prompt/思考链；
  - M05 `api/src/pivot/runs/conversations_http.py`：`build_conversations_router(conversations, auth)`，Bearer；创建后认领 owner；GET/DELETE/messages 走既有会话授权（用户 404 / 管理员 403）；创建 201；删除 204；`pagination: null`；
  - M11 `create_app(conversations=..., auth=...)`：二者齐备才挂载，缺任一 fail-closed；
  - MODULE_SPEC 注明会话 HTTP 适配位于 `runs/conversations_http.py`（M05）；
  - 不挂预览/下载、metrics/tasks；不冻结分页 TBD-P0。
- **影响模块**：M05（领域与 router）；M11（挂载与 pipeline 测试）；M01 catalog 仅只读消费 `claim_conversation`。M00 契约已存在。
- **兼容方案**：默认 `create_app()` 不变；既有 Run HTTP 仍可按 conversation_id 认领；领域单测不依赖 FastAPI。
- **测试 ID**：`test_FR_RBAC_002_http_conversations_*`、`test_FR_STREAM_001_http_conversation_*`、`test_NFR_OBS_auth_only_app_does_not_mount_conversations`。
- **是否触发 ADR**：否。
- **审核结果**：2026-09-08 Wave 3 集成会话 **批准**。
