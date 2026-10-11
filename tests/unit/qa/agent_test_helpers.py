"""
Agent StateGraph 测试辅助工具

用途：为 StateGraph 条件循环测试提供状态构造和断言工具。
状态：基础设施准备，等待 02-G StateGraph 实现。

设计原则：
- 提供标准的 State 构造函数
- 支持消息序列验证
- 提供条件路由断言辅助
"""

from __future__ import annotations

from typing import Any

# ====================
# State 构造函数
# ====================


def make_agent_state(
    messages: list[dict[str, Any]] | None = None,
    run_id: str = "run_test",
    principal_id: str = "user_test",
    scope_type: str = "shared",
    scope_document_id: str | None = None,
    budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    构造标准 Agent State。

    Args:
        messages: 消息历史
        run_id: Run ID
        principal_id: 用户 ID
        scope_type: 检索范围类型
        scope_document_id: 可选文档范围
        budget: 可选预算状态

    Returns:
        标准 State 字典
    """
    return {
        "messages": messages or [],
        "run_id": run_id,
        "principal_id": principal_id,
        "scope_type": scope_type,
        "scope_document_id": scope_document_id,
        "budget": budget or make_budget_state(),
    }


def make_budget_state(
    remaining: float = 100.0,
    model_calls: int = 0,
    tool_calls: int = 0,
    rewrite_count: int = 0,
) -> dict[str, Any]:
    """
    构造预算状态。

    Args:
        remaining: 剩余预算
        model_calls: 模型调用次数
        tool_calls: 工具调用次数
        rewrite_count: 查询改写次数

    Returns:
        预算状态字典
    """
    return {
        "remaining": remaining,
        "model_calls": model_calls,
        "tool_calls": tool_calls,
        "rewrite_count": rewrite_count,
    }


def make_human_message(content: str, message_id: str | None = None) -> dict[str, Any]:
    """
    构造 HumanMessage。

    Args:
        content: 用户消息内容
        message_id: 可选消息 ID

    Returns:
        HumanMessage 字典
    """
    msg = {"type": "human", "content": content}
    if message_id:
        msg["id"] = message_id
    return msg


def make_ai_message(
    content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    message_id: str | None = None,
) -> dict[str, Any]:
    """
    构造 AIMessage。

    Args:
        content: AI 响应内容
        tool_calls: 可选工具调用列表
        message_id: 可选消息 ID

    Returns:
        AIMessage 字典
    """
    msg: dict[str, Any] = {"type": "ai", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    if message_id:
        msg["id"] = message_id
    return msg


def make_tool_message_dict(
    tool_call_id: str, content: Any, message_id: str | None = None
) -> dict[str, Any]:
    """
    构造 ToolMessage（避免与 agent_fakes.py 中的函数冲突，添加 _dict 后缀）。

    Args:
        tool_call_id: 对应工具调用 ID
        content: 工具响应内容
        message_id: 可选消息 ID

    Returns:
        ToolMessage 字典
    """
    msg = {"type": "tool", "tool_call_id": tool_call_id, "content": content}
    if message_id:
        msg["id"] = message_id
    return msg


# ====================
# 消息序列断言
# ====================


def assert_message_types(messages: list[dict[str, Any]], expected_types: list[str]) -> None:
    """
    断言消息类型序列。

    Args:
        messages: 消息列表
        expected_types: 期望的类型序列 (如 ["human", "ai", "tool"])

    Raises:
        AssertionError: 类型不匹配
    """
    actual_types = [msg.get("type") for msg in messages]
    assert actual_types == expected_types, (
        f"消息类型不匹配:\n"
        f"  期望: {expected_types}\n"
        f"  实际: {actual_types}"
    )


def assert_has_tool_call(message: dict[str, Any], tool_name: str | None = None) -> None:
    """
    断言消息包含工具调用。

    Args:
        message: AI 消息
        tool_name: 可选的工具名称验证

    Raises:
        AssertionError: 没有工具调用或工具名不匹配
    """
    assert message.get("type") == "ai", f"消息类型必须是 'ai'，实际: {message.get('type')}"

    tool_calls = message.get("tool_calls", [])
    assert len(tool_calls) > 0, "消息必须包含至少一个工具调用"

    if tool_name:
        actual_name = tool_calls[0].get("name")
        assert actual_name == tool_name, (
            f"工具名称不匹配:\n" f"  期望: {tool_name}\n" f"  实际: {actual_name}"
        )


def assert_tool_call_id_matches(
    tool_message: dict[str, Any], ai_message: dict[str, Any]
) -> None:
    """
    断言 ToolMessage 的 tool_call_id 匹配 AIMessage 中的 tool_call.id。

    Args:
        tool_message: ToolMessage
        ai_message: 对应的 AIMessage

    Raises:
        AssertionError: ID 不匹配
    """
    assert tool_message.get("type") == "tool", (
        f"消息类型必须是 'tool'，实际: {tool_message.get('type')}"
    )
    assert ai_message.get("type") == "ai", (
        f"消息类型必须是 'ai'，实际: {ai_message.get('type')}"
    )

    tool_call_id = tool_message.get("tool_call_id")
    tool_calls = ai_message.get("tool_calls", [])

    assert len(tool_calls) > 0, "AIMessage 必须包含工具调用"

    expected_id = tool_calls[0].get("id")
    assert tool_call_id == expected_id, (
        f"tool_call_id 不匹配:\n" f"  期望: {expected_id}\n" f"  实际: {tool_call_id}"
    )


def get_last_message_of_type(
    messages: list[dict[str, Any]], msg_type: str
) -> dict[str, Any] | None:
    """
    获取最后一条指定类型的消息。

    Args:
        messages: 消息列表
        msg_type: 消息类型 (human/ai/tool)

    Returns:
        最后一条匹配的消息，如果没有返回 None
    """
    for msg in reversed(messages):
        if msg.get("type") == msg_type:
            return msg
    return None


def count_messages_by_type(messages: list[dict[str, Any]]) -> dict[str, int]:
    """
    统计各类型消息数量。

    Args:
        messages: 消息列表

    Returns:
        类型计数字典
    """
    counts: dict[str, int] = {}
    for msg in messages:
        msg_type = msg.get("type", "unknown")
        counts[msg_type] = counts.get(msg_type, 0) + 1
    return counts


# ====================
# 条件路由断言
# ====================


def assert_should_route_to_tools(state: dict[str, Any]) -> None:
    """
    断言 State 应该路由到工具执行。

    检查最后一条 AI 消息是否包含工具调用。

    Args:
        state: Agent State

    Raises:
        AssertionError: 不应该路由到工具
    """
    messages = state.get("messages", [])
    last_ai = get_last_message_of_type(messages, "ai")

    assert last_ai is not None, "没有找到 AI 消息"
    assert len(last_ai.get("tool_calls", [])) > 0, "AI 消息应该包含工具调用"


def assert_should_route_to_finalize(state: dict[str, Any]) -> None:
    """
    断言 State 应该路由到 finalize。

    检查是否存在 finalize 控制意图或没有工具调用。

    Args:
        state: Agent State

    Raises:
        AssertionError: 不应该路由到 finalize
    """
    control_intent = state.get("control_intent")
    if control_intent:
        assert control_intent == "finalize", (
            f"控制意图应该是 'finalize'，实际: {control_intent}"
        )
    else:
        # 如果没有显式控制意图，检查最后一条 AI 消息是否没有工具调用
        messages = state.get("messages", [])
        last_ai = get_last_message_of_type(messages, "ai")
        if last_ai:
            tool_calls = last_ai.get("tool_calls", [])
            assert len(tool_calls) == 0, (
                "AI 消息不应该包含工具调用（应该 finalize）"
            )


def assert_budget_decreased(
    state_before: dict[str, Any], state_after: dict[str, Any]
) -> None:
    """
    断言预算减少。

    Args:
        state_before: 操作前的 State
        state_after: 操作后的 State

    Raises:
        AssertionError: 预算没有减少
    """
    budget_before = state_before.get("budget", {})
    budget_after = state_after.get("budget", {})

    remaining_before = budget_before.get("remaining", 0)
    remaining_after = budget_after.get("remaining", 0)

    assert remaining_after < remaining_before, (
        f"预算应该减少:\n"
        f"  操作前: {remaining_before}\n"
        f"  操作后: {remaining_after}"
    )


def assert_budget_exhausted(state: dict[str, Any]) -> None:
    """
    断言预算耗尽。

    Args:
        state: Agent State

    Raises:
        AssertionError: 预算未耗尽
    """
    budget = state.get("budget", {})
    remaining = budget.get("remaining", float("inf"))

    assert remaining <= 0, f"预算应该耗尽，实际剩余: {remaining}"
