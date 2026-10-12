"""
Agent StateGraph 实现

实现 FR-AGENT-001：真实 ReAct Agent
- 观察驱动决策循环
- 条件路由（工具/finalize）
- 预算门禁集成
- 工具执行与状态管理
"""

from __future__ import annotations

import json
import threading
from typing import Annotated, Any, Literal, NotRequired

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from pivot.qa.agent_budget import BudgetExhaustedError, BudgetGuard, BudgetPolicy, BudgetState
from pivot.qa.agent_context import ContextGuard, OutboundGuard, RunContext
from pivot.qa.agent_finalizer import StructuredFinalizer
from pivot.qa.agent_tools import EvidenceRegistry, ToolExecutor
from pivot.qa.errors import AgentSecurityError, AgentToolError, UnknownToolError
from pivot.qa.ports import DraftWriter, Retriever, Verifier

# ====================
# Agent State
# ====================


class AgentState(TypedDict):
    """
    Agent 状态

    包含消息历史、上下文信息和预算状态
    """

    messages: Annotated[list[Any], add_messages]
    run_id: str
    principal_id: str
    scope_type: str
    scope_document_id: str | None
    conversation_id: str  # 用于重建 RunContext
    budget_state: dict[str, Any]  # BudgetState 序列化
    evidence_registry_data: dict[str, Any]  # EvidenceRegistry 序列化
    final_answer: dict[str, Any] | None
    clarification: NotRequired[dict[str, Any] | None]


# ====================
# Agent 图节点
# ====================


class AgentNodes:
    """Agent 图节点实现"""

    def __init__(
        self,
        retriever: Retriever,
        budget_policy: BudgetPolicy,
        context: RunContext,
        model: Any | None = None,
        finalizer: StructuredFinalizer | None = None,
        is_external_model: bool = True,
    ) -> None:
        self.retriever = retriever
        self.budget_policy = budget_policy
        self.context = context
        self.model = model
        self.finalizer = finalizer
        self.is_external_model = is_external_model
        self.context_guard = ContextGuard(context)
        self.outbound_guard = OutboundGuard(context)
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        """请求在下一个调用边界停止，不覆盖已经发布的终态。"""
        self._cancelled.set()

    def _cancelled_state(self, state: AgentState) -> AgentState | None:
        if not self._cancelled.is_set():
            return None
        return {
            "messages": [],
            "run_id": state["run_id"],
            "principal_id": state["principal_id"],
            "scope_type": state["scope_type"],
            "scope_document_id": state["scope_document_id"],
            "conversation_id": state["conversation_id"],
            "budget_state": state["budget_state"],
            "evidence_registry_data": state["evidence_registry_data"],
            "final_answer": {
                "answer": "",
                "claims": [],
                "status": "cancelled",
            },
        }

    def decide(self, state: AgentState) -> AgentState:
        """
        决策节点：调用模型生成下一步行动

        Returns:
            更新后的状态（包含新的 AIMessage）
        """
        stopped = self._cancelled_state(state)
        if stopped is not None:
            return stopped

        # 恢复预算状态和证据注册表
        budget_state = BudgetState(**state["budget_state"])
        budget_guard = BudgetGuard(self.budget_policy, budget_state)

        evidence_registry = EvidenceRegistry.restore(
            state["evidence_registry_data"],
            run_id=state["run_id"],
            principal_id=state["principal_id"],
        )

        # 预算耗尽时停止收费调用，不再进入工具循环。
        try:
            budget_guard.before_model_call()
        except BudgetExhaustedError:
            # 不回传已有 messages，避免 add_messages 把历史再追加一遍。
            return {
                "messages": [],
                "run_id": state["run_id"],
                "principal_id": state["principal_id"],
                "scope_type": state["scope_type"],
                "scope_document_id": state["scope_document_id"],
                "conversation_id": state["conversation_id"],
                "budget_state": state["budget_state"],
                "evidence_registry_data": state["evidence_registry_data"],
                "final_answer": {
                    "answer": "预算已耗尽，已停止继续调用。",
                    "claims": [],
                    "status": "budget_exhausted",
                },
            }

        # 外发门禁检查：在调用模型前检查消息中是否包含受限内容
        formatted_messages = [_message_dict(msg) for msg in state["messages"]]
        try:
            self.outbound_guard.check_before_model_call(
                messages=formatted_messages,
                evidence_registry=evidence_registry,
                is_external_model=self.is_external_model,
            )
        except AgentSecurityError:
            # 受限内容不能发送给外部模型，拒绝执行
            return {
                "messages": [],
                "run_id": state["run_id"],
                "principal_id": state["principal_id"],
                "scope_type": state["scope_type"],
                "scope_document_id": state["scope_document_id"],
                "conversation_id": state["conversation_id"],
                "budget_state": state["budget_state"],
                "evidence_registry_data": state["evidence_registry_data"],
                "final_answer": {
                    "answer": "无法继续：消息包含受限内容，不能发送给外部模型。",
                    "claims": [],
                    "status": "security_violation",
                },
            }

        # 调用真实模型（如果有）
        if self.model is not None:
            from pivot.qa.agent_model import get_tool_schemas

            response = self.model.decide(
                messages=formatted_messages,
                tools=get_tool_schemas(),
            )

            # 转换为 dict 格式
            ai_message: dict[str, Any] = {
                "type": "ai",
                "content": response.content or "",
            }

            # 处理 tool_calls
            if response.tool_calls:
                ai_message["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "name": tc["name"],
                        "args": tc["args"],
                    }
                    for tc in response.tool_calls
                ]
        else:
            # 使用占位符响应（用于测试）
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

        # 只有供应商返回 usage_metadata 时才结算 token。脚本模型不计未知用量。
        usage = getattr(response, "usage_metadata", None) if self.model is not None else None
        if isinstance(usage, dict):
            try:
                budget_guard.settle_reported_usage(usage)
            except BudgetExhaustedError:
                pass
        else:
            budget_guard.after_model_call()

        stopped = self._cancelled_state(state)
        if stopped is not None:
            return stopped

        # 更新状态
        return {
            **state,
            "messages": [ai_message],
            "budget_state": budget_guard.state_snapshot(),
        }

    def execute_tools(self, state: AgentState) -> AgentState:
        """
        工具执行节点：执行工具调用并返回 ToolMessage

        Returns:
            更新后的状态（包含 ToolMessage）
        """
        stopped = self._cancelled_state(state)
        if stopped is not None:
            return stopped

        # 恢复预算和证据注册表
        budget_state = BudgetState(**state["budget_state"])
        budget_guard = BudgetGuard(self.budget_policy, budget_state)

        evidence_registry = EvidenceRegistry.restore(
            state["evidence_registry_data"],
            run_id=state["run_id"],
            principal_id=state["principal_id"],
        )

        # add_messages converts dictionaries to native LangChain messages.
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage):
            tool_calls: list[dict[str, Any]] = [dict(call) for call in last_message.tool_calls]
        elif isinstance(last_message, dict) and last_message.get("type") == "ai":
            tool_calls = last_message.get("tool_calls", [])
        else:
            raise ValueError("Last message must be AI message with tool calls")
        if not tool_calls:
            raise ValueError("No tool calls found")

        # FR-AGENT-002: 单工具调用限制
        if len(tool_calls) > 1:
            # 多个工具调用违反规范，全部拒绝
            tool_messages = [
                ToolMessage(
                    tool_call_id=tc["id"],
                    content=json.dumps({"error": "multiple_tool_calls_not_allowed"}),
                )
                for tc in tool_calls
            ]
            return {
                **state,
                "messages": tool_messages,
                "budget_state": budget_guard.state_snapshot(),
                "evidence_registry_data": evidence_registry.snapshot(),
            }

        # 预算检查
        budget_guard.before_tool_calls(tool_calls)

        # 检测 rewrite：提取历史中所有 search_knowledge 的查询（排除当前消息）
        previous_queries = set()
        for i, msg in enumerate(state["messages"]):
            # 跳过最后一条消息（当前正在执行的）
            if i == len(state["messages"]) - 1:
                break

            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc["name"] == "search_knowledge":
                        previous_queries.add(tc["args"].get("query", ""))
            elif isinstance(msg, dict) and msg.get("type") == "ai":
                for tc in msg.get("tool_calls", []):
                    if tc["name"] == "search_knowledge":
                        previous_queries.add(tc["args"].get("query", ""))

        # 执行工具
        tool_executor = ToolExecutor(self.retriever)
        tool_messages = []

        for tool_call in tool_calls:
            try:
                # 上下文验证：检查工具参数是否包含禁止字段
                self.context_guard.validate_tool_execution(
                    tool_name=tool_call["name"],
                    tool_args=tool_call["args"],
                )

                # FR-AGENT-004: Rewrite 预算检查
                is_rewrite = False
                if tool_call["name"] == "search_knowledge":
                    query = tool_call["args"].get("query", "")
                    if query in previous_queries:
                        # 重复查询，消耗 rewrite 预算
                        is_rewrite = True
                        try:
                            budget_guard.before_rewrite()
                        except BudgetExhaustedError:
                            # Rewrite 预算耗尽
                            tool_messages.append(
                                ToolMessage(
                                    tool_call_id=tool_call["id"],
                                    content=json.dumps({"error": "rewrite_budget_exhausted"}),
                                )
                            )
                            continue

                result = tool_executor.execute(
                    tool_call,
                    run_id=state["run_id"],
                    principal_id=state["principal_id"],
                    scope_type=state["scope_type"],
                    scope_document_id=state["scope_document_id"],
                    evidence_registry=evidence_registry,
                )
                tool_messages.append(
                    ToolMessage(
                        tool_call_id=result["tool_call_id"],
                        content=json.dumps(result["content"], ensure_ascii=False),
                    )
                )

                # 如果是 rewrite，更新预算
                if is_rewrite:
                    budget_guard.after_rewrite()

            except AgentSecurityError:
                # 安全违规：工具参数包含禁止字段
                tool_messages.append(
                    ToolMessage(
                        tool_call_id=tool_call["id"],
                        content=json.dumps({"error": "security_violation"}),
                    )
                )
            except (AgentToolError, UnknownToolError):
                # Do not send raw backend errors or protected parameters to a model.
                tool_messages.append(
                    ToolMessage(
                        tool_call_id=tool_call["id"],
                        content=json.dumps({"error": "tool_execution_failed"}),
                    )
                )

        # 更新预算
        budget_guard.after_tool_calls(tool_calls)

        stopped = self._cancelled_state(state)
        if stopped is not None:
            return stopped

        # 更新状态
        return {
            **state,
            "messages": tool_messages,
            "budget_state": budget_guard.state_snapshot(),
            "evidence_registry_data": evidence_registry.snapshot(),
        }

    def finalize(self, state: AgentState) -> AgentState:
        """
        完成节点：生成最终答案

        Returns:
            更新后的状态（包含 final_answer）
        """
        if state.get("final_answer"):
            return state
        stopped = self._cancelled_state(state)
        if stopped is not None:
            return stopped

        evidences = EvidenceRegistry.restore(
            state["evidence_registry_data"],
            run_id=state["run_id"],
            principal_id=state["principal_id"],
        ).list_for_run(state["run_id"])
        question = _latest_human_content(state["messages"])
        if self.finalizer is None:
            final_answer = {
                "answer": "基于证据生成的答案",
                "claims": [],
                "status": "completed",
            }
        else:
            final_answer = self.finalizer.finalize(question, evidences)

        return {
            **state,
            "final_answer": final_answer,
        }


# ====================
# 条件路由
# ====================


def accept_clarification(state: AgentState) -> AgentState:
    """接受第一轮澄清。第二轮和已发布终态都拒绝。"""
    final_answer = state.get("final_answer") or {}
    if final_answer.get("status") in {"answered", "refused", "cancelled", "failed"}:
        return state
    budget = dict(state["budget_state"])
    if int(budget.get("clarification_count") or 0) >= 1:
        return {
            **state,
            "final_answer": {
                "answer": "",
                "claims": [],
                "status": "second_clarification_rejected",
            },
        }
    budget["clarification_count"] = 1
    return {
        **state,
        "budget_state": budget,
        "clarification": {"status": "waiting_for_user", "owner_id": state["principal_id"]},
        "final_answer": None,
    }


def resume_clarification(state: AgentState, reply: str, *, actor_id: str) -> AgentState:
    """只有原 owner 能恢复同一 Run，且不重置已消耗预算。"""
    pending = state.get("clarification") or {}
    if pending.get("status") != "waiting_for_user" or actor_id != pending.get("owner_id"):
        return {
            **state,
            "final_answer": {"answer": "", "claims": [], "status": "resume_forbidden"},
        }
    if not reply.strip():
        return {
            **state,
            "final_answer": {"answer": "", "claims": [], "status": "resume_forbidden"},
        }
    return {
        **state,
        "messages": [{"type": "human", "content": reply}],
        "clarification": {"status": "resuming", "owner_id": actor_id},
        "final_answer": None,
    }


def should_continue(
    state: AgentState,
    budget_policy: BudgetPolicy | None = None,
) -> Literal["tools", "finalize", "end"]:
    """
    条件路由：决定下一步是调用工具、完成还是结束

    Returns:
        "tools": 继续调用工具
        "finalize": 生成最终答案
        "end": 结束（预算耗尽或其他终止条件）
    """
    if (state.get("clarification") or {}).get("status") == "waiting_for_user":
        return "end"
    final_answer = state.get("final_answer") or {}
    if final_answer.get("status") in {
        "budget_exhausted",
        "cancelled",
        "second_clarification_rejected",
        "resume_forbidden",
    }:
        return "end"

    if not state["messages"]:
        return "end"

    # 模型次数在 decide 内拦截。这里只阻止超出工具额度的新工具派发。
    message_type, tool_calls = _message_route(state["messages"][-1])
    if budget_policy is not None and message_type == "ai" and tool_calls:
        budget_state = BudgetState(**state["budget_state"])
        if budget_state.tool_calls + len(tool_calls) > budget_policy.max_tool_calls:
            return "end"

    if message_type == "ai" and tool_calls:
        return "tools"
    if message_type == "ai":
        return "finalize"
    return "end"


def _message_route(message: Any) -> tuple[str, list[Any]]:
    if isinstance(message, AIMessage):
        return "ai", list(message.tool_calls)
    if isinstance(message, ToolMessage):
        return "tool", []
    if isinstance(message, dict):
        message_type = message.get("type") or message.get("role") or ""
        if message_type in {"ai", "assistant"}:
            return "ai", list(message.get("tool_calls") or [])
        if message_type in {"tool", "tool_call"}:
            return "tool", []
    return "", []


def _message_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, AIMessage):
        payload: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            payload["tool_calls"] = list(message.tool_calls)
        return payload
    if isinstance(message, ToolMessage):
        return {"role": "tool", "content": message.content, "tool_call_id": message.tool_call_id}
    if isinstance(message, dict):
        role = message.get("role") or message.get("type") or "user"
        if role == "human":
            role = "user"
        if role == "ai":
            role = "assistant"
        return {**message, "role": role, "content": message.get("content", "")}
    content = getattr(message, "content", "")
    return {"role": "user", "content": content}


def _latest_human_content(messages: list[Any]) -> str:
    for message in reversed(messages):
        payload = _message_dict(message)
        if payload["role"] == "user" and payload.get("content"):
            return str(payload["content"])
    return ""


# ====================
# Agent 图构建
# ====================


def create_agent_graph(
    retriever: Retriever,
    budget_policy: BudgetPolicy,
    context: RunContext,
    model: Any | None = None,
    *,
    draft_writer: DraftWriter | None = None,
    verifier: Verifier | None = None,
    finalizer: StructuredFinalizer | None = None,
    is_external_model: bool = True,
) -> StateGraph:
    """
    创建 Agent StateGraph

    Args:
        retriever: 检索器
        budget_policy: 预算策略
        context: 可信 Run 上下文
        model: 可选的模型实例（AgentModel），用于真实决策
        draft_writer: 可选答案草稿生成器
        verifier: 可选答案校验器
        finalizer: 可选结构化答案生成器；优先于 draft_writer
        is_external_model: 是否为外部模型（如 OpenAI）

    Returns:
        配置好的 StateGraph
    """
    if finalizer is None and draft_writer is not None:
        finalizer = StructuredFinalizer(draft_writer, verifier)
    nodes = AgentNodes(retriever, budget_policy, context, model, finalizer, is_external_model)

    # 创建图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("decide", nodes.decide)
    workflow.add_node("execute_tools", nodes.execute_tools)
    workflow.add_node("finalize", nodes.finalize)

    # 添加边
    workflow.add_edge(START, "decide")

    def route(state: AgentState) -> Literal["tools", "finalize", "end"]:
        return should_continue(state, budget_policy)

    workflow.add_conditional_edges(
        "decide",
        route,
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
    conversation_id: str,
    scope_type: str = "global",
    scope_document_id: str | None = None,
    *,
    model: Any | None = None,
    draft_writer: DraftWriter | None = None,
    verifier: Verifier | None = None,
    finalizer: StructuredFinalizer | None = None,
    is_external_model: bool = True,
) -> dict[str, Any]:
    """
    运行 Agent

    Args:
        question: 用户问题
        retriever: 检索器
        budget_policy: 预算策略
        run_id: Run ID
        principal_id: 用户 ID
        conversation_id: 会话 ID
        scope_type: 检索范围类型
        scope_document_id: 可选文档范围
        model: 可选模型实例
        draft_writer: 可选草稿生成器
        verifier: 可选校验器
        finalizer: 可选结构化答案生成器
        is_external_model: 是否为外部模型

    Returns:
        最终结果
    """
    # 创建可信上下文
    from pivot.qa.agent_context import create_trusted_context

    context = create_trusted_context(
        run_id=run_id,
        conversation_id=conversation_id,
        principal_id=principal_id,
        scope_type=scope_type,
        scope_document_id=scope_document_id,
    )

    # 创建图
    workflow = create_agent_graph(
        retriever,
        budget_policy,
        context,
        model,
        draft_writer=draft_writer,
        verifier=verifier,
        finalizer=finalizer,
        is_external_model=is_external_model,
    )
    graph = workflow.compile()

    # 初始化状态
    initial_state: AgentState = {
        "messages": [{"type": "human", "content": question}],
        "run_id": run_id,
        "principal_id": principal_id,
        "conversation_id": conversation_id,
        "scope_type": scope_type,
        "scope_document_id": scope_document_id,
        "budget_state": BudgetGuard(budget_policy, BudgetState()).state_snapshot(),
        "evidence_registry_data": {},
        "final_answer": None,
    }

    # 执行图
    result = graph.invoke(initial_state)

    return result
