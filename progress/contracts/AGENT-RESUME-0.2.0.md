# AGENT-RESUME Contract v0.2.0

| 项目 | 内容 |
|---|---|
| 契约 ID | AGENT-RESUME |
| 版本 | 0.2.0 |
| 发布日期 | 2026-10-12 |
| 状态 | **released** |
| 基础提案 | AGENT-RESUME-0.1-draft.1 |
| 签认文档 | [20261012-03-a-final-signoff.md](../approvals/20261012-03-a-final-signoff.md) |
| 适用范围 | Agent 澄清恢复公开 API (contract-v0.2) |

## 1. 发布摘要

本契约定义 Agent 模式下澄清恢复的公开 HTTP 接口，作为 contract-v0.1 的兼容扩展发布为 **contract-v0.2**。

**核心能力**:
- 用户可在 `waiting_for_user` 状态提供澄清回复
- 服务端幂等受理并恢复原 Run 执行
- 累计预算、期限、次数不重置
- 支持取消与恢复的正确竞争

**关键约束**:
- Owner-only，管理员无代理权限
- 只允许一次澄清（第二轮禁止）
- 终态不可覆盖
- 敏感信息不泄露

## 2. 公开 API

### 2.1 恢复请求

**Endpoint**: `POST /api/v1/runs/{id}/resume`

**认证**: Bearer access token (沿用 contract-v0.1)

**请求 Body**:
```json
{
  "clarification_id": "string (必需, 非空, ≤128)",
  "answer": "string (必需, 非空, ≤10000)",
  "idempotency_key": "string (必需, 非空, ≤128)"
}
```

**字段约束**:
- 所有字段必需，严格拒绝额外字段
- `clarification_id`: 服务端生成，来自等待视图
- `answer`: 用户输入，最大 10,000 字符，拒绝控制字符和超过 1000 字符的单行
- `idempotency_key`: 客户端生成，UUID 格式推荐

**成功响应 (HTTP 202)**:
```json
{
  "run_id": "string",
  "message_id": "string",
  "clarification_id": "string",
  "state": "resuming",
  "request_id": "string"
}
```

**说明**:
- 202 表示受理成功，不保证执行完成
- `state=resuming` 是历史受理状态
- 实时状态通过 `GET /runs/{id}` 或 SSE 获取
- 同键同参重放返回相同回执（即使已终态）

### 2.2 等待视图

**扩展**: `GET /api/v1/runs/{id}` 的 RunDetail

**新增可选字段** (仅 `waiting_for_user` 状态返回):
```json
{
  "clarification": {
    "clarification_id": "string",
    "prompt": "string"
  }
}
```

**说明**:
- `clarification_id`: 用于恢复请求
- `prompt`: 脱敏后的澄清提示，不含 reasoning/工具参数/敏感证据
- 其他状态不返回此字段

### 2.3 SSE 事件

**新增事件类型**: `waiting_for_user`

**事件格式** (沿用 contract-v0.1 SSE 信封):
```json
{
  "run_id": "string",
  "message_id": "string",
  "seq": 42,
  "timestamp": "2026-10-12T10:00:00Z",
  "stage": "clarifying",
  "payload": {
    "clarification_id": "string",
    "prompt": "string"
  }
}
```

**说明**:
- 客户端收到 `waiting_for_user` 后应调用 GET 获取完整等待视图
- SSE 连接保持，恢复后继续推送后续事件
- 不是终态事件，不发布 token/citation/completed

## 3. 错误码

### 3.1 新增错误码

| HTTP | code | retryable | 触发条件 |
|---|---|---|---|
| 409 | RESUME_NOT_ALLOWED | false | 错误状态/已消费/第二轮/配置不足 |
| 409 | CLARIFICATION_MISMATCH | false | 澄清 ID 不匹配 |
| 422 | INVALID_RESUME_REQUEST | false | 非法 JSON/字段/大小 |

### 3.2 现有错误码语义

| HTTP | code | resume 场景 |
|---|---|---|
| 401 | AUTH_INVALID_CREDENTIALS | 缺失/无效/过期凭证 |
| 403 | AUTH_FORBIDDEN | 账户禁用 |
| 404 | RESOURCE_NOT_FOUND | 不存在/不可见/非 owner/会话删除 (统一 404，不泄露) |
| 409 | IDEMPOTENCY_CONFLICT | 同键异参 |
| 409 | RUN_CANCELLED | 已取消 |
| 409 | RUN_TIMEOUT | 已超时 |
| 503 | PROVIDER_TEMPORARY_ERROR | 临时不可用，可重试 |

**错误优先级**: 鉴权 → 已受理键 → 终态/时限 → 状态/澄清ID → 其他门禁

**错误 Body**: 沿用 SPEC §5.1 格式，`details` 固定空对象，不反射用户输入

## 4. 行为契约

### 4.1 鉴权

- ✅ Owner-only: 只有 Run owner 可恢复
- ✅ 管理员无代理权限
- ✅ 不存在/不可见/他人 Run 统一 404，不泄露存在性
- ✅ 重放时重新验证 Bearer/active/token_version

### 4.2 幂等性

- ✅ 命名空间: `(principal_id, run_id, operation=resume, idempotency_key)` UNIQUE
- ✅ 精确值绑定: `(clarification_id, answer)` 不 trim/归一化
- ✅ 同键同参: 重放 202 历史回执，即使已终态
- ✅ 同键异参: 409 IDEMPOTENCY_CONFLICT
- ✅ 实现建议: SHA256(固定顺序JSON) 索引 + 原始值精确比较

### 4.3 单次受理

- ✅ 每 `(run_id, clarification_id)` 最多一个有效受理
- ✅ 第二轮 interrupt 禁止 (409 RESUME_NOT_ALLOWED)
- ✅ 不同键并发: 只有一个成功，失败者 409
- ✅ 条件转移: `waiting_for_user → resuming` 与受理记录原子事务

### 4.4 预算与期限

- ✅ 累计预算不重置
- ✅ 已消耗 rewrite/clarification 次数不重置
- ✅ 原截止时间 `deadline_at` 不延长
- ✅ 预算耗尽: 安全终止 (failed/refused/uncertain)

### 4.5 竞争与终态保护

- ✅ 取消优先: 取消先提交则恢复失败；恢复先提交则取消幂等读终态
- ✅ 终态不可覆盖: answered/cancelled/failed 不能被晚到恢复改写
- ✅ 执行边界重检: 模型/工具/提交前验证 cancelled/租约/fencing

### 4.6 资源重检

- ✅ 恢复前重新验证: active/owner/scope/文档可见性/外发资格
- ✅ 版本固定: graph/state/prompt/tools/model 不匹配则 fail closed
- ✅ 删除/撤销: 不能用旧证据或换供应商绕过

## 5. 生产配置

| 策略 | 批准值 | 来源 |
|---|---|---|
| 等待超时 | 24 小时 | Owner 批准 |
| 回复字符上限 | 10,000 字符 | Owner 批准 |
| 单行字符上限 | 1,000 字符 | 安全建议 |
| 幂等记录保留期 | 7 天 | Owner 批准 |

**说明**:
- 超时后等待自动失效，新恢复请求 409 RUN_TIMEOUT
- 超过字符上限: 422 INVALID_RESUME_REQUEST
- 保留期后幂等记录可清理，但已终态 Run 保留

## 6. 客户端集成指南

### 6.1 推荐流程

1. 监听 SSE，收到 `waiting_for_user` 事件
2. 调用 `GET /runs/{id}` 获取 `clarification` 视图
3. 显示 `prompt`，提供输入框
4. 生成 `idempotency_key` (UUID 推荐)
5. 提交 `POST /runs/{id}/resume`
6. 收到 202，继续监听 SSE 后续事件
7. 缓存 `idempotency_key` 到 localStorage (防止刷新重复提交)

### 6.2 错误处理

- 409 RESUME_NOT_ALLOWED: 显示 "无法恢复，请检查状态"
- 409 CLARIFICATION_MISMATCH: 显示 "澄清 ID 不匹配，请刷新页面"
- 409 IDEMPOTENCY_CONFLICT: 显示 "请求参数已变更，请勿重复提交"
- 422 INVALID_RESUME_REQUEST: 显示 "输入无效，请检查字符数"

### 6.3 旧客户端兼容

- 不支持 `waiting_for_user` 的旧客户端应禁用 Agent 模式
- 保持线性 RAG 或在设置中隐藏 Agent 功能
- contract-v0.1 客户端可继续使用 (不会遇到 waiting_for_user)

## 7. 实现状态

### 7.1 已完成

- ✅ 后端 API: `POST /runs/{id}/resume` (M08)
- ✅ 前端 API 函数: `resumeRun()` / `cancelRun()` (M08)
- ✅ SSE 事件处理: `waiting_for_user` (M08)
- ✅ Web UI: 澄清输入框、恢复/取消按钮 (M09)
- ✅ 类型检查: TypeScript/Python 通过
- ✅ 单元测试: 3 passed (幂等性/冲突检测)

### 7.2 已知限制

- ⚠️ 当前使用 InMemorySaver (内存恢复)
- ⚠️ BackgroundTasks 执行意图 (不保证崩溃恢复)
- ⚠️ SQLite 开发环境 (非生产 PG)

### 7.3 待完成 (不阻塞 v0.2 发布)

- ⏳ Playwright 端到端测试
- ⏳ HTTP 真实负向测试
- ⏳ 并发崩溃测试 (依赖 04-A PG)
- ⏳ 真实 PostgreSQL Checkpointer (04-C)
- ⏳ 持久化执行意图队列 (04-A ExecutionIntent)

## 8. 升级指南

### 8.1 从 contract-v0.1 升级

**API 变更**:
- ✅ 新增 `POST /runs/{id}/resume` (可选使用)
- ✅ `GET /runs/{id}` 可能返回 `clarification` 字段 (向后兼容)
- ✅ SSE 新增 `waiting_for_user` 事件 (可忽略)
- ✅ 新增 3 个错误码 (已有客户端不会遇到)

**兼容性**: ✅ 完全向后兼容
- 不使用 Agent 模式的客户端无影响
- 旧客户端不会收到 `waiting_for_user` 事件

**升级窗口**: 1 个月 (2026-10-12 ~ 2026-11-12)
- 新功能立即可用
- 旧客户端可继续使用 v0.1 端点
- 建议在窗口期内升级以支持 Agent 模式

### 8.2 开发者检查清单

- [ ] 更新 OpenAPI schema 添加 `/runs/{id}/resume`
- [ ] 更新 SPEC.md 附录 B 添加 3 个错误码
- [ ] 更新客户端 SDK (如有)
- [ ] 测试 `waiting_for_user` 事件处理
- [ ] 实现幂等键生成与缓存
- [ ] 配置生产数值 (24h/10000/7天)

## 9. 后续计划

### 9.1 下一个契约版本

**contract-v0.3** (依赖 04-A):
- 持久化执行意图 (ExecutionIntent 表)
- PostgreSQL Checkpointer
- 租约与 fencing
- 真实崩溃恢复

### 9.2 未来扩展可能

- 多轮澄清 (当前只允许一次)
- 澄清附件上传 (当前只支持文本)
- 澄清历史记录查看
- 澄清超时自动取消策略

---

**发布批准**: Owner (2026-10-12)  
**下一步**: 开始 04-A 持久化契约签认
