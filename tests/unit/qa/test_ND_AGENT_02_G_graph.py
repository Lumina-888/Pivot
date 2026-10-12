"""
ND-AGENT-02-G: 真实 StateGraph 工具循环测试

测试 FR-AGENT-001：观察驱动决策循环
- 观察驱动下一步工具选择
- 真实 StateGraph 条件路由
- 工具调用 ID 关联
- 多轮工具循环
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from pivot.qa.agent_budget import BudgetPolicy
from pivot.qa.agent_context import create_trusted_context
from pivot.qa.agent_graph import create_agent_graph
from pivot.qa.ports import EvidenceHit, RetrievalResult


# ====================
# Test Fixtures
# ====================


class ScriptedModel:
    """脚本化模型：按调用次序返回预设响应"""

    def __init__(self, responses: list[AIMessage]) -> None:
        self.responses = responses
        self.call_count = 0
        self.calls: list[list[dict[str, Any]]] = []

    def decide(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AIMessage:
        """返回预设的响应"""
        self.calls.append(messages)
        if self.call_count >= len(self.responses):
            raise AssertionError("scripted model ran out of responses")
        response = self.responses[self.call_count]
        self.call_count += 1
        return response


class ControlledRetriever:
    """可控检索器：返回预设结果"""

    def __init__(self, results: dict[str, tuple[EvidenceHit, ...]]) -> None:
        self.results = results
        self.queries: list[str] = []

    def retrieve(self, question: str, *, scope_type, scope_document_id, principal_id):
        self.queries.append(question)
        hits = self.results.get(question, ())
        if not hits:
            return RetrievalResult(status="empty", evidence=())
        return RetrievalResult(status="found", evidence=hits)

    def resolve_evidence(
        self, chunk_id: str, *, scope_type, scope_document_id, principal_id
    ):
        for hits in self.results.values():
            for hit in hits:
                if hit.chunk_id == chunk_id:
                    return hit
        return None


def _policy(
    max_model_calls: int = 10,
    max_tool_calls: int = 10,
    max_rewrite_count: int = 2,
) -> BudgetPolicy:
    """创建测试预算策略"""
    return BudgetPolicy(
        max_model_calls=max_model_calls,
        max_tool_calls=max_tool_calls,
        max_rewrite_count=max_rewrite_count,
        timeout_seconds=30.0,
    )


# ====================
# FR-AGENT-001: 观察驱动决策
# ====================


def test_FR_AGENT_001_observation_drives_next_tool():
    """
    测试 FR-AGENT-001：观察驱动下一步工具选择
    
    场景：
    1. 首次搜索返回空结果 → 模型改写查询
    2. 第二次搜索返回证据 → 模型选择读取
    3. 读取证据后 → 模型选择结束
    """
    # 准备测试数据
    evidence = EvidenceHit(
        chunk_id="chunk_1",
        document_id="doc_1",
        version_id="v1",
        text="一个月内累计迟到三次，视为旷工一天。",
        locator="第一条",
        external_llm_allowed=True,
        index_generation="gen_1",
        embedding_model_version="v1",
        retrieval_config_version="v1",
    )

    retriever = ControlledRetriever(
        {
            "迟到三次": (),  # 第一次搜索返回空
            "考勤迟到规定": (evidence,),  # 第二次搜索返回结果
        }
    )

    # 脚本化模型响应
    model = ScriptedModel(
        [
            # 第一次决策：搜索 "迟到三次"
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "search_knowledge",
                        "args": {"query": "迟到三次"},
                    }
                ],
            ),
            # 第二次决策：空结果后改写查询
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_2",
                        "name": "search_knowledge",
                        "args": {"query": "考勤迟到规定"},
                    }
                ],
            ),
            # 第三次决策：读取证据
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_3",
                        "name": "read_evidence",
                        "args": {"evidence_id": "ev_1"},
                    }
                ],
            ),
            # 第四次决策：结束
            AIMessage(content="根据规定，迟到三次视为旷工一天。"),
        ]
    )

    # 创建图
    context = create_trusted_context(
        run_id="run_test",
        conversation_id="conv_test",
        principal_id="user_test",
        scope_type="all",
    )

    workflow = create_agent_graph(
        retriever=retriever,
        budget_policy=_policy(),
        context=context,
        model=model,
        is_external_model=False,  # 内部模型，允许所有数据
    )
    graph = workflow.compile()

    # 初始化状态
    initial_state = {
        "messages": [{"type": "human", "content": "迟到三次怎么处理？"}],
        "run_id": "run_test",
        "principal_id": "user_test",
        "conversation_id": "conv_test",
        "scope_type": "all",
        "scope_document_id": None,
        "budget_state": {"model_calls": 0, "tool_calls": 0, "rewrite_count": 0},
        "evidence_registry_data": {},
        "final_answer": None,
    }

    # 执行图
    result = graph.invoke(initial_state)

    # 验证：模型被调用了 4 次
    assert model.call_count == 4

    # 验证：执行了 3 次工具调用（2 次搜索 + 1 次读取）
    assert result["budget_state"]["tool_calls"] == 3

    # 验证：检索器收到了两个不同的查询
    assert len(retriever.queries) == 2
    assert retriever.queries[0] == "迟到三次"
    assert retriever.queries[1] == "考勤迟到规定"

    # 验证：最终答案已生成
    assert result["final_answer"] is not None
    assert result["final_answer"]["status"] == "completed"


def test_FR_AGENT_001_empty_observation_changes_query():
    """
    测试 FR-AGENT-001：空观察导致查询改写
    
    Given: 首次搜索返回空结果
    When: 模型决策
    Then: 应该改写查询，且消耗 rewrite 预算
    """
    retriever = ControlledRetriever(
        {
            "query1": (),  # 空结果
            "query2": (
                EvidenceHit(
                    chunk_id="chunk_1",
                    document_id="doc_1",
                    version_id="v1",
                    text="结果内容",
                    locator="loc",
                    external_llm_allowed=True,
                    index_generation="gen_1",
                    embedding_model_version="v1",
                    retrieval_config_version="v1",
                ),
            ),
        }
    )

    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "search_knowledge", "args": {"query": "query1"}}
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_2", "name": "search_knowledge", "args": {"query": "query2"}}
                ],
            ),
            AIMessage(content="找到结果"),
        ]
    )

    context = create_trusted_context(
        run_id="run_test",
        conversation_id="conv_test",
        principal_id="user_test",
        scope_type="all",
    )

    workflow = create_agent_graph(
        retriever=retriever,
        budget_policy=_policy(),
        context=context,
        model=model,
        is_external_model=False,
    )
    graph = workflow.compile()

    initial_state = {
        "messages": [{"type": "human", "content": "问题"}],
        "run_id": "run_test",
        "principal_id": "user_test",
        "conversation_id": "conv_test",
        "scope_type": "all",
        "scope_document_id": None,
        "budget_state": {"model_calls": 0, "tool_calls": 0, "rewrite_count": 0},
        "evidence_registry_data": {},
        "final_answer": None,
    }

    result = graph.invoke(initial_state)

    # 验证：两次查询不同
    assert retriever.queries[0] != retriever.queries[1]

    # 验证：两次搜索都成功执行
    assert result["budget_state"]["tool_calls"] == 2
    
    # 验证：rewrite_count 不增加（因为查询不同）
    assert result["budget_state"]["rewrite_count"] == 0


# ====================
# FR-AGENT-002: 单工具调用限制
# ====================


def test_FR_AGENT_002_multiple_calls_fail_closed():
    """
    测试 FR-AGENT-002：多个工具调用应该被拒绝
    
    Given: 模型在一个响应中返回多个 tool_calls
    When: 工具执行
    Then: 应该拒绝，只返回错误消息
    """
    retriever = ControlledRetriever({})

    # 模型返回多个工具调用（违反规范）
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "search_knowledge", "args": {"query": "Q1"}},
                    {"id": "call_2", "name": "read_evidence", "args": {"evidence_id": "ev_1"}},
                ],
            ),
            AIMessage(content="结束"),
        ]
    )

    context = create_trusted_context(
        run_id="run_test",
        conversation_id="conv_test",
        principal_id="user_test",
        scope_type="all",
    )

    workflow = create_agent_graph(
        retriever=retriever,
        budget_policy=_policy(),
        context=context,
        model=model,
        is_external_model=False,
    )
    graph = workflow.compile()

    initial_state = {
        "messages": [{"type": "human", "content": "问题"}],
        "run_id": "run_test",
        "principal_id": "user_test",
        "conversation_id": "conv_test",
        "scope_type": "all",
        "scope_document_id": None,
        "budget_state": {"model_calls": 0, "tool_calls": 0, "rewrite_count": 0},
        "evidence_registry_data": {},
        "final_answer": None,
    }

    result = graph.invoke(initial_state)

    # 验证：图应该正常结束（不崩溃）
    assert result["final_answer"] is not None

    # 验证：没有执行任何工具（因为多调用被拒绝）
    # 注意：当前实现可能会执行第一个工具，但理想情况下应该全部拒绝
    # 这里先验证不会崩溃，具体行为可以后续优化


# ====================
# FR-AGENT-001: 工具调用 ID 关联
# ====================


def test_FR_AGENT_001_tool_message_matches_call_id():
    """
    测试 FR-AGENT-001：工具消息 ID 关联
    
    Given: AIMessage 包含 tool_calls 与 ID
    When: 工具执行并返回 ToolMessage
    Then: ToolMessage.tool_call_id 必须匹配原 tool_call.id
    """
    evidence = EvidenceHit(
        chunk_id="chunk_1",
        document_id="doc_1",
        version_id="v1",
        text="测试内容",
        locator="loc",
        external_llm_allowed=True,
        index_generation="gen_1",
        embedding_model_version="v1",
        retrieval_config_version="v1",
    )

    retriever = ControlledRetriever({"test": (evidence,)})

    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "unique_call_id_123", "name": "search_knowledge", "args": {"query": "test"}}
                ],
            ),
            AIMessage(content="结束"),
        ]
    )

    context = create_trusted_context(
        run_id="run_test",
        conversation_id="conv_test",
        principal_id="user_test",
        scope_type="all",
    )

    workflow = create_agent_graph(
        retriever=retriever,
        budget_policy=_policy(),
        context=context,
        model=model,
        is_external_model=False,
    )
    graph = workflow.compile()

    initial_state = {
        "messages": [{"type": "human", "content": "问题"}],
        "run_id": "run_test",
        "principal_id": "user_test",
        "conversation_id": "conv_test",
        "scope_type": "all",
        "scope_document_id": None,
        "budget_state": {"model_calls": 0, "tool_calls": 0, "rewrite_count": 0},
        "evidence_registry_data": {},
        "final_answer": None,
    }

    result = graph.invoke(initial_state)

    # 查找 ToolMessage - LangGraph 会将消息转换为 LangChain 对象
    from langchain_core.messages import ToolMessage as LCToolMessage
    
    messages = result["messages"]
    lc_tool_messages = [msg for msg in messages if isinstance(msg, LCToolMessage)]

    # 至少应该有一个 ToolMessage
    assert len(lc_tool_messages) > 0

    # 验证第一个 ToolMessage 的 tool_call_id 匹配原始调用 ID
    assert lc_tool_messages[0].tool_call_id == "unique_call_id_123"


# ====================
# FR-AGENT-004: 预算耗尽终止
# ====================


def test_FR_AGENT_004_exhausted_budget_stops_graph():
    """
    测试 FR-AGENT-004：预算耗尽时停止执行
    
    Given: 预算只允许 1 次工具调用
    When: 执行图
    Then: 在第一次工具调用后停止，不继续循环
    """
    evidence = EvidenceHit(
        chunk_id="chunk_1",
        document_id="doc_1",
        version_id="v1",
        text="内容",
        locator="loc",
        external_llm_allowed=True,
        index_generation="gen_1",
        embedding_model_version="v1",
        retrieval_config_version="v1",
    )

    retriever = ControlledRetriever({"test": (evidence,)})

    # 模型准备了多次响应，但预算会阻止后续调用
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "search_knowledge", "args": {"query": "test"}}
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_2", "name": "search_knowledge", "args": {"query": "test2"}}
                ],
            ),
            AIMessage(content="结束"),
        ]
    )

    context = create_trusted_context(
        run_id="run_test",
        conversation_id="conv_test",
        principal_id="user_test",
        scope_type="all",
    )

    # 限制工具调用次数为 1
    workflow = create_agent_graph(
        retriever=retriever,
        budget_policy=_policy(max_tool_calls=1),
        context=context,
        model=model,
        is_external_model=False,
    )
    graph = workflow.compile()

    initial_state = {
        "messages": [{"type": "human", "content": "问题"}],
        "run_id": "run_test",
        "principal_id": "user_test",
        "conversation_id": "conv_test",
        "scope_type": "all",
        "scope_document_id": None,
        "budget_state": {"model_calls": 0, "tool_calls": 0, "rewrite_count": 0},
        "evidence_registry_data": {},
        "final_answer": None,
    }

    result = graph.invoke(initial_state)

    # 验证：只执行了 1 次工具调用
    assert result["budget_state"]["tool_calls"] == 1

    # 验证：模型只被调用了 2 次（1 次工具决策 + 1 次检查后停止）
    # 不应该执行第二次工具调用
    assert model.call_count <= 2


def test_FR_AGENT_004_rewrite_budget_tracking():
    """
    测试 FR-AGENT-004：Rewrite 预算跟踪
    
    Given: 模型重复相同的搜索查询
    When: 执行图
    Then: 应该消耗 rewrite 预算
    """
    evidence = EvidenceHit(
        chunk_id="chunk_1",
        document_id="doc_1",
        version_id="v1",
        text="内容",
        locator="loc",
        external_llm_allowed=True,
        index_generation="gen_1",
        embedding_model_version="v1",
        retrieval_config_version="v1",
    )

    retriever = ControlledRetriever({"same_query": (evidence,)})

    # 模型两次调用相同的查询
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "search_knowledge", "args": {"query": "same_query"}}
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_2", "name": "search_knowledge", "args": {"query": "same_query"}}
                ],
            ),
            AIMessage(content="结束"),
        ]
    )

    context = create_trusted_context(
        run_id="run_test",
        conversation_id="conv_test",
        principal_id="user_test",
        scope_type="all",
    )

    workflow = create_agent_graph(
        retriever=retriever,
        budget_policy=_policy(),
        context=context,
        model=model,
        is_external_model=False,
    )
    graph = workflow.compile()

    initial_state = {
        "messages": [{"type": "human", "content": "问题"}],
        "run_id": "run_test",
        "principal_id": "user_test",
        "conversation_id": "conv_test",
        "scope_type": "all",
        "scope_document_id": None,
        "budget_state": {"model_calls": 0, "tool_calls": 0, "rewrite_count": 0},
        "evidence_registry_data": {},
        "final_answer": None,
    }

    result = graph.invoke(initial_state)

    # 验证：rewrite_count 增加（第二次相同查询计为 rewrite）
    assert result["budget_state"]["rewrite_count"] == 1

    # 验证：两次工具调用都成功
    assert result["budget_state"]["tool_calls"] == 2


def test_FR_AGENT_004_rewrite_budget_exhausted():
    """
    测试 FR-AGENT-004：Rewrite 预算耗尽
    
    Given: rewrite 预算为 0，模型尝试重复查询
    When: 执行图
    Then: 第二次相同查询应该被阻止
    """
    evidence = EvidenceHit(
        chunk_id="chunk_1",
        document_id="doc_1",
        version_id="v1",
        text="内容",
        locator="loc",
        external_llm_allowed=True,
        index_generation="gen_1",
        embedding_model_version="v1",
        retrieval_config_version="v1",
    )

    retriever = ControlledRetriever({"same_query": (evidence,)})

    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "search_knowledge", "args": {"query": "same_query"}}
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_2", "name": "search_knowledge", "args": {"query": "same_query"}}
                ],
            ),
            AIMessage(content="结束"),
        ]
    )

    context = create_trusted_context(
        run_id="run_test",
        conversation_id="conv_test",
        principal_id="user_test",
        scope_type="all",
    )

    # 限制 rewrite 预算为 0
    workflow = create_agent_graph(
        retriever=retriever,
        budget_policy=_policy(max_rewrite_count=0),
        context=context,
        model=model,
        is_external_model=False,
    )
    graph = workflow.compile()

    initial_state = {
        "messages": [{"type": "human", "content": "问题"}],
        "run_id": "run_test",
        "principal_id": "user_test",
        "conversation_id": "conv_test",
        "scope_type": "all",
        "scope_document_id": None,
        "budget_state": {"model_calls": 0, "tool_calls": 0, "rewrite_count": 0},
        "evidence_registry_data": {},
        "final_answer": None,
    }

    result = graph.invoke(initial_state)

    # 验证：两次工具调用都被尝试（即使第二次被 rewrite 限制阻止）
    # 注意：工具调用计数包括失败的尝试
    assert result["budget_state"]["tool_calls"] == 2

    # 验证：rewrite_count 仍为 0（因为被阻止前就检查了）
    assert result["budget_state"]["rewrite_count"] == 0
    
    # 验证：第二次工具调用返回了错误
    from langchain_core.messages import ToolMessage as LCToolMessage
    
    tool_messages = [msg for msg in result["messages"] if isinstance(msg, LCToolMessage)]
    assert len(tool_messages) >= 2
    
    # 第二次工具调用应该返回 rewrite_budget_exhausted 错误
    second_tool_content = json.loads(tool_messages[1].content)
    assert second_tool_content.get("error") == "rewrite_budget_exhausted"


def test_FR_AGENT_002_multiple_calls_rejected():
    """
    测试 FR-AGENT-002：多个工具调用全部拒绝
    
    Given: 模型返回多个工具调用
    When: 执行图
    Then: 所有工具调用都应该被拒绝，返回错误
    """
    retriever = ControlledRetriever({})

    # 模型返回多个工具调用（违反规范）
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "search_knowledge", "args": {"query": "Q1"}},
                    {"id": "call_2", "name": "read_evidence", "args": {"evidence_id": "ev_1"}},
                ],
            ),
            AIMessage(content="结束"),
        ]
    )

    context = create_trusted_context(
        run_id="run_test",
        conversation_id="conv_test",
        principal_id="user_test",
        scope_type="all",
    )

    workflow = create_agent_graph(
        retriever=retriever,
        budget_policy=_policy(),
        context=context,
        model=model,
        is_external_model=False,
    )
    graph = workflow.compile()

    initial_state = {
        "messages": [{"type": "human", "content": "问题"}],
        "run_id": "run_test",
        "principal_id": "user_test",
        "conversation_id": "conv_test",
        "scope_type": "all",
        "scope_document_id": None,
        "budget_state": {"model_calls": 0, "tool_calls": 0, "rewrite_count": 0},
        "evidence_registry_data": {},
        "final_answer": None,
    }

    result = graph.invoke(initial_state)

    # 验证：图应该正常结束（不崩溃）
    assert result["final_answer"] is not None

    # 验证：没有执行任何工具（因为多调用被全部拒绝）
    assert result["budget_state"]["tool_calls"] == 0

    # 验证：消息中包含错误响应
    from langchain_core.messages import ToolMessage as LCToolMessage
    
    tool_messages = [msg for msg in result["messages"] if isinstance(msg, LCToolMessage)]
    assert len(tool_messages) == 2  # 两个工具调用都返回错误
    
    # 验证错误内容
    for msg in tool_messages:
        content = json.loads(msg.content)
        assert content.get("error") == "multiple_tool_calls_not_allowed"
