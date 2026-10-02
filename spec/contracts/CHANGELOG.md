# spec/contracts/ 变更记录

格式：契约版本（manifest 版本）— 日期 — 变更摘要与兼容性说明。

## 2026-10-02 — SPEC-1.1 目标迁移说明（不发布新契约版本）

- SPEC-1.1/AGENT-SPEC/ADR-009 接受 LangGraph 受控 ReAct，旧固定主图不再是目标。
- contract-v0.1 信封、字段、事件类型和路由结构不变；仅更新 SSE stage 描述为兼容公开投影，不能据阶段名称推断固定执行顺序。
- 恢复接口、新错误映射和 Agent payload 尚未冻结；后续 Contract 切片再发布版本并跑消费者测试。
- 当前机器契约与旧绿灯不代表新 Agent/状态迁移/答案门禁已实现。

## 0.1.0 — 2026-09-06 — 建立 `contract-v0.1` 草案

- **来源**：SPEC-1.0（`SPEC.md` §5.1~5.5、§2.2、§3.3、附录 B/C/D）。
- **新增文件**：
  - `openapi.yaml`：覆盖 SPEC §5.2~5.5 全部 26 条路径、30 个 operation；统一错误包 `Error`（code 枚举 = SPEC 附录 B.1 全部 19 码）；`/auth/login`、`/auth/refresh` 之外所有接口强制 bearerAuth（FR-RBAC-001/003、FR-AUTH-001）；SSE 端点声明 `text/event-stream`；上传端点声明 `multipart/form-data` + `Idempotency-Key`；
  - `sse.schema.json`：信封字段 required 六元组；`x-event-types`（10 类）与 `x-terminal-event-types`（5 类终态）机器可读；`additionalProperties: false` 拒绝信封外字段；
  - `worker.schema.json`：`oneOf` 三分支，ok/insufficient 禁带 error_code、failed 必带非空 error_code。
- **草案期结构声明（TBD-P0，未冻结）**：分页参数与 pagination 结构、`RunCreated.initial_state`、`AdminMetrics` 字段集、token 有效期、初始密码传递机制——均仅注解，不承诺默认值。
- **行为口径声明（依 SPEC 固化）**：`DocumentSummary.current_version` 允许为空对象或 null（无 ready 版本）；版本 `state` 取值见 SPEC 附录 C.3（13 态）；Run 状态见附录 C.2（13 态）；ExportTask 状态见附录 C.5（6 态）。
- **测试**：`tests/contract/` 48 项契约测试全部通过（错误包、OpenAPI 路由/方法/安全、SSE schema 与序列约束、Worker schema）。
- **兼容性**：基线建立，无历史版本可比；此后兼容字段增加提升 0.2.0（minor），破坏性变更提升 1.0.0（major）并需兼容窗口/API 版本升级与 ADR。
- **下一步（Wave 0 退出评审）**：M03 数据模型、M08 client、M01/M02/M04/M05/M06/M07 依本版契约消费；发现缺口经 `progress/changes/` 提交变更申请后由本模块升级 minor。
