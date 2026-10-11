"""
Agent StateGraph 实现

实现 FR-AGENT-001：真实 ReAct Agent
- 观察驱动决策循环
- 条件路由（工具/finalize）
- 预算门禁集成
- 工具执行与状态管理
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from pivot.qa.agent_budget import BudgetGuard, BudgetPolicy, BudgetState
from pivot.qa.agent_tools import EvidenceRegistry, ToolExecutor
from pivot.qa.errors import AgentToolError, UnknownToolError
from pivot.qa.ports import Retriever

# ====================
# Agent State
# ====================


class AgentState(TypedDict):
    """
    Agent 状态

    包含消息历史、上下文信息和预算状态
    """

    messages: Annotated[list[dict[str, Any]], add_messages]
    run_id: str
    principal_id: str
    scope_type: str
    scope_document_id: str | None
    budget_state: dict[str, Any]  # BudgetState 序列化
    evidence_registry_data: dict[str, Any]  # EvidenceRegistry 序列化
    final_answer: dict[str, Any] | None


# ====================
# Agent 图节点
# ====================


class AgentNodes:
    """Agent 图节点实现"""

    def __init__(
        self,
        retriever: Retriever,
        budget_policy: BudgetPolicy,
    ) -> None:
        self.retriever = retriever
        self.budget_policy = budget_policy

    def decide(self, state: AgentState) -> AgentState:
        """
        决策节点：调用模型生成下一步行动

        Returns:
            更新后的状态（包含新的 AIMessage）
        """
        # 恢复预算状态
        budget_state = BudgetState(**state["budget_state"])
        budget_guard = BudgetGuard(self.budget_policy, budget_state)

        # 预算检查
        budget_guard.before_model_call()

        # TODO: 调用真实模型
        # 当前使用占位符响应
        ai_message = {
            "type": "ai",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_placeholder",
                    "name": "search_knowledge",
                    "args": {"query": "考勤规定"},
                }
            ],
        }

        # 更新预算
        budget_guard.after_model_call()

        # 更新状态
        return {
            **state,
            "messages": [ai_message],
            "budget_state": {
                "model_calls": budget_state.model_calls,
                "tool_calls": budget_state.tool_calls,
                "rewrite_count": budget_state.rewrite_count,
                "elapsed_seconds": budget_state.elapsed_seconds,
            },
        }

    def execute_tools(self, state: AgentState) -> AgentState:
        """
        工具执行节点：执行工具调用并返回 ToolMessage

        Returns:
            更新后的状态（包含 ToolMessage）
        """
        # 恢复预算和证据注册表
        budget_state = BudgetState(**state["budget_state"])
        budget_guard = BudgetGuard(self.budget_policy, budget_state)

        evidence_registry = EvidenceRegistry()
        # TODO: 恢复 evidence_registry 状态

        # 获取最后一条 AI 消息
        last_message = state["messages"][-1]
        if last_message["type"] != "ai":
            raise ValueError("Last message must be AI message with tool calls")

        tool_calls = last_message.get("tool_calls", [])
        if not tool_calls:
            raise ValueError("No tool calls found")

        # 预算检查
        budget_guard.before_tool_calls(tool_calls)

        # 执行工具
        tool_executor = ToolExecutor(self.retriever)
        tool_messages = []

        for tool_call in tool_calls:
            try:
                result = tool_executor.execute(
                    tool_call,
                    run_id=state["run_id"],
                    principal_id=state["principal_id"],
                    scope_type=state["scope_type"],
                    scope_document_id=state["scope_document_id"],
                    evidence_registry=evidence_registry,
                )
                tool_messages.append(
                    {
                        "type": "tool",
                        "tool_call_id": result["tool_call_id"],
                        "content": result["content"],
                    }
                )
            except (AgentToolError, UnknownToolError) as e:
                # 工具错误也作为 ToolMessage 返回
                tool_messages.append(
                    {
                        "type": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "content": {"error": str(e)},
                    }
                )

        # 更新预算
        budget_guard.after_tool_calls(tool_calls)

        # 更新状态
        return {
            **state,
            "messages": tool_messages,
            "budget_state": {
                "model_calls": budget_state.model_calls,
                "tool_calls": budget_state.tool_calls,
                "rewrite_count": budget_state.rewrite_count,
                "elapsed_seconds": budget_state.elapsed_seconds,
            },
            "evidence_registry_data": {},  # TODO: 序列化 evidence_registry
        }

    def finalize(self, state: AgentState) -> AgentState:
        """
        完成节点：生成最终答案

        Returns:
            更新后的状态（包含 final_answer）
        """
        # TODO: 调用 Finalizer 生成结构化答案
        final_answer = {
            "answer": "基于证据生成的答案",
            "claims": [],
            "status": "completed",
        }

        return {
            **state,
            "final_answer": final_answer,
        }


# ====================
# 条件路由
# ====================


def should_continue(state: AgentState) -> Literal["tools", "finalize", "end"]:
    """
    条件路由：决定下一步是调用工具、完成还是结束

    Returns:
        "tools": 继续调用工具
        "finalize": 生成最终答案
        "end": 结束（预算耗尽或其他终止条件）
    """
    # 检查预算是否耗尽
    budget_state = BudgetState(**state["budget_state"])
    budget_policy = BudgetPolicy(
        max_model_calls=10,
        max_tool_calls=20,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )
    if budget_state.is_exhausted(budget_policy):
        return "end"

    # 检查最后一条消息
    if not state["messages"]:
        return "end"

    last_message = state["messages"][-1]

    # 如果是 AI 消息且有工具调用，路由到工具执行
    if last_message["type"] == "ai" and last_message.get("tool_calls"):
        return "tools"

    # 如果是 AI 消息且没有工具调用，路由到 finalize
    if last_message["type"] == "ai" and not last_message.get("tool_calls"):
        return "finalize"

    # 如果是 ToolMessage，继续循环（回到 decide）
    if last_message["type"] == "tool":
        return "tools"  # 这里会继续循环

    return "end"


# ====================
# Agent 图构建
# ====================


def create_agent_graph(
    retriever: Retriever,
    budget_policy: BudgetPolicy,
) -> StateGraph:
    """
    创建 Agent StateGraph

    Args:
        retriever: 检索器
        budget_policy: 预算策略

    Returns:
        配置好的 StateGraph
    """
    nodes = AgentNodes(retriever, budget_policy)

    # 创建图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("decide", nodes.decide)
    workflow.add_node("execute_tools", nodes.execute_tools)
    workflow.add_node("finalize", nodes.finalize)

    # 添加边
    workflow.add_edge(START, "decide")
    workflow.add_conditional_edges(
        "decide",
        should_continue,
        {
            "tools": "execute_tools",
            "finalize": "finalize",
            "end": END,
        },
    )
    workflow.add_edge("execute_tools", "decide")  # 工具执行后回到决策
    workflow.add_edge("finalize", END)

    return workflow


def run_agent(
    question: str,
    retriever: Retriever,
    budget_policy: BudgetPolicy,
    run_id: str,
    principal_id: str,
    scope_type: str = "shared",
    scope_document_id: str | None = None,
) -> dict[str, Any]:
    """
    运行 Agent

    Args:
        question: 用户问题
        retriever: 检索器
        budget_policy: 预算策略
        run_id: Run ID
        principal_id: 用户 ID
        scope_type: 检索范围类型
        scope_document_id: 可选文档范围

    Returns:
        最终结果
    """
    # 创建图
    workflow = create_agent_graph(retriever, budget_policy)
    graph = workflow.compile()

    # 初始化状态
    initial_state: AgentState = {
        "messages": [{"type": "human", "content": question}],
        "run_id": run_id,
        "principal_id": principal_id,
        "scope_type": scope_type,
        "scope_document_id": scope_document_id,
        "budget_state": {
            "model_calls": 0,
            "tool_calls": 0,
            "rewrite_count": 0,
            "elapsed_seconds": 0.0,
        },
        "evidence_registry_data": {},
        "final_answer": None,
    }

    # 执行图
    result = graph.invoke(initial_state)

    return result
