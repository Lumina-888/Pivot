# Agent Phase 3 完成交接文档

> **会话日期**：2026-10-11  
> **交接时间**：2026-10-11 23:30  
> **项目**：Pivot - 毕业设计 RAG 问答系统  
> **当前分支**：main  
> **最新提交**：eef40df

---

## 1. 本次会话完成内容

### Phase 3: 端到端测试与闭环

**目标**：让 Agent 图能够完整运行，并通过 Fake 模型验证完整流程。

#### 1.1 修复的问题

1. **路由无法识别 LangGraph 消息**
   - `should_continue` 只处理 dict 格式，无法识别 `AIMessage` 对象
   - 修复：新增 `_message_route` 辅助函数，同时支持 LangGraph 和 dict

2. **finalize 节点是占位符**
   - 返回固定文本，不使用真实证据
   - 修复：接入 `StructuredFinalizer`，从 `EvidenceRegistry` 获取已授权证据

3. **run_agent 未传递模型和 Finalizer**
   - 无法使用真实模型或自定义 Finalizer
   - 修复：新增 `model`/`draft_writer`/`verifier`/`finalizer` 可选参数

4. **预算耗尽时抛出异常**
   - `BudgetExhaustedError` 导致图崩溃
   - 修复：decide 节点捕获异常，返回 `budget_exhausted` 状态

5. **路由硬编码预算策略**
   - `should_continue` 写死了 `max_model_calls=10`
   - 修复：通过闭包传递 `budget_policy`

#### 1.2 新增功能

**文件**：`tests/e2e/test_agent_complete_flow.py`

4 个端到端测试（Fake 模型，无付费 API）：

1. **`test_complete_question_answering_flow`**
   - 完整流程：搜索 → 读取证据 → 生成答案
   - 验证：答案引用已授权原文、预算正确追踪、模型接收完整上下文

2. **`test_multi_turn_tool_sequence_keeps_question_context`**
   - 多轮工具调用保持原始问题
   - 验证：第二次决策仍能看到原始问题和上一轮工具结果

3. **`test_budget_exhaustion_stops_before_another_model_call`**
   - 预算耗尽时优雅停止
   - 验证：不再发起新的模型调用，返回 `budget_exhausted` 状态

4. **`test_run_agent_rejects_non_positive_budget`**
   - 非法预算拒绝
   - 验证：`max_model_calls=0` 抛出 `ValueError`

**测试辅助类**：
- `ScriptedModel`：按调用次序返回预设 AIMessage
- `CorpusRetriever`：内存检索器，支持 `resolve_evidence`
- `EchoWriter`：简单草稿生成器，直接返回证据文本

---

## 2. 代码变更

### 2.1 核心修改

**文件**：`api/src/pivot/qa/agent_graph.py`

1. **导入新增**：
   ```python
   from pivot.qa.agent_budget import BudgetExhaustedError, ...
   from pivot.qa.agent_finalizer import StructuredFinalizer
   from pivot.qa.ports import DraftWriter, Verifier
   ```

2. **AgentNodes 构造函数**：
   ```python
   def __init__(self, ..., finalizer: StructuredFinalizer | None = None)
   ```

3. **decide 节点预算耗尽处理**：
   ```python
   try:
       budget_guard.before_model_call()
   except BudgetExhaustedError:
       return {"final_answer": {"status": "budget_exhausted", ...}}
   ```

4. **finalize 节点**：
   ```python
   evidences = EvidenceRegistry.restore(...).list_for_run(...)
   question = _latest_human_content(state["messages"])
   if self.finalizer is None:
       final_answer = {"answer": "...", "claims": [], "status": "completed"}
   else:
       final_answer = self.finalizer.finalize(question, evidences)
   ```

5. **should_continue 路由**：
   ```python
   def should_continue(state, budget_policy=None):
       message_type, tool_calls = _message_route(state["messages"][-1])
       if message_type == "ai" and tool_calls:
           return "tools"
       if message_type == "ai":
           return "finalize"
       return "end"
   ```

6. **辅助函数**：
   - `_message_route(message)`: 识别 AIMessage/ToolMessage/dict
   - `_message_dict(message)`: 统一转换为 dict 格式
   - `_latest_human_content(messages)`: 提取原始问题

7. **create_agent_graph 新增参数**：
   ```python
   def create_agent_graph(
       retriever, budget_policy, model=None, *,
       draft_writer=None, verifier=None, finalizer=None
   ):
   ```

8. **run_agent 新增参数**：
   ```python
   def run_agent(
       question, retriever, budget_policy, run_id, principal_id, ..., *,
       model=None, draft_writer=None, verifier=None, finalizer=None
   ):
   ```

### 2.2 测试文件

**文件**：`tests/e2e/test_agent_complete_flow.py`

- 194 行新代码
- 4 个测试用例
- 3 个测试辅助类
- 1 个预算策略构造函数

---

## 3. 验收结果

### 3.1 测试通过

```bash
pytest tests/e2e/test_agent_complete_flow.py -q
# ....
# 4 passed in 6.50s
```

### 3.2 代码质量

```bash
ruff check api/src/pivot/qa/agent_graph.py tests/e2e/test_agent_complete_flow.py
# All checks passed!

ruff format api/src/pivot/qa/agent_graph.py tests/e2e/test_agent_complete_flow.py
# 2 files reformatted
```

### 3.3 LSP 诊断

```
Files checked: 2
Total diagnostics: 0
```

---

## 4. 当前状态

### 4.1 完成的 Phase

- ✅ Phase 0: 基础设施（工具、预算、图框架、Finalizer）
- ✅ Phase 1: LlamaIndex 检索集成
- ✅ Phase 2: 真实模型集成
- ✅ Phase 3: 端到端测试与闭环

### 4.2 未完成的可选任务

- ⚠️ 真实 API 端到端测试（需要 OPENAI_API_KEY）
- ⚠️ 答案质量人工评估（5-10 个问题）
- ⚠️ 性能测试（响应时间、并发）
- ⚠️ Demo 准备（演示问题、录屏）

### 4.3 已知限制

1. **测试使用 Fake 模型**：不验证真实 LLM 的工具调用质量
2. **检索器为内存实现**：未验证 LlamaIndex 真实索引
3. **无持久化**：Claim/Citation 仍不入库，checkpoint 未实现
4. **无恢复测试**：跨进程恢复、取消、澄清待 Phase 4

---

## 5. 下一步行动

### 5.1 立即可做

1. **更新项目文档**（已完成）
   - [x] 提交代码：commit eef40df
   - [x] 更新路线图：标记 Phase 3 完成
   - [ ] 更新 PROGRESS.md：记录最新进展

2. **可选验证**
   - [ ] 添加真实 API 测试（需要 API key）
   - [ ] 手动测试 5-10 个问题
   - [ ] 记录答案质量

### 5.2 后续工作

按 `progress/tickets.md` 中的优先级：

1. **02-A/B/C 签认**：前置提案仍在 review
2. **03-A 恢复 Contract**：Run/SSE/取消/澄清
3. **04-A 持久化 Contract**：checkpoint/租约/事实一致性
4. **05 模型能力评测**：Agent Golden Set

---

## 6. 工作区状态

### 6.1 未提交的文件

```
 M api/src/pivot/http/bootstrap.py
 M api/src/pivot/http/settings.py
 M api/src/pivot/qa/agent_model.py
```

这些文件包含格式化改动（ruff format），未纳入本次提交。

### 6.2 已提交的文件

```
M  api/src/pivot/qa/agent_graph.py
A  tests/e2e/test_agent_complete_flow.py
```

### 6.3 分支状态

```
main eef40df feat(M05): 完成 Agent Phase 3 端到端闭环 [ND-AGENT-02, Phase 3]
```

---

## 7. 恢复命令

```bash
cd ~/Projects/Pivot
source .venv/bin/activate
git log --oneline -3

# 运行端到端测试
pytest tests/e2e/test_agent_complete_flow.py -v

# 运行完整 Agent 测试套件
pytest tests/unit/qa/test_ND_AGENT_02_*.py -v
pytest tests/integration/agent/ -v
pytest tests/e2e/test_agent_complete_flow.py -v

# 检查代码质量
ruff check api/src/pivot/qa/
ruff format --check api/src/pivot/qa/
```

---

## 8. 关键决策记录

1. **使用 Fake 模型而非真实 API**
   - 原因：避免每次测试消耗 API 配额
   - 权衡：无法验证真实 LLM 的工具调用质量
   - 后续：可添加 opt-in 真实 API 测试

2. **预算耗尽返回特殊状态而非异常**
   - 原因：LangGraph 无法优雅处理节点异常
   - 权衡：需要额外的路由逻辑识别 `budget_exhausted`
   - 好处：测试可验证预算门禁行为

3. **finalize 节点接入 StructuredFinalizer**
   - 原因：答案必须绑定已授权证据
   - 实现：从 `EvidenceRegistry` 获取证据列表
   - 后续：需要真实 DraftWriter 和 Verifier

---

**准备就绪**：Agent 端到端闭环已完成，可进入下一阶段开发。
