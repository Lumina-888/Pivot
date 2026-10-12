# ND-AGENT-03-E M09 UI 实施证据

> **票号 / 日期**：ND-AGENT-03-E (M09 部分) / 2026-10-12  
> **范围**：澄清输入框、恢复/取消按钮 UI  
> **责任**：M09（对话页 UI 消费）  
> **依赖**：03-E M08 部分已完成（API/SSE client）  

## 一、实施范围

### 1.1 ChatWorkspace UI 组件

**路径**：`web/features/user/components/ChatWorkspace.tsx`

✅ **已实现**：
1. 新增 `clarificationAnswer` 状态管理澄清回复输入
2. 新增 `onCancel()` 函数调用后端取消接口
3. 新增 `onResume()` 函数处理澄清回复提交
4. `waiting_for_user` 状态显示澄清 prompt banner
5. `waiting_for_user` 状态切换到澄清输入表单（替代普通问题输入）
6. 澄清表单包含：
   - 文本输入框（带 aria-label 和 sr-only label）
   - "取消" 按钮
   - "继续" 提交按钮
7. `loading` 状态显示取消按钮
8. `cancelled` 状态显示取消横幅
9. 恢复后自动重新连接 SSE 继续接收事件
10. 使用生成的幂等键避免重复提交

### 1.2 可访问性支持

✅ **已实现**：
- `<label for="clarification-input" className="sr-only">` - 屏幕阅读器标签
- `aria-label="澄清回复"` - 输入框 ARIA 标签
- 语义化 HTML：`<form>` / `<textarea>` / `<button type="submit">`
- 取消按钮明确 `type="button"` 避免表单提交
- 禁用加载中的输入框 `disabled={state.status === "loading"}`

⏳ **计划但未实施**（需额外工作）：
- aria-live 公告区域动态通知状态变化
- 焦点管理（恢复后焦点回到输入框）
- 键盘导航验证
- reduced-motion 动画适配

### 1.3 用户体验

✅ **已实现**：
- 清晰的视觉状态：loading / waiting_for_user / cancelled
- 双按钮布局（取消 + 继续）
- 输入验证：空白回复不提交
- 状态保护：只在 waiting_for_user 时允许恢复
- 错误处理：显示 API 错误信息

## 二、测试覆盖

### 2.1 后端集成

✅ **已通过**：
- `tests/unit/runs/test_ND_AGENT_03_E_web_resume.py` - 3 passed
- 恢复返回同一 run_id/message_id
- 幂等性检查（同键同参/异参）

### 2.2 前端类型检查

✅ **已通过**：
- TypeScript `tsc --noEmit` - 无错误
- ESLint - 无警告
- 所有函数调用类型匹配

### 2.3 计划但未实施

⏳ **需 Playwright 端到端测试**：
- 浏览器显示澄清 prompt
- 用户输入澄清答案并点击继续
- 取消按钮功能验证
- SSE 断线重连后状态一致
- 键盘 Tab/Enter 导航
- 屏幕阅读器公告

## 三、用户流程

### 3.1 正常澄清流程

1. 用户提问 → Run 进入 `waiting_for_user` 状态
2. UI 显示澄清 prompt banner（来自后端）
3. 普通输入框被澄清输入框替代
4. 用户输入补充信息并点击"继续"
5. 调用 `resumeRun()` 提交回复（带幂等键）
6. 状态切换为 `loading`
7. SSE 继续接收后续事件（token/citation/completed）
8. 显示最终答案

### 3.2 取消流程

**场景 A - 加载中取消**：
1. 问答进行中（`loading` 状态）
2. 显示取消按钮
3. 用户点击取消
4. 调用 `cancelRun()`
5. 状态切换为 `cancelled`
6. 中止 SSE 连接

**场景 B - 等待澄清时取消**：
1. Run 等待用户回复（`waiting_for_user` 状态）
2. 澄清表单显示取消按钮
3. 用户点击取消
4. 调用 `cancelRun()`
5. 状态切换为 `cancelled`

### 3.3 错误处理

- API 调用失败 → 状态切换为 `failed`，显示错误消息
- 空白回复 → 阻止提交
- 非法状态 → 守卫条件阻止操作

## 四、代码变更

### 4.1 新增状态

```typescript
const [clarificationAnswer, setClarificationAnswer] = useState("");
```

### 4.2 新增函数

```typescript
async function onCancel() { ... }
async function onResume(event: FormEvent<HTMLFormElement>) { ... }
```

### 4.3 UI 条件渲染

```typescript
{state.status === "waiting_for_user" ? (
  <form className="composer" onSubmit={onResume}>
    {/* 澄清输入框 + 取消/继续按钮 */}
  </form>
) : (
  <form className="composer" onSubmit={onSend}>
    {/* 普通问题输入框 + 发送按钮 */}
  </form>
)}
```

## 五、DoD 检查

| 条目 | 状态 | 说明 |
|------|------|------|
| 澄清输入框 | ✅ | textarea + placeholder + aria-label |
| 恢复按钮 | ✅ | "继续" 提交按钮 |
| 取消按钮 | ✅ | loading 和 waiting_for_user 状态可用 |
| 状态横幅 | ✅ | waiting_for_user / cancelled 显示提示 |
| API 集成 | ✅ | resumeRun() / cancelRun() 调用正确 |
| 类型安全 | ✅ | TypeScript 通过 |
| ESLint | ✅ | 无警告 |
| 可访问性基础 | ✅ | label / aria-label / 语义化 |
| 键盘导航 | ⏳ | 需手动测试 |
| 焦点管理 | ⏳ | 需实现 |
| aria-live | ⏳ | 需实现 |
| Playwright 测试 | ⏳ | 需编写 |
| reduced-motion | ⏳ | 需验证 |

## 六、已知限制

### 6.1 可访问性待完善

- **aria-live 公告**：状态变化未通过屏幕阅读器公告
- **焦点管理**：恢复后焦点未自动返回输入框
- **键盘陷阱**：未验证 Tab 循环和焦点顺序
- **动画尊重**：未检查 `prefers-reduced-motion`

### 6.2 端到端测试缺失

- 无浏览器自动化测试覆盖完整用户流程
- 无 SSE 断线重连真实场景验证
- 无并发澄清/取消竞争测试

### 6.3 跨进程恢复待完成

- 当前仅内存恢复（InMemoryRunStore）
- 进程重启后无法恢复等待状态
- 依赖 04-C PostgreSQL Checkpointer

## 七、下一步

### 7.1 优先级 P0（阻塞验收）

1. ✅ M09 UI 基础实现（本票）
2. ⏳ Playwright 端到端测试
3. ⏳ 可访问性增强（aria-live / 焦点管理）

### 7.2 优先级 P1（增强体验）

1. ⏳ 键盘快捷键（Ctrl+Enter 提交）
2. ⏳ 加载进度指示器
3. ⏳ 取消确认对话框
4. ⏳ 输入历史记录

### 7.3 依赖后续票

- 04-C：跨进程恢复
- 04-D：租约/fencing
- ND-AGENT-05：真实模型工具能力

## 八、验收建议

### 8.1 手动验收步骤

1. 启动 dev server：`npm run dev`
2. 访问 `/chat`
3. 提问触发澄清（需 03-D 图实现支持）
4. 验证澄清 UI 显示
5. 输入补充信息并继续
6. 验证答案继续流式输出
7. 新问题测试取消功能
8. 验证键盘 Tab 导航
9. 使用屏幕阅读器测试 aria 标签

### 8.2 自动化验收（待实现）

```bash
# Playwright 测试（计划）
npm run test:e2e -- --grep "clarification"
npm run test:e2e -- --grep "cancel"
npm run test:e2e -- --grep "accessibility"
```

## 九、证据归档

- 本文档：`evidence/agent-m09/nd-agent-03-e-ui.md`
- 代码提交：git log --grep="ND-AGENT-03-E.*M09"
- TypeScript 检查：`cd web && npm run typecheck`
- ESLint 检查：`cd web && npm run lint`

---

**状态**：M09 UI 基础实现完成 ✅  
**下一步**：Playwright 端到端测试 + 可访问性增强  
**阻塞项**：04-C 跨进程恢复、真实 Agent 图澄清场景
