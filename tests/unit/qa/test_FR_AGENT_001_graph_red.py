"""
ND-AGENT-02-G Red 用例：真实 StateGraph 工具循环

测试策略：验证 LangGraph StateGraph 的条件循环和工具选择行为。
当前状态：RED - 等待 02-A/B/C 签认和 02-D/E/F 实现。

核心验证：
- FR-AGENT-001: 观察驱动下一步工具选择
- 真实 StateGraph 条件路由
- 工具调用 ID 关联
- 状态消息管理
"""

from __future__ import annotations

import pytest

# ====================
# RED: 观察驱动决策测试
# ====================


def test_FR_AGENT_001_observation_drives_next_tool():
    """
    Given: Fake 模型收到不同的 Observation
    When: StateGraph 执行下一轮决策
    Then: 应该根据观察内容选择不同的工具或结束

    场景 1: 空搜索结果 → 改写查询再搜索
    场景 2: 有结果但不足 → read_evidence
    场景 3: 证据充分 → finalize

    当前状态: RED - StateGraph 尚未实现
    """
    # TODO: 实现 StateGraph 条件循环
    #
    # # 场景 1: 空结果导致改写
    # fake_model = FakeAgentModel([
    #     {"tool_calls": [{"id": "call_1", "name": "search_knowledge", "args": {"query": "迟到"}}]},
    #     {"tool_calls": [{"id": "call_2", "name": "search_knowledge", "args": {"query": "考勤迟到规定"}}]},
    # ])
    # empty_observation = ToolMessage(
    #     tool_call_id="call_1",
    #     content=json.dumps({"status": "empty", "evidences": []})
    # )
    #
    # state = {"messages": [..., empty_observation]}
    # next_action = graph.invoke(state)
    #
    # # 验证模型选择了不同的查询
    # assert next_action["messages"][-1].tool_calls[0]["args"]["query"] != "迟到"
    #
    # # 场景 2: 有摘要但需要读取正文
    # partial_observation = ToolMessage(
    #     tool_call_id="call_2",
    #     content=json.dumps({
    #         "status": "found",
    #         "evidences": [{"evidence_id": "ev_1", "summary": "考勤规定..."}]
    #     })
    # )
    #
    # state = {"messages": [..., partial_observation]}
    # next_action = graph.invoke(state)
    #
    # # 验证选择了 read_evidence
    # assert next_action["messages"][-1].tool_calls[0]["name"] == "read_evidence"
    # assert next_action["messages"][-1].tool_calls[0]["args"]["evidence_id"] == "ev_1"
    #
    # # 场景 3: 证据充分，选择结束
    # full_observation = ToolMessage(
    #     tool_call_id="call_3",
    #     content=json.dumps({"status": "success", "content": "完整考勤规定内容..."})
    # )
    #
    # state = {"messages": [..., full_observation]}
    # next_action = graph.invoke(state)
    #
    # # 验证选择了 finalize
    # assert next_action.get("control_intent") == "finalize"

    pytest.skip("等待 02-D/E/F 实现和 02-G StateGraph 接入")


def test_FR_AGENT_001_empty_observation_changes_query():
    """
    Given: 首次搜索返回空结果
    When: 模型决策
    Then: 应该改写查询而不是重复相同搜索

    当前状态: RED - 查询改写逻辑尚未实现
    """
    # TODO: 实现查询改写检测
    # fake_model = FakeAgentModel([
    #     {"tool_calls": [{"id": "call_1", "name": "search_knowledge", "args": {"query": "Q1"}}]},
    #     {"tool_calls": [{"id": "call_2", "name": "search_knowledge", "args": {"query": "Q2"}}]},
    # ])
    #
    # # 第一次空结果
    # result = execute_graph_with_empty_search(fake_model)
    #
    # # 验证第二次查询不同
    # assert result.queries[0] != result.queries[1]
    # # 验证消耗了 rewrite 预算
    # assert result.budget.rewrite_count == 1

    pytest.skip("等待 02-F 预算实现和 02-G StateGraph")


# ====================
# RED: StateGraph 结构测试
# ====================


def test_FR_AGENT_001_graph_has_required_nodes():
    """
    Given: StateGraph 定义
    When: 检查节点和边
    Then: 应该包含所有必需的节点：
         - input_guard
         - load_context
         - agent
         - tool_guard
         - tools
         - observation_guard
         - structured_finalize
         - verify
         - persist_result

    当前状态: RED - StateGraph 尚未定义
    """
    # TODO: 实现 StateGraph
    # from pivot.qa.graph import create_agent_graph
    #
    # graph = create_agent_graph()
    #
    # required_nodes = [
    #     "input_guard",
    #     "load_context",
    #     "agent",
    #     "tool_guard",
    #     "tools",
    #     "observation_guard",
    #     "structured_finalize",
    #     "verify",
    #     "persist_result"
    # ]
    #
    # for node in required_nodes:
    #     assert node in graph.nodes

    pytest.skip("等待 02-G StateGraph 实现")


def test_FR_AGENT_001_conditional_edges_correct():
    """
    Given: StateGraph 定义
    When: 检查条件边
    Then: agent 应该有条件路由到：
         - tool_guard (如果有 tool_calls)
         - structured_finalize (如果 finalize 意图)
         - clarify/refuse (其他控制意图)

    当前状态: RED - 条件边尚未实现
    """
    # TODO: 实现条件边
    # graph = create_agent_graph()
    #
    # # 验证 agent 节点有条件路由
    # agent_edges = graph.get_conditional_edges("agent")
    # assert "tool_guard" in agent_edges
    # assert "structured_finalize" in agent_edges
    # assert "clarify" in agent_edges
    # assert "refuse" in agent_edges

    pytest.skip("等待 02-G StateGraph 实现")


# ====================
# RED: 工具调用 ID 关联测试
# ====================


def test_FR_AGENT_001_tool_message_matches_call_id():
    """
    Given: AIMessage 包含 tool_calls 与 ID
    When: 工具执行并返回 ToolMessage
    Then: ToolMessage.tool_call_id 必须匹配原 tool_call.id

    当前状态: RED - 工具执行器尚未实现 ID 关联
    """
    # TODO: 实现工具调用 ID 关联
    # tool_call = {
    #     "id": "call_abc123",
    #     "name": "search_knowledge",
    #     "args": {"query": "考勤"}
    # }
    #
    # ai_message = AIMessage(content="", tool_calls=[tool_call])
    #
    # # 执行工具
    # tool_message = tool_executor.execute(tool_call, run_context)
    #
    # # 验证 ID 匹配
    # assert tool_message.tool_call_id == "call_abc123"

    pytest.skip("等待 02-D 工具执行器实现")


def test_FR_AGENT_001_missing_tool_call_id_rejected():
    """
    Given: 模型返回的 tool_call 缺少 ID
    When: 解析 AIMessage
    Then: 应该拒绝并标记为协议错误，不执行工具

    当前状态: RED - ID 验证尚未实现
    """
    # TODO: 实现 ID 验证
    # invalid_tool_call = {
    #     # "id": 缺失
    #     "name": "search_knowledge",
    #     "args": {"query": "test"}
    # }
    #
    # with pytest.raises(ProtocolViolationError, match="missing tool_call_id"):
    #     parse_tool_calls([invalid_tool_call])

    pytest.skip("等待 02-A Contract 和 Adapter 实现")


# ====================
# RED: 单工具调用限制测试
# ====================


def test_FR_AGENT_002_multiple_calls_fail_closed():
    """
    Given: 模型在一个响应中返回多个 tool_calls
    When: 工具守卫验证
    Then: 应该拒绝并返回协议错误，不执行任何工具

    当前状态: RED - 多调用检测尚未实现
    """
    # TODO: 实现单工具调用限制
    # multiple_calls = [
    #     {"id": "call_1", "name": "search_knowledge", "args": {"query": "Q1"}},
    #     {"id": "call_2", "name": "read_evidence", "args": {"evidence_id": "ev_1"}}
    # ]
    #
    # ai_message = AIMessage(content="", tool_calls=multiple_calls)
    #
    # state = {"messages": [ai_message]}
    #
    # # tool_guard 节点应该拒绝
    # with pytest.raises(MultipleToolCallsError):
    #     graph.nodes["tool_guard"](state)

    pytest.skip("等待 02-G StateGraph 和 tool_guard 实现")


# ====================
# RED: 状态管理测试
# ====================


def test_FR_AGENT_001_agent_state_includes_messages():
    """
    Given: StateGraph 执行
    When: 访问状态
    Then: AgentState 应该包含：
         - messages: 完整的消息历史
         - evidence_registry: 证据注册表
         - budget: 预算状态
         - step/attempt: 稳定标识

    当前状态: RED - AgentState 定义尚未完成
    """
    # TODO: 实现 AgentState
    # from pivot.qa.state import AgentState
    #
    # state = AgentState(
    #     messages=[],
    #     evidence_registry=EvidenceRegistry(),
    #     budget=BudgetState(...),
    #     step=1,
    #     attempt=1
    # )
    #
    # # 验证可序列化
    # serialized = state.dict()
    # restored = AgentState(**serialized)
    #
    # assert restored.step == 1
    # assert restored.attempt == 1

    pytest.skip("等待 02-A Contract 和 AgentState 实现")


def test_FR_AGENT_001_state_preserves_tool_message_order():
    """
    Given: 执行多轮工具调用
    When: 检查消息历史
    Then: AIMessage 和对应的 ToolMessage 应该严格交替出现

    当前状态: RED - 消息顺序管理尚未实现
    """
    # TODO: 实现消息顺序验证
    # fake_model = FakeAgentModel([
    #     {"tool_calls": [{"id": "call_1", "name": "search_knowledge", ...}]},
    #     {"tool_calls": [{"id": "call_2", "name": "read_evidence", ...}]},
    # ])
    #
    # result = execute_graph(fake_model)
    #
    # messages = result.state["messages"]
    #
    # # 验证顺序：HumanMessage, AIMessage(tool), ToolMessage, AIMessage(tool), ToolMessage, ...
    # for i, msg in enumerate(messages[1:], 1):  # 跳过初始 HumanMessage
    #     if i % 2 == 1:  # 奇数位应该是 AIMessage
    #         assert isinstance(msg, AIMessage)
    #         if msg.tool_calls:
    #             # 下一条应该是对应的 ToolMessage
    #             next_msg = messages[i + 1]
    #             assert isinstance(next_msg, ToolMessage)
    #             assert next_msg.tool_call_id == msg.tool_calls[0]["id"]

    pytest.skip("等待 02-G StateGraph 实现")


# ====================
# RED: 预算耗尽终止测试
# ====================


def test_FR_AGENT_004_exhausted_budget_stops_graph():
    """
    Given: 预算即将耗尽
    When: 检查是否允许下一次工具调用
    Then: 应该终止图执行，不继续调用工具

    当前状态: RED - 预算检查尚未集成到 StateGraph
    """
    # TODO: 实现预算门禁集成
    # fake_model = FakeAgentModel([
    #     {"tool_calls": [{"id": "call_1", "name": "search_knowledge", ...}]},
    #     {"tool_calls": [{"id": "call_2", "name": "search_knowledge", ...}]},  # 应该被阻止
    # ])
    #
    # budget_state = BudgetState(
    #     tool_calls_remaining=1,  # 只允许一次
    #     rewrite_remaining=0
    # )
    #
    # result = execute_graph(fake_model, initial_budget=budget_state)
    #
    # # 验证只执行了一次工具调用
    # tool_messages = [m for m in result.state["messages"] if isinstance(m, ToolMessage)]
    # assert len(tool_messages) == 1
    #
    # # 验证最终状态反映预算耗尽
    # assert result.run.state in ["refused", "partial"]

    pytest.skip("等待 02-F 预算实现和 02-G StateGraph 集成")


# ====================
# RED: 图不是线性函数包装测试
# ====================


def test_FR_AGENT_001_not_just_wrapped_linear_function():
    """
    Given: StateGraph 实现
    When: 检查图结构
    Then: 必须是真实的 LangGraph StateGraph，不是简单包装的线性函数

    验证点：
    - 使用 StateGraph 类
    - 有条件边（不是固定顺序）
    - 使用 Checkpointer（即使是 InMemorySaver）

    当前状态: RED - 这是架构验证测试
    """
    # TODO: 实现真实 StateGraph
    # from langgraph.graph import StateGraph
    # from pivot.qa.graph import create_agent_graph, AgentState
    #
    # graph = create_agent_graph()
    #
    # # 验证是 StateGraph 实例
    # assert isinstance(graph, StateGraph)
    #
    # # 验证有条件边（不是固定线性）
    # conditional_edges = graph.get_all_conditional_edges()
    # assert len(conditional_edges) > 0
    #
    # # 验证可以编译并使用 checkpointer
    # compiled = graph.compile(checkpointer=InMemorySaver())
    # assert compiled is not None

    pytest.skip("等待 02-G StateGraph 实现 - 这是架构关键验证")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
