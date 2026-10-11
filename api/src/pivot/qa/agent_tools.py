"""
Agent 只读工具实现

实现 FR-AGENT-002：白名单只读工具
- search_knowledge: 检索知识库
- read_evidence: 读取证据详情
- 严格参数验证，拒绝额外字段
- 服务端授权和重授权
"""

from __future__ import annotations

from typing import Any, Protocol

from pivot.qa.errors import AgentToolError, UnknownToolError
from pivot.qa.ports import EvidenceHit, Retriever

# ====================
# 工具协议
# ====================


class AgentTool(Protocol):
    """Agent 工具协议"""

    @property
    def name(self) -> str:
        """工具名称"""
        ...

    def execute(
        self,
        args: dict[str, Any],
        *,
        run_id: str,
        principal_id: str,
        scope_type: str,
        scope_document_id: str | None,
        evidence_registry: EvidenceRegistry,
    ) -> dict[str, Any]:
        """
        执行工具调用

        Args:
            args: 工具参数
            run_id: Run ID
            principal_id: 用户 ID
            scope_type: 检索范围类型
            scope_document_id: 可选文档范围
            evidence_registry: 证据注册表

        Returns:
            工具执行结果

        Raises:
            AgentToolError: 参数错误或执行失败
        """
        ...


# ====================
# EvidenceRegistry
# ====================


class EvidenceRegistry:
    """
    证据注册表

    追踪 Agent 工具返回的证据来源，支持：
    - 完整来源追踪（document_id/version_id/chunk_id）
    - Run 隔离（跨 Run 访问拒绝）
    - 重授权检查（读取时验证版本/删除/权限）
    """

    def __init__(self) -> None:
        self._registry: dict[str, dict[str, Any]] = {}
        self._next_id = 1

    def register_search_result(
        self,
        hits: tuple[EvidenceHit, ...],
        *,
        run_id: str,
        tool_call_id: str,
        principal_id: str,
    ) -> list[str]:
        """
        注册搜索结果

        Args:
            hits: 检索命中的证据
            run_id: Run ID
            tool_call_id: 工具调用 ID
            principal_id: 用户 ID

        Returns:
            生成的 evidence_id 列表
        """
        evidence_ids = []
        for hit in hits:
            evidence_id = f"ev_{self._next_id}"
            self._next_id += 1

            self._registry[evidence_id] = {
                "evidence_id": evidence_id,
                "run_id": run_id,
                "tool_call_id": tool_call_id,
                "principal_id": principal_id,
                "document_id": hit.document_id,
                "version_id": hit.version_id,
                "chunk_id": hit.chunk_id,
                "text": hit.text,
                "locator": hit.locator,
                "external_llm_allowed": hit.external_llm_allowed,
            }
            evidence_ids.append(evidence_id)

        return evidence_ids

    def get(self, evidence_id: str, *, run_id: str) -> dict[str, Any] | None:
        """
        获取证据（验证 Run 所属）

        Args:
            evidence_id: 证据 ID
            run_id: 请求的 Run ID

        Returns:
            证据数据，如果不存在或 Run 不匹配返回 None
        """
        entry = self._registry.get(evidence_id)
        if entry and entry.get("run_id") == run_id:
            return entry
        return None

    def list_for_run(self, run_id: str) -> list[dict[str, Any]]:
        """列出指定 Run 的所有证据"""
        return [
            entry for entry in self._registry.values() if entry.get("run_id") == run_id
        ]


# ====================
# 搜索工具
# ====================


class SearchKnowledgeTool:
    """search_knowledge 工具：检索知识库"""

    def __init__(self, retriever: Retriever) -> None:
        self._retriever = retriever

    @property
    def name(self) -> str:
        return "search_knowledge"

    def execute(
        self,
        args: dict[str, Any],
        *,
        run_id: str,
        principal_id: str,
        scope_type: str,
        scope_document_id: str | None,
        evidence_registry: EvidenceRegistry,
    ) -> dict[str, Any]:
        """
        执行搜索

        要求：
        - 只接受 query 参数
        - 拒绝额外参数
        - 返回 evidence_id 列表
        """
        # 严格参数验证
        if "query" not in args:
            raise AgentToolError("search_knowledge requires 'query' parameter")

        # 拒绝额外参数
        extra_keys = set(args.keys()) - {"query"}
        if extra_keys:
            raise AgentToolError(
                f"search_knowledge does not accept extra parameters: {sorted(extra_keys)}"
            )

        query = args["query"]
        if not isinstance(query, str) or not query.strip():
            raise AgentToolError("query must be a non-empty string")

        # 执行检索
        result = self._retriever.retrieve(
            query,
            scope_type=scope_type,
            scope_document_id=scope_document_id,
            principal_id=principal_id,
        )

        # 注册证据
        # tool_call_id 应由调用者传入，这里暂时使用占位符
        evidence_ids = evidence_registry.register_search_result(
            result.evidence,
            run_id=run_id,
            tool_call_id="",  # 将在实际集成时传入
            principal_id=principal_id,
        )

        return {
            "status": result.status,
            "evidence_ids": evidence_ids,
            "count": len(evidence_ids),
        }


# ====================
# 读取证据工具
# ====================


class ReadEvidenceTool:
    """read_evidence 工具：读取证据详情"""

    @property
    def name(self) -> str:
        return "read_evidence"

    def execute(
        self,
        args: dict[str, Any],
        *,
        run_id: str,
        principal_id: str,
        scope_type: str,
        scope_document_id: str | None,
        evidence_registry: EvidenceRegistry,
    ) -> dict[str, Any]:
        """
        读取证据

        要求：
        - 只接受 evidence_id 参数
        - 拒绝额外参数
        - 验证 evidence_id 属于当前 Run
        - 重新检查权限（版本/删除/外发）
        """
        # 严格参数验证
        if "evidence_id" not in args:
            raise AgentToolError("read_evidence requires 'evidence_id' parameter")

        # 拒绝额外参数
        extra_keys = set(args.keys()) - {"evidence_id"}
        if extra_keys:
            raise AgentToolError(
                f"read_evidence does not accept extra parameters: {sorted(extra_keys)}"
            )

        evidence_id = args["evidence_id"]
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise AgentToolError("evidence_id must be a non-empty string")

        # 获取证据（验证 Run 所属）
        evidence = evidence_registry.get(evidence_id, run_id=run_id)
        if evidence is None:
            # 不泄露是否存在
            raise AgentToolError(f"evidence_id not found or not accessible: {evidence_id}")

        # TODO: 重新检查版本/删除/外发权限
        # 当前简化实现，返回证据内容

        return {
            "evidence_id": evidence_id,
            "document_id": evidence["document_id"],
            "version_id": evidence["version_id"],
            "chunk_id": evidence["chunk_id"],
            "text": evidence["text"],
            "locator": evidence["locator"],
        }


# ====================
# 工具执行器
# ====================


class ToolExecutor:
    """
    工具执行器

    管理工具白名单，执行工具调用
    """

    def __init__(self, retriever: Retriever) -> None:
        self._tools: dict[str, AgentTool] = {
            "search_knowledge": SearchKnowledgeTool(retriever),
            "read_evidence": ReadEvidenceTool(),
        }

    def execute(
        self,
        tool_call: dict[str, Any],
        *,
        run_id: str,
        principal_id: str,
        scope_type: str,
        scope_document_id: str | None,
        evidence_registry: EvidenceRegistry,
    ) -> dict[str, Any]:
        """
        执行工具调用

        Args:
            tool_call: 包含 id/name/args 的工具调用
            run_id: Run ID
            principal_id: 用户 ID
            scope_type: 检索范围类型
            scope_document_id: 可选文档范围
            evidence_registry: 证据注册表

        Returns:
            工具执行结果（包含 tool_call_id）

        Raises:
            UnknownToolError: 工具不在白名单
            AgentToolError: 参数错误或执行失败
        """
        tool_name = tool_call.get("name")
        tool_call_id = tool_call.get("id")
        args = tool_call.get("args", {})

        # 白名单检查
        if tool_name not in self._tools:
            raise UnknownToolError(
                f"Tool '{tool_name}' is not allowed. "
                f"Allowed tools: {sorted(self._tools.keys())}"
            )

        tool = self._tools[tool_name]

        # 执行工具
        try:
            result = tool.execute(
                args,
                run_id=run_id,
                principal_id=principal_id,
                scope_type=scope_type,
                scope_document_id=scope_document_id,
                evidence_registry=evidence_registry,
            )

            # 返回 ToolMessage 格式
            return {
                "tool_call_id": tool_call_id,
                "content": result,
            }
        except AgentToolError:
            raise
        except Exception as e:
            raise AgentToolError(f"Tool execution failed: {e}") from e
