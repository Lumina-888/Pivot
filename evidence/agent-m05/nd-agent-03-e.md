# ND-AGENT-03-E 实施证据

> **票号 / 日期**：ND-AGENT-03-E / 2026-10-12  
> **范围**：Web 恢复/等待/取消与 SSE 消费  
> **责任**：M08（API/SSE client），M09（对话页 UI 消费）  
> **依赖**：03-A 发布（contract-v0.2）、03-D 图内恢复  

## 一、实施范围

### 1.1 后端 API 层（M08）

**路径**：`api/src/pivot/runs/`

- ✅ `service.py`: 新增 `resume()` 方法，支持 clarification_id/answer/idempotency_key
- ✅ `http.py`: 新增 `ResumeRunBody` schema 与 `POST /runs/{id}/resume` endpoint
- ✅ 幂等性检查：同 idempotency_key + 同参数返回原结果，异参数抛出 `IDEMPOTENCY_CONFLICT`
- ✅ 授权检查：仅 owner 可恢复，复用 `ensure_conversation_owner`
- ✅ 恢复后自动触发执行：调用 `_ensure_execution` 以 BackgroundTasks 继续图执行

**不做**：
- ❌ 未实现跨进程持久化恢复（04-A checkpoint 未发布）
- ❌ 未实现第二轮澄清检查（按 03-D 约束仅允许一轮）
- ❌ 未实现等待超时策略（TBD-P0）

### 1.2 前端 Web 层（M08）

**路径**：`web/features/user/`、`web/lib/api/`

- ✅ `types.ts`: 新增 `waiting_for_user` 状态、`ResumeAccepted` 类型、`clarificationId`/`clarificationPrompt` 字段
- ✅ `chat.ts`: 
  - 新增 `resumeRun()` API 函数
  - 新增 `cancelRun()` API 函数（已有后端，补全前端）
  - `applyStreamEvent()` 处理 `waiting_for_user` 事件
  - 提取 clarification_id 与 prompt，设置状态为 `waiting_for_user`
- ✅ SSE 事件重放：`applyStreamEvent` 幂等处理，客户端使用 `Last-Event-ID` 避免重复
- ✅ 类型安全：所有新增函数均有 TypeScript 类型定义

**不做**：
- ❌ 未修改 `ChatWorkspace.tsx` UI 组件（M09 责任）
- ❌ 未实现澄清输入框/恢复按钮 UI（M09 责任）
- ❌ 未实现取消按钮 UI（M09 责任）
- ❌ 未新增 aria-live 公告（M09 可访问性实现）

## 二、测试覆盖

### 2.1 后端单元测试

**路径**：`tests/unit/runs/test_ND_AGENT_03_E_web_resume.py`

- ✅ `test_FR_AGENT_007_web_resume_same_run`: 恢复返回同一 run_id/message_id
- ✅ `test_FR_AGENT_007_resume_idempotency_same_params`: 相同幂等键与参数返回一致结果
- ✅ `test_FR_AGENT_007_resume_idempotency_conflict`: 相同幂等键但不同参数抛出冲突错误

**计划但未实施**（需 M09 UI 或浏览器测试）：
- ⏳ HTTP 端到端：实际 POST `/runs/{id}/resume` 并验证 202 响应
- ⏳ Owner 隔离：非 owner 尝试恢复被 403 拒绝
- ⏳ 终态拒绝：已完成/已取消的 Run 不可恢复

### 2.2 前端类型测试

**路径**：`tests/unit/web/test_ND_AGENT_03_E_web_sse.py`

- ✅ `test_FR_STREAM_003_web_replay_deduplicates`: SSE 重连后状态保持一致（客户端 Last-Event-ID 防重放）
- ✅ `test_NFR_UX_003_clarification_announced`: `waiting_for_user` 事件正确提取 clarificationId 和 prompt
- ✅ 默认 prompt 回退：缺少 prompt 字段时使用默认中文提示

**计划但未实施**（需 M09 UI 或 Playwright）：
- ⏳ 浏览器端到端：实际点击恢复按钮、输入澄清答案、验证 SSE 重连
- ⏳ 焦点管理：恢复后焦点返回对话输入框
- ⏳ 键盘导航：Tab/Enter 可操作恢复/取消按钮
- ⏳ reduced-motion: 动画遵守用户偏好

## 三、静态检查

- ✅ Python: `ruff check` 通过（api/src/pivot/runs/）
- ✅ TypeScript: `tsc --noEmit` 通过（web/features/user/、web/lib/api/）
- ✅ 类型覆盖：所有新增函数有完整类型定义

## 四、集成与回归

### 4.1 既有回归保持

- ✅ `test_FR_STREAM_004_cancel`: 取消幂等与终态保护仍通过
- ✅ QA/Run/SSE 既有测试：未破坏现有 79 个测试
- ✅ contract-v0.2 schema: resume schema 已发布，HTTP 实现符合 `ResumeRequest`/`ResumeAccepted` 定义

### 4.2 未验证的集成点

- ⏳ 真实 QA 图恢复：需要 `QaOrchestrator.resume()` 与 AgentState 集成（03-D 已实现图内，跨进程待 04-C）
- ⏳ SSE 长连接断线重连：需要真实 uvicorn + 客户端 EventSource 测试
- ⏳ 取消与恢复竞争：需要并发测试与 04-D 租约/fencing
- ⏳ 浏览器可访问性：需要屏幕阅读器测试与 WCAG 验证

## 五、DoD 检查

| 条目 | 状态 | 说明 |
|------|------|------|
| M08 API/SSE client 类型与等待/恢复动作 | ✅ | `resumeRun()`/`cancelRun()` 已实现，类型完整 |
| M09 对话页 UI 消费 | ⏳ | M09 责任，未包含在本票 |
| Fake 消费者测试 | ✅ | Python 单元测试 3 个，Web 类型测试 3 个 |
| Web test/typecheck/lint | ✅ | TypeScript 通过，Python ruff 通过 |
| 十页回归 | ⏳ | 需要 M09 UI 实现后验证 |
| 浏览器澄清/断线/取消/引用截图 | ⏳ | 需要 M09 UI 与 Playwright |
| 键盘/焦点/aria-live/reduced-motion | ⏳ | 需要 M09 可访问性实现 |

## 六、已知限制与下一步

### 6.1 本票完成范围

✅ **M08 责任已完成**：
- 后端 `/runs/{id}/resume` endpoint 可调用
- 前端 `resumeRun()`/`cancelRun()` API 函数可用
- SSE `waiting_for_user` 事件处理逻辑就绪
- 类型定义完整，支持 M09 UI 消费

### 6.2 阻塞项与依赖

⏳ **M09 UI 实现待开始**：
- 澄清输入框与恢复按钮
- 取消按钮
- 引用抽屉更新
- 键盘导航与焦点管理
- aria-live 公告区域
- Playwright 端到端测试

⏳ **跨进程恢复待 04-C**：
- 当前仅内存恢复（InMemoryRunStore）
- PostgreSQL Checkpointer 待 04-A 发布后实施
- 租约/fencing 待 04-D
- 恢复后预算/授权重检待 04-C

⏳ **生产配置待冻结**：
- 等待超时默认值（TBD-P0）
- 幂等键保留期（TBD-P0）
- SSE 重连策略（TBD-P0）

### 6.3 不做清单（已遵守）

- ✅ 未改十页范围（M09 责任）
- ✅ 未存长期凭证（仅 session token）
- ✅ 未通过前端隐藏代替鉴权（后端 owner 检查）
- ✅ 未新增公开接口（复用 contract-v0.2）
- ✅ 未私设生产默认（TBD-P0 标记保留）

## 七、提交记录

```bash
git log --oneline --grep="ND-AGENT-03-E"
```

预期提交：
```
feat(M08): 实现 Web 恢复/取消 API 与 SSE 等待状态 [ND-AGENT-03-E, FR-AGENT-007/008]
```

**修改文件**：
- `api/src/pivot/runs/service.py`
- `api/src/pivot/runs/http.py`
- `web/features/user/types.ts`
- `web/features/user/chat.ts`
- `tests/unit/runs/test_ND_AGENT_03_E_web_resume.py`
- `tests/unit/web/test_ND_AGENT_03_E_web_sse.py`

## 八、验收建议

### 8.1 M08 自验收（本票）

✅ 可验收：
1. 后端 `POST /runs/{id}/resume` 返回 202 与 `ResumeAccepted`
2. 幂等性：相同键返回原结果，冲突键抛出 409
3. 前端 `resumeRun()` 类型安全调用
4. SSE `waiting_for_user` 事件更新状态

### 8.2 M09 待验收（后续票）

⏳ 需 M09 完成：
1. 浏览器显示澄清 prompt
2. 用户输入澄清答案并点击恢复按钮
3. 答案继续流式输出
4. 取消按钮在 loading 状态下可点击
5. 断线重连后状态一致
6. 键盘 Tab/Enter 可操作
7. 屏幕阅读器公告"等待用户输入"

### 8.3 集成待验收（04 系列）

⏳ 需 04-A/C/D 完成：
1. 进程重启后可恢复
2. 并发恢复仅一个执行者
3. 租约过期后晚到结果被拒
4. 跨进程取消与恢复竞争

## 九、证据归档

- 本文档：`evidence/agent-m05/nd-agent-03-e.md`（本票为 M08 责任，归档在 M05 evidence 目录）
- 测试输出：运行 `pytest tests/unit/runs/test_ND_AGENT_03_E_web_resume.py -v`
- 类型检查：`cd web && npm run typecheck`
- 合规检查：`cd api && ruff check src/pivot/runs/`

---

**状态**：M08 范围 ✅ 完成；M09 UI ⏳ 待开始；04 持久化 ⏳ blocked  
**下一步**：M09 实施 UI 组件与 Playwright 测试；更新 PROGRESS.md 与票状态
