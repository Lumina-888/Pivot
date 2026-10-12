"""
Agent 阶段投影

实现 FR-AGENT-008：将内部 Agent 节点映射到公开 Run 状态
- 内部 agent/tools 循环保持 retrieving
- verifying → agent 补证映射回 retrieving
- 只发送白名单阶段，不透传内部节点名
"""

from __future__ import annotations

# 内部节点到公开阶段的映射
INTERNAL_TO_PUBLIC_STAGE = {
    # Agent 决策节点
    "agent": "retrieving",
    "decide": "retrieving",
    # 工具相关节点
    "tool_guard": "retrieving",
    "tools": "retrieving",
    "execute_tools": "retrieving",
    "observation_guard": "retrieving",
    # 搜索和证据
    "search_knowledge": "retrieving",
    "read_evidence": "retrieving",
    # 补证循环
    "repair_feedback": "retrieving",
    # 输入和上下文
    "input_guard": "planning",
    "load_context": "planning",
    # 澄清
    "clarify": "waiting_for_user",
    "authorized_resume": "resuming",
    # 答案生成
    "build_evidence": "drafting",
    "structured_finalize": "verifying",
    "verify": "verifying",
    # 终态
    "persist_result": "answered",
    "refuse_or_uncertain": "refused",
}

# 允许公开的阶段名称（来自 SPEC §3.2）
PUBLIC_STAGES = frozenset(
    {
        # SPEC §3.2 Run 状态
        "received",
        "planning",
        "retrieving",
        "retrying",
        "drafting",
        "verifying",
        "waiting_for_user",
        "resuming",
        # 终态
        "answered",
        "uncertain",
        "refused",
        "failed",
        "cancelled",
        # 兼容旧线性阶段（历史回归）
        "normalize",
        "classify",
        "retrieve",
        "rerank",
        "build_evidence",
        "draft_answer",
        "verify_claims",
        "finalize",
        "refuse",
    }
)


def project_stage(
    internal_node: str, *, is_terminal: bool = False, terminal_state: str | None = None
) -> str:
    """
    将内部节点名投影到公开阶段

    Args:
        internal_node: 内部节点名称（如 'agent', 'tools', 'verify'）
        is_terminal: 是否为终态节点
        terminal_state: 如果是终态，具体的终态类型

    Returns:
        公开阶段名称

    Raises:
        ValueError: 节点名未知、终态非法，或映射不在公开白名单
    """
    if is_terminal and terminal_state:
        if terminal_state not in PUBLIC_STAGES:
            raise ValueError("terminal stage is not public")
        return terminal_state

    public_stage = INTERNAL_TO_PUBLIC_STAGE.get(internal_node)
    if public_stage is None or public_stage not in PUBLIC_STAGES:
        raise ValueError("internal stage is not public")
    return public_stage


def is_public_stage_allowed(stage: str) -> bool:
    """
    检查阶段名是否允许公开

    Args:
        stage: 阶段名称

    Returns:
        True 如果允许公开，False 否则
    """
    return stage in PUBLIC_STAGES


def should_emit_draft_content(stage: str, verified: bool) -> bool:
    """
    判断是否应该发送草稿内容（token/citation）

    Args:
        stage: 当前阶段
        verified: 是否已通过校验

    Returns:
        True 如果应该发送内容，False 如果只发送阶段
    """
    return verified and stage == "answered"
