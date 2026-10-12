"""
Agent 可信上下文与外发门禁

实现 FR-AGENT-003：可信上下文与外发门禁
- 服务端注入可信 RunContext
- 每次调用前后检查外发资格
- 防止模型伪造身份或扩大 scope
- 历史与 Observation 的外发控制
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pivot.qa.agent_tools import EvidenceRegistry
from pivot.qa.errors import AgentSecurityError


@dataclass(frozen=True)
class RunContext:
    """
    可信 Run 上下文

    服务端注入，不可由模型或客户端伪造的权限依据。
    包含执行所需的身份、权限、范围和策略。
    """

    run_id: str
    conversation_id: str
    principal_id: str
    scope_type: str  # "all", "document", etc.
    scope_document_id: str | None

    # 执行策略（未来扩展）
    allow_external_llm: bool = True  # 是否允许外部 LLM（内部部署时为 False）

    def __post_init__(self):
        """验证上下文完整性"""
        if not self.run_id:
            raise ValueError("run_id is required")
        if not self.conversation_id:
            raise ValueError("conversation_id is required")
        if not self.principal_id:
            raise ValueError("principal_id is required")
        if not self.scope_type:
            raise ValueError("scope_type is required")
        if self.scope_type == "document" and not self.scope_document_id:
            raise ValueError("scope_document_id required when scope_type is 'document'")


class OutboundGuard:
    """
    外发门禁

    在每次模型调用前检查：
    - 是否有受限文档（external_llm_allowed=False）
    - 受限内容是否会被发送给外部模型
    - 确保历史、Observation 和衍生数据符合外发策略
    """

    def __init__(self, context: RunContext) -> None:
        self.context = context

    def check_before_model_call(
        self,
        *,
        messages: list[dict[str, Any]],
        evidence_registry: EvidenceRegistry,
        is_external_model: bool,
    ) -> None:
        """
        模型调用前的外发门禁检查

        Args:
            messages: 将要发送的消息历史
            evidence_registry: 证据注册表
            is_external_model: 是否为外部模型（如 OpenAI）

        Raises:
            AgentSecurityError: 检测到外发违规
        """
        # 如果不是外部模型，允许所有数据
        if not is_external_model:
            return

        # 检查证据注册表中是否有受限文档
        restricted_evidence = self._find_restricted_evidence(evidence_registry)

        if not restricted_evidence:
            return

        # 检查消息中是否包含受限内容
        self._check_messages_for_restricted_content(
            messages,
            restricted_evidence,
            evidence_registry,
        )

    def _find_restricted_evidence(
        self,
        evidence_registry: EvidenceRegistry,
    ) -> set[str]:
        """
        查找所有受限证据的 evidence_id

        Returns:
            受限证据 ID 集合
        """
        restricted = set()
        for entry in evidence_registry.list_for_run(self.context.run_id):
            if not entry.get("external_llm_allowed", True):
                restricted.add(entry["evidence_id"])
        return restricted

    def _check_messages_for_restricted_content(
        self,
        messages: list[dict[str, Any]],
        restricted_evidence: set[str],
        evidence_registry: EvidenceRegistry,
    ) -> None:
        """
        检查消息中是否包含受限内容

        Args:
            messages: 消息列表
            restricted_evidence: 受限证据 ID 集合
            evidence_registry: 证据注册表

        Raises:
            AgentSecurityError: 发现受限内容将被发送给外部模型
        """
        for message in messages:
            msg_type = message.get("type")

            # 检查 ToolMessage 中的证据引用
            if msg_type == "tool":
                self._check_tool_message(message, restricted_evidence, evidence_registry)

            # 检查 AI/Human 消息中的文本内容
            elif msg_type in ("ai", "human"):
                self._check_text_message(message, restricted_evidence, evidence_registry)

    def _check_tool_message(
        self,
        message: dict[str, Any],
        restricted_evidence: set[str],
        evidence_registry: EvidenceRegistry,
    ) -> None:
        """检查 ToolMessage 是否包含受限证据"""
        content = message.get("content", "")

        # 如果 content 是字符串形式的 JSON，尝试解析
        if isinstance(content, str):
            try:
                import json

                content_data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                # 无法解析，检查纯文本
                self._check_text_for_restricted_content(
                    content,
                    restricted_evidence,
                    evidence_registry,
                )
                return
        else:
            content_data = content

        # 检查 evidence_ids 字段
        if isinstance(content_data, dict):
            evidence_ids = content_data.get("evidence_ids", [])
            for evidence_id in evidence_ids:
                if evidence_id in restricted_evidence:
                    raise AgentSecurityError(
                        f"Cannot send restricted evidence {evidence_id} to external model"
                    )

    def _check_text_message(
        self,
        message: dict[str, Any],
        restricted_evidence: set[str],
        evidence_registry: EvidenceRegistry,
    ) -> None:
        """检查文本消息是否包含受限内容"""
        content = message.get("content", "")
        if isinstance(content, str):
            self._check_text_for_restricted_content(
                content,
                restricted_evidence,
                evidence_registry,
            )

    def _check_text_for_restricted_content(
        self,
        text: str,
        restricted_evidence: set[str],
        evidence_registry: EvidenceRegistry,
    ) -> None:
        """
        检查文本中是否泄露受限证据内容

        策略：检查受限证据的关键片段是否出现在文本中
        """
        for evidence_id in restricted_evidence:
            entry = evidence_registry.get(evidence_id, run_id=self.context.run_id)
            if entry is None:
                continue

            evidence_text = entry.get("text", "")
            if not evidence_text:
                continue

            # 检查是否有显著的文本片段泄露
            # 使用简单策略：检查受限证据文本的前N个字符是否出现在消息中
            # 为了检测泄露，我们检查证据文本的多个片段
            if len(evidence_text) > 20:
                # 检查前50个字符
                snippet = evidence_text[:50]
                if snippet in text:
                    raise AgentSecurityError(
                        f"Message contains content from restricted evidence {evidence_id}"
                    )

                # 也检查中间部分（避免只改开头绕过检测）
                if len(evidence_text) > 100:
                    mid_snippet = evidence_text[25:75]
                    if len(mid_snippet) > 20 and mid_snippet in text:
                        raise AgentSecurityError(
                            f"Message contains content from restricted evidence {evidence_id}"
                        )


class ContextGuard:
    """
    上下文防护

    防止模型或客户端伪造身份、扩大 scope 或访问未授权资源
    """

    def __init__(self, context: RunContext) -> None:
        self.context = context

    def validate_tool_execution(
        self,
        *,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> None:
        """
        工具执行前的上下文验证

        确保工具调用不会扩大权限或访问越界资源

        Args:
            tool_name: 工具名称
            tool_args: 工具参数

        Raises:
            AgentSecurityError: 检测到权限扩大或越界访问
        """
        # 检查是否尝试注入 principal_id 或 scope
        forbidden_params = {
            "principal_id",
            "scope_type",
            "scope_document_id",
            "run_id",
            "conversation_id",
        }

        for param in forbidden_params:
            if param in tool_args:
                raise AgentSecurityError(f"Tool {tool_name} cannot specify {param} parameter")

    def validate_evidence_access(
        self,
        *,
        evidence_id: str,
        evidence_registry: EvidenceRegistry,
    ) -> None:
        """
        证据访问前的验证

        确保只能访问本 Run 已注册的合法证据

        Args:
            evidence_id: 证据 ID
            evidence_registry: 证据注册表

        Raises:
            AgentSecurityError: 跨 Run 访问或非法证据 ID
        """
        entry = evidence_registry.get(evidence_id, run_id=self.context.run_id)

        if entry is None:
            raise AgentSecurityError(
                f"Evidence {evidence_id} not found or not accessible in this run"
            )

        # 验证 principal 匹配
        if entry.get("principal_id") != self.context.principal_id:
            raise AgentSecurityError(f"Evidence {evidence_id} belongs to different principal")


def create_trusted_context(
    *,
    run_id: str,
    conversation_id: str,
    principal_id: str,
    scope_type: str,
    scope_document_id: str | None = None,
    allow_external_llm: bool = True,
) -> RunContext:
    """
    创建可信上下文（服务端调用）

    这是唯一创建 RunContext 的合法入口，确保所有上下文都经过验证。

    Args:
        run_id: Run ID
        conversation_id: 会话 ID
        principal_id: 用户 ID
        scope_type: 检索范围类型
        scope_document_id: 可选文档范围
        allow_external_llm: 是否允许外部 LLM

    Returns:
        可信 RunContext
    """
    return RunContext(
        run_id=run_id,
        conversation_id=conversation_id,
        principal_id=principal_id,
        scope_type=scope_type,
        scope_document_id=scope_document_id,
        allow_external_llm=allow_external_llm,
    )
