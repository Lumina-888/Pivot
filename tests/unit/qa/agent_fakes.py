"""
Agent 测试 Fake 对象与辅助工具

用途：为 ND-AGENT-02 系列测试提供可控的 Fake 实现。
状态：基础设施准备，等待 02-A/B/C 签认后实施业务逻辑。

设计原则：
- 所有 Fake 对象仅用于单元测试，不进入生产代码
- 预设响应序列，支持断言调用历史
- 明确标记 unit_fake_only，不替代真实模型/供应商验收
"""

from __future__ import annotations

from typing import Any

# ====================
# Fake AgentModel
# ====================


class FakeAgentModel:
    """
    可编程的 Fake 模型，返回预设的工具调用序列。

    用于测试 StateGraph 条件循环和工具选择逻辑。
    不实现真实的 LLM 推理，只返回预先配置的响应。
    """

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        """
        Args:
            responses: 预设的响应序列，每次 decide 调用返回下一个
        """
        self.responses = responses
        self.call_history: list[dict[str, Any]] = []
        self.current_index = 0

    def decide(self, messages: list[Any], context: dict[str, Any]) -> dict[str, Any]:
        """
        返回预设的下一个响应。

        记录调用历史用于断言。
        """
        self.call_history.append({"messages": messages, "context": context})

        if self.current_index >= len(self.responses):
            raise RuntimeError(
                f"FakeAgentModel: 已用完所有预设响应 (调用 {self.current_index + 1} 次)"
            )

        response = self.responses[self.current_index]
        self.current_index += 1
        return response

    def reset(self) -> None:
        """重置调用历史和索引，用于多次测试场景。"""
        self.call_history.clear()
        self.current_index = 0


# ====================
# Fake ToolExecutor
# ====================


class FakeToolExecutor:
    """
    可编程的 Fake 工具执行器。

    用于测试工具调用流程，不执行真实的检索或读取。
    """

    def __init__(self, tool_responses: dict[str, Any] | None = None) -> None:
        """
        Args:
            tool_responses: 按工具名称映射的响应配置
        """
        self.tool_responses = tool_responses or {}
        self.call_history: list[dict[str, Any]] = []

    def execute(self, tool_call: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """
        执行工具调用，返回预设或默认响应。

        Args:
            tool_call: 包含 id/name/args 的工具调用
            context: 执行上下文

        Returns:
            包含 tool_call_id 和 content 的 ToolMessage
        """
        self.call_history.append({"tool_call": tool_call, "context": context})

        tool_name = tool_call.get("name")
        tool_call_id = tool_call.get("id")

        if tool_name in self.tool_responses:
            content = self.tool_responses[tool_name]
        else:
            # 默认响应
            content = {"status": "success", "result": f"Fake result for {tool_name}"}

        return {"tool_call_id": tool_call_id, "content": content}


# ====================
# Fake EvidenceRegistry
# ====================


class FakeEvidenceRegistry:
    """
    内存 EvidenceRegistry，用于测试证据追踪。

    不持久化，每次测试独立创建。
    """

    def __init__(self) -> None:
        self.registry: dict[str, dict[str, Any]] = {}
        self.next_id = 1

    def register(
        self, evidence_data: dict[str, Any], run_id: str, tool_call_id: str
    ) -> str:
        """
        注册证据，返回 evidence_id。

        Args:
            evidence_data: 包含 document_id/chunk_id/version_id 等的证据信息
            run_id: 所属 Run ID
            tool_call_id: 来源工具调用 ID

        Returns:
            生成的 evidence_id
        """
        evidence_id = f"ev_{self.next_id}"
        self.next_id += 1

        self.registry[evidence_id] = {
            "evidence_id": evidence_id,
            "run_id": run_id,
            "tool_call_id": tool_call_id,
            **evidence_data,
        }

        return evidence_id

    def get(self, evidence_id: str, run_id: str) -> dict[str, Any] | None:
        """
        获取证据，验证所属 Run。

        Args:
            evidence_id: 证据 ID
            run_id: 请求的 Run ID

        Returns:
            证据数据，如果不存在或 Run 不匹配返回 None
        """
        entry = self.registry.get(evidence_id)
        if entry and entry.get("run_id") == run_id:
            return entry
        return None

    def list_for_run(self, run_id: str) -> list[dict[str, Any]]:
        """列出指定 Run 的所有证据。"""
        return [entry for entry in self.registry.values() if entry.get("run_id") == run_id]


# ====================
# Fake StructuredFinalizer
# ====================


class FakeStructuredFinalizer:
    """
    可编程的 Fake Finalizer。

    用于测试答案生成和验证流程。
    """

    def __init__(self, response: dict[str, Any] | None = None) -> None:
        """
        Args:
            response: 预设的 finalize 响应
        """
        self.response = response or {
            "answer": "根据规定...",
            "claims": [{"text": "迟到三次以上记为旷工", "evidence_ids": ["ev_1"]}],
        }
        self.call_history: list[dict[str, Any]] = []

    def finalize(
        self, question: str, evidences: list[dict[str, Any]], context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        生成结构化答案。

        Args:
            question: 用户问题
            evidences: 已授权的证据列表
            context: 执行上下文

        Returns:
            包含 answer/claims 的结构化结果
        """
        self.call_history.append(
            {"question": question, "evidences": evidences, "context": context}
        )
        return self.response


# ====================
# 辅助构造函数
# ====================


def make_tool_call(
    call_id: str, tool_name: str, args: dict[str, Any]
) -> dict[str, Any]:
    """
    构造标准工具调用对象。

    Args:
        call_id: 工具调用 ID
        tool_name: 工具名称 (search_knowledge 或 read_evidence)
        args: 工具参数

    Returns:
        标准工具调用字典
    """
    return {"id": call_id, "name": tool_name, "args": args}


def make_tool_message(tool_call_id: str, content: Any) -> dict[str, Any]:
    """
    构造标准 ToolMessage。

    Args:
        tool_call_id: 对应的工具调用 ID
        content: 工具响应内容

    Returns:
        标准 ToolMessage 字典
    """
    return {"tool_call_id": tool_call_id, "content": content}


def make_search_result(
    status: str = "found", evidences: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """
    构造搜索结果。

    Args:
        status: 状态 (empty/found)
        evidences: 证据候选列表

    Returns:
        搜索结果字典
    """
    return {"status": status, "evidences": evidences or []}


def make_evidence_entry(
    document_id: str,
    chunk_id: str,
    version_id: str,
    summary: str | None = None,
    content: str | None = None,
) -> dict[str, Any]:
    """
    构造证据条目。

    Args:
        document_id: 文档 ID
        chunk_id: Chunk ID
        version_id: 版本 ID
        summary: 可选摘要
        content: 可选完整内容

    Returns:
        证据条目字典
    """
    entry = {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "version_id": version_id,
    }
    if summary is not None:
        entry["summary"] = summary
    if content is not None:
        entry["content"] = content
    return entry
