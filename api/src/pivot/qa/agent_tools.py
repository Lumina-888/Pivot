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
from pivot.qa.ports import EvidenceHit, EvidenceResolver, Retriever

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


def _valid_sources(sources: object) -> bool:
    return isinstance(sources, list) and all(
        isinstance(item, dict)
        and set(item) == {"tool_call_id", "tool"}
        and isinstance(item["tool_call_id"], str)
        and isinstance(item["tool"], str)
        for item in sources
    )


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

    @staticmethod
    def _identity(hit: EvidenceHit) -> tuple[str, str, str, str]:
        return (hit.document_id, hit.version_id, hit.chunk_id, hit.index_generation)

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
            identity = self._identity(hit)
            existing_id = next(
                (
                    evidence_id
                    for evidence_id, entry in self._registry.items()
                    if entry["run_id"] == run_id
                    and entry["principal_id"] == principal_id
                    and (
                        entry["document_id"],
                        entry["version_id"],
                        entry["chunk_id"],
                        entry["index_generation"],
                    )
                    == identity
                ),
                None,
            )
            source = {"tool_call_id": tool_call_id, "tool": "search_knowledge"}
            if existing_id is not None:
                entry = self._registry[existing_id]
                if (entry["text"], entry["locator"]) != (hit.text, hit.locator):
                    raise AgentToolError("inconsistent evidence identity")
                entry["sources"].append(source)
                entry["tool_call_id"] = tool_call_id
                evidence_ids.append(existing_id)
                continue

            evidence_id = f"ev_{self._next_id}"
            self._next_id += 1
            self._registry[evidence_id] = {
                "evidence_id": evidence_id,
                "run_id": run_id,
                "tool_call_id": tool_call_id,
                "sources": [source],
                "principal_id": principal_id,
                "document_id": hit.document_id,
                "version_id": hit.version_id,
                "chunk_id": hit.chunk_id,
                "text": hit.text,
                "locator": hit.locator,
                "external_llm_allowed": hit.external_llm_allowed,
                "index_generation": hit.index_generation,
                "embedding_model_version": hit.embedding_model_version,
                "retrieval_config_version": hit.retrieval_config_version,
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
        return [entry for entry in self._registry.values() if entry.get("run_id") == run_id]

    def version_conflicts(self, document_id: str, *, run_id: str) -> list[dict[str, Any]]:
        """返回本 Run 内同一文档的不同版本，单一版本不是冲突。"""
        versions = {
            entry["version_id"]
            for entry in self._registry.values()
            if entry.get("run_id") == run_id and entry.get("document_id") == document_id
        }
        if len(versions) < 2:
            return []
        return [
            {"document_id": document_id, "version_id": version_id}
            for version_id in sorted(versions)
        ]

    def snapshot(self) -> dict[str, Any]:
        """Sensitive server-side graph state, never a public response."""
        return {key: dict(entry) for key, entry in self._registry.items()}

    @classmethod
    def restore(
        cls,
        data: dict[str, Any],
        *,
        run_id: str,
        principal_id: str,
    ) -> EvidenceRegistry:
        registry = cls()
        fields = {
            "evidence_id",
            "run_id",
            "tool_call_id",
            "sources",
            "principal_id",
            "document_id",
            "version_id",
            "chunk_id",
            "text",
            "locator",
            "external_llm_allowed",
            "index_generation",
            "embedding_model_version",
            "retrieval_config_version",
        }
        for evidence_id, entry in data.items():
            if (
                not isinstance(entry, dict)
                or set(entry) != fields
                or entry.get("run_id") != run_id
                or entry.get("principal_id") != principal_id
                or entry.get("evidence_id") != evidence_id
                or type(entry.get("external_llm_allowed")) is not bool
                or not _valid_sources(entry.get("sources"))
                or any(
                    not isinstance(entry[key], str)
                    for key in fields - {"external_llm_allowed", "sources"}
                )
            ):
                raise AgentToolError("invalid evidence registry state")
            prefix, separator, number = evidence_id.partition("_")
            if prefix != "ev" or not separator or not number.isdecimal() or int(number) < 1:
                raise AgentToolError("invalid evidence registry state")
            registry._registry[evidence_id] = dict(entry)
            registry._next_id = max(registry._next_id, int(number) + 1)
        return registry

    def record_tool_call(self, evidence_ids: list[str], *, run_id: str, tool_call_id: str):
        for evidence_id in evidence_ids:
            entry = self.get(evidence_id, run_id=run_id)
            if entry is not None:
                entry["tool_call_id"] = tool_call_id


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

    def __init__(self, resolver: EvidenceResolver | None = None) -> None:
        self._resolver = resolver

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

        if evidence["principal_id"] != principal_id or (
            scope_type == "document" and evidence["document_id"] != scope_document_id
        ):
            raise AgentToolError("evidence not accessible")
        if self._resolver is not None:
            hit = self._resolver.resolve_evidence(
                evidence["chunk_id"],
                principal_id=principal_id,
                scope_type=scope_type,
                scope_document_id=scope_document_id,
            )
            if hit is None or (hit.document_id, hit.version_id) != (
                evidence["document_id"],
                evidence["version_id"],
            ):
                raise AgentToolError("evidence not accessible")
            evidence = {
                **evidence,
                "text": hit.text,
                "locator": hit.locator,
                "external_llm_allowed": hit.external_llm_allowed,
            }
        if evidence["external_llm_allowed"] is not True:
            raise AgentToolError("evidence external use not allowed")

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
            "read_evidence": ReadEvidenceTool(
                retriever if isinstance(retriever, EvidenceResolver) else None,
            ),
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
                f"Tool '{tool_name}' is not allowed. Allowed tools: {sorted(self._tools.keys())}"
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

            if tool_name == "search_knowledge":
                evidence_registry.record_tool_call(
                    result["evidence_ids"],
                    run_id=run_id,
                    tool_call_id=tool_call_id or "",
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
