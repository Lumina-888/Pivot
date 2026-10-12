# ND-AGENT-02-E 开发完成交接

**日期**: 2026-10-12  
**会话**: 根据进度继续开发 pivot：ND-AGENT-02-E  
**基线**: main `f3e0b62`

## 完成事项

### ND-AGENT-02-E: 可信上下文与外发门禁 ✅

**状态**: 核心实现完成，测试通过，已提交  
**Commit**: `f3e0b62`

#### 实现内容

1. **RunContext（可信上下文）**
   - 服务端注入的不可伪造权限依据
   - 包含 run_id、conversation_id、principal_id、scope 等
   - 完整性验证，防止伪造

2. **ContextGuard（上下文防护）**
   - 防止工具参数注入权限字段（principal_id、scope_type 等）
   - 验证证据访问权限（Run 隔离、用户隔离）
   - 阻止跨 Run 和跨用户访问

3. **OutboundGuard（外发门禁）**
   - 检查证据注册表中的受限文档
   - 阻止受限证据（external_llm_allowed=False）发送给外部模型
   - 检测消息历史中的受限内容泄露
   - 允许内部模型访问受限数据

#### 测试覆盖

**FR-AGENT-003 必测用例（全部通过）**:
- ✅ test_FR_AGENT_003_model_cannot_expand_scope
- ✅ test_FR_AGENT_003_restricted_evidence_blocks_external_call
- ✅ test_FR_AGENT_003_restricted_content_leak_in_history
- ✅ test_FR_AGENT_003_document_injection_cannot_change_tools

**完整测试**: 17/17 通过（100%覆盖）

**全部 QA 测试**: 145 passed, 22 skipped

#### 文件清单

**新增**:
- `api/src/pivot/qa/agent_context.py` (335 行)
- `tests/unit/qa/test_agent_context.py` (535 行)
- `evidence/agent-m01/nd-agent-02-e.md` (实施报告)

**修改**:
- `api/src/pivot/qa/errors.py` (添加 AgentSecurityError)

## 规范符合性

### FR-AGENT-003 对应关系

| 规范要求 | 实现 | 测试 |
|---------|------|------|
| 服务端重建 RunContext | ✅ create_trusted_context | ✅ 4 个创建测试 |
| 防止身份/scope 伪造 | ✅ ContextGuard | ✅ 7 个注入防护测试 |
| 每次调用检查外发 | ✅ OutboundGuard | ✅ 6 个外发门禁测试 |
| 受限内容不外发 | ✅ 证据和历史检查 | ✅ 泄露检测测试 |
| Run/用户隔离 | ✅ 证据访问验证 | ✅ 隔离测试 |

### AGENT_SPEC §5 符合性

- ✅ §5.1 可信 RunContext - 完整实现
- ⚠️ §5.2 可序列化 AgentState - 不含凭证（待集成到图）
- ✅ §5.3 每次调用外发门禁 - 已实现检查逻辑

## 当前项目状态

### ND-AGENT-02 子票进度

| 子票 | 状态 | 说明 |
|------|------|------|
| 02-A | released | 内部契约已发布 |
| 02-B | released | 预算契约已发布 |
| 02-C | released-conditional | 依赖验证（遥测/许可证审核 pending）|
| 02-D | implementation-ready | 工具实现（部分已落地）|
| 02-E | **done** | **本次完成** |
| 02-F | implementation-ready | 预算实现（部分已落地）|
| 02-G | blocked | StateGraph 循环（等待 02-D/E/F）|
| 02-H | blocked | 答案门禁接图（等待 02-G）|

### 依赖关系解锁

✅ **02-E 完成解锁**:
- 02-G 可以开始集成可信上下文
- 后续所有票可以使用安全上下文和外发门禁

## 下一步工作

### 立即可做（优先级 P0）

1. **集成到 AgentGraph**
   - 修改 `create_agent_graph` 接收 `RunContext` 参数
   - 在 `decide` 节点前调用 `OutboundGuard.check_before_model_call`
   - 在 `execute_tools` 节点前调用 `ContextGuard.validate_tool_execution`
   - 添加集成测试

2. **更新 AgentState**
   - 添加 `context_snapshot` 字段以支持 checkpoint
   - 实现 RunContext 序列化/反序列化
   - 在恢复时重建和验证上下文

3. **推进 02-G（StateGraph 工具循环）**
   - 02-D、02-E、02-F 核心逻辑已完成
   - 可以开始真实 StateGraph 集成
   - 需要确保所有 Guard 正确集成

### 待定事项

- 遥测审核（7 天内，02-C 附加条件）
- 许可证确认（7 天内，02-C 附加条件）
- 生产预算数值确定（DR-010）
- 原生组件审核（生产部署前）

## 技术亮点

### 安全设计

1. **不可伪造性**: RunContext 使用 frozen dataclass，只能通过工厂函数创建
2. **多层防护**: ContextGuard（参数）+ OutboundGuard（内容）双重保护
3. **细粒度检测**: 检测证据 ID 引用和文本片段泄露
4. **明确错误**: 安全违规有清晰的错误类型和消息

### 测试策略

1. **FR 对应**: 每个 FR-AGENT-003 要求都有明确的测试
2. **负向测试**: 重点测试各种攻击和绕过尝试
3. **隔离测试**: 跨 Run、跨用户的完整隔离验证
4. **集成测试**: 完整的外发门禁工作流测试

## 风险与限制

### 当前限制

1. **未集成到图**: Guard 逻辑已实现但未接入 AgentGraph
2. **泄露检测简单**: 基于文本片段匹配，未来可增强为语义检测
3. **恢复场景未测**: checkpoint 恢复后的上下文验证待后续补充

### 缓解计划

1. 下一步立即集成到 AgentGraph（02-G）
2. 在 DR-004 中考虑语义相似度检测
3. 在 03-D/04-C 中补充恢复场景测试

## 验收标准

### ND-AGENT-02-E DoD ✅

- ✅ 实现可信 RunContext
- ✅ 实现 ContextGuard 和 OutboundGuard
- ✅ 通过所有 FR-AGENT-003 测试
- ✅ 跨 Run/用户隔离测试通过
- ✅ 外发门禁负向测试通过
- ✅ 代码通过 Python clean
- ⏳ 集成到 AgentGraph（下一步）
- ⏳ 端到端测试（下一步）

## 参考文档

- [AGENT_SPEC.md](../../spec/AGENT_SPEC.md) - §5 可信上下文与外发
- [FR-AGENT-003](../../spec/AGENT_SPEC.md#4-工具白名单与证据) - 规范要求
- [实施报告](../../evidence/agent-m01/nd-agent-02-e.md) - 详细技术文档
- [tickets.md](../tickets/spec-1.1-remaining.md) - ND-AGENT-02-E 工单

## 建议的下一步

**选项 1（推荐）**: 立即集成到 AgentGraph
- 修改 `agent_graph.py` 使用 RunContext
- 在决策和工具节点前加入 Guard 检查
- 添加端到端安全测试

**选项 2**: 推进 02-G（StateGraph 循环）
- 将 02-D/E/F 的实现整合成完整的图
- 确保工具循环中的安全检查

**选项 3**: 更新项目文档
- 更新 tickets.md 中 02-E 的状态
- 在 PROGRESS.md 中记录里程碑
- 准备 02-G 的 DoR 检查

## 工作区状态

**已提交**:
- commit `f3e0b62`: ND-AGENT-02-E 完整实现

**未提交修改**: 无

**新增未跟踪文件**: 无

**建议**: 工作区干净，可以继续下一步工作

---

**交接状态**: ✅ 完成  
**下次启动建议**: 从集成到 AgentGraph 开始，或推进 02-G
