"""
ND-AGENT-02-D 单元测试：只读工具与 EvidenceRegistry

测试覆盖：
- FR-AGENT-002: 工具白名单
- 严格参数验证
- EvidenceRegistry Run 隔离
- 证据追踪完整性
"""

from __future__ import annotations

import pytest

from pivot.qa.agent_tools import (
    EvidenceRegistry,
    ReadEvidenceTool,
    SearchKnowledgeTool,
    ToolExecutor,
)
from pivot.qa.errors import AgentToolError, UnknownToolError
from pivot.qa.ports import EvidenceHit, RetrievalResult


# ====================
# Fake Retriever
# ====================


class FakeRetriever:
    def __init__(self, result: RetrievalResult) -> None:
        self.result = result
        self.calls: list[dict] = []

    def retrieve(self, question, *, scope_type, scope_document_id, principal_id):
        self.calls.append(
            {
                "question": question,
                "scope_type": scope_type,
                "scope_document_id": scope_document_id,
                "principal_id": principal_id,
            }
        )
        return self.result


# ====================
# SearchKnowledgeTool 测试
# ====================


def test_search_knowledge_accepts_only_query_parameter():
    """
    Given: search_knowledge 工具
    When: 传入额外参数
    Then: 应该拒绝并抛出 AgentToolError
    """
    hit = EvidenceHit(
        chunk_id="chk_1",
        document_id="doc_1",
        version_id="ver_1",
        text="考勤规定",
        locator="page=1",
    )
    retriever = FakeRetriever(RetrievalResult(status="found", evidence=(hit,)))
    tool = SearchKnowledgeTool(retriever)
    registry = EvidenceRegistry()

    # 额外参数应该被拒绝
    with pytest.raises(AgentToolError) as exc_info:
        tool.execute(
            {"query": "考勤", "extra_param": "not_allowed"},
            run_id="run_1",
            principal_id="user_1",
            scope_type="shared",
            scope_document_id=None,
            evidence_registry=registry,
        )

    assert "extra_param" in str(exc_info.value)
    assert "does not accept extra parameters" in str(exc_info.value)


def test_search_knowledge_requires_query_parameter():
    """
    Given: search_knowledge 工具
    When: 缺少 query 参数
    Then: 应该拒绝
    """
    retriever = FakeRetriever(RetrievalResult(status="empty", evidence=()))
    tool = SearchKnowledgeTool(retriever)
    registry = EvidenceRegistry()

    with pytest.raises(AgentToolError) as exc_info:
        tool.execute(
            {},
            run_id="run_1",
            principal_id="user_1",
            scope_type="shared",
            scope_document_id=None,
            evidence_registry=registry,
        )

    assert "requires 'query' parameter" in str(exc_info.value)


def test_search_knowledge_rejects_empty_query():
    """
    Given: search_knowledge 工具
    When: query 为空字符串
    Then: 应该拒绝
    """
    retriever = FakeRetriever(RetrievalResult(status="empty", evidence=()))
    tool = SearchKnowledgeTool(retriever)
    registry = EvidenceRegistry()

    with pytest.raises(AgentToolError) as exc_info:
        tool.execute(
            {"query": "  "},
            run_id="run_1",
            principal_id="user_1",
            scope_type="shared",
            scope_document_id=None,
            evidence_registry=registry,
        )

    assert "non-empty string" in str(exc_info.value)


def test_search_knowledge_returns_evidence_ids():
    """
    Given: search_knowledge 返回证据
    When: 执行搜索
    Then: 应该注册证据并返回 evidence_id 列表
    """
    hit1 = EvidenceHit(
        chunk_id="chk_1",
        document_id="doc_1",
        version_id="ver_1",
        text="迟到三次记旷工",
        locator="page=1",
    )
    hit2 = EvidenceHit(
        chunk_id="chk_2",
        document_id="doc_1",
        version_id="ver_1",
        text="旷工扣除当日工资",
        locator="page=2",
    )
    retriever = FakeRetriever(RetrievalResult(status="found", evidence=(hit1, hit2)))
    tool = SearchKnowledgeTool(retriever)
    registry = EvidenceRegistry()

    result = tool.execute(
        {"query": "考勤规定"},
        run_id="run_1",
        principal_id="user_1",
        scope_type="shared",
        scope_document_id=None,
        evidence_registry=registry,
    )

    assert result["status"] == "found"
    assert result["count"] == 2
    assert len(result["evidence_ids"]) == 2
    assert all(eid.startswith("ev_") for eid in result["evidence_ids"])


# ====================
# ReadEvidenceTool 测试
# ====================


def test_read_evidence_accepts_only_evidence_id_parameter():
    """
    Given: read_evidence 工具
    When: 传入额外参数
    Then: 应该拒绝
    """
    tool = ReadEvidenceTool()
    registry = EvidenceRegistry()

    with pytest.raises(AgentToolError) as exc_info:
        tool.execute(
            {"evidence_id": "ev_1", "extra_param": "not_allowed"},
            run_id="run_1",
            principal_id="user_1",
            scope_type="shared",
            scope_document_id=None,
            evidence_registry=registry,
        )

    assert "extra_param" in str(exc_info.value)


def test_read_evidence_requires_evidence_id_parameter():
    """
    Given: read_evidence 工具
    When: 缺少 evidence_id 参数
    Then: 应该拒绝
    """
    tool = ReadEvidenceTool()
    registry = EvidenceRegistry()

    with pytest.raises(AgentToolError) as exc_info:
        tool.execute(
            {},
            run_id="run_1",
            principal_id="user_1",
            scope_type="shared",
            scope_document_id=None,
            evidence_registry=registry,
        )

    assert "requires 'evidence_id' parameter" in str(exc_info.value)


def test_read_evidence_rejects_empty_evidence_id():
    """
    Given: read_evidence 工具
    When: evidence_id 为空
    Then: 应该拒绝
    """
    tool = ReadEvidenceTool()
    registry = EvidenceRegistry()

    with pytest.raises(AgentToolError) as exc_info:
        tool.execute(
            {"evidence_id": "  "},
            run_id="run_1",
            principal_id="user_1",
            scope_type="shared",
            scope_document_id=None,
            evidence_registry=registry,
        )

    assert "non-empty string" in str(exc_info.value)


def test_read_evidence_rejects_foreign_run_evidence():
    """
    Given: 证据属于 run_1
    When: run_2 尝试读取
    Then: 应该拒绝，不泄露存在性
    """
    # 注册证据
    registry = EvidenceRegistry()
    hit = EvidenceHit(
        chunk_id="chk_1",
        document_id="doc_1",
        version_id="ver_1",
        text="机密信息",
        locator="page=1",
    )
    evidence_ids = registry.register_search_result(
        (hit,), run_id="run_1", tool_call_id="call_1", principal_id="user_1"
    )

    # run_2 尝试读取
    tool = ReadEvidenceTool()
    with pytest.raises(AgentToolError) as exc_info:
        tool.execute(
            {"evidence_id": evidence_ids[0]},
            run_id="run_2",
            principal_id="user_2",
            scope_type="shared",
            scope_document_id=None,
            evidence_registry=registry,
        )

    # 不泄露存在性
    assert "not found or not accessible" in str(exc_info.value)


def test_read_evidence_returns_full_content():
    """
    Given: 证据已注册
    When: 同一 Run 读取
    Then: 应该返回完整证据内容
    """
    registry = EvidenceRegistry()
    hit = EvidenceHit(
        chunk_id="chk_1",
        document_id="doc_1",
        version_id="ver_1",
        text="完整考勤规定内容...",
        locator="page=1,section=2",
        external_llm_allowed=True,
    )
    evidence_ids = registry.register_search_result(
        (hit,), run_id="run_1", tool_call_id="call_1", principal_id="user_1"
    )

    tool = ReadEvidenceTool()
    result = tool.execute(
        {"evidence_id": evidence_ids[0]},
        run_id="run_1",
        principal_id="user_1",
        scope_type="shared",
        scope_document_id=None,
        evidence_registry=registry,
    )

    assert result["evidence_id"] == evidence_ids[0]
    assert result["document_id"] == "doc_1"
    assert result["version_id"] == "ver_1"
    assert result["chunk_id"] == "chk_1"
    assert result["text"] == "完整考勤规定内容..."
    assert result["locator"] == "page=1,section=2"


# ====================
# EvidenceRegistry 测试
# ====================


def test_evidence_registry_tracks_search_origin():
    """
    Given: search_knowledge 返回证据
    When: 注册到 EvidenceRegistry
    Then: 应该包含完整来源追踪信息
    """
    registry = EvidenceRegistry()
    hit = EvidenceHit(
        chunk_id="chk_a",
        document_id="doc_123",
        version_id="ver_456",
        text="考勤规定内容",
        locator="page=5",
    )

    evidence_ids = registry.register_search_result(
        (hit,),
        run_id="run_abc",
        tool_call_id="call_xyz",
        principal_id="user_789",
    )

    assert len(evidence_ids) == 1
    evidence = registry.get(evidence_ids[0], run_id="run_abc")
    assert evidence is not None
    assert evidence["run_id"] == "run_abc"
    assert evidence["tool_call_id"] == "call_xyz"
    assert evidence["principal_id"] == "user_789"
    assert evidence["document_id"] == "doc_123"
    assert evidence["version_id"] == "ver_456"
    assert evidence["chunk_id"] == "chk_a"


def test_evidence_registry_isolates_runs():
    """
    Given: 两个不同的 Run
    When: 各自注册证据
    Then: 不能跨 Run 访问
    """
    registry = EvidenceRegistry()
    hit1 = EvidenceHit(
        chunk_id="chk_1", document_id="doc_1", version_id="ver_1", text="内容1"
    )
    hit2 = EvidenceHit(
        chunk_id="chk_2", document_id="doc_2", version_id="ver_2", text="内容2"
    )

    # Run 1 注册
    ids1 = registry.register_search_result(
        (hit1,), run_id="run_1", tool_call_id="call_1", principal_id="user_1"
    )

    # Run 2 注册
    ids2 = registry.register_search_result(
        (hit2,), run_id="run_2", tool_call_id="call_2", principal_id="user_2"
    )

    # Run 1 不能访问 Run 2 的证据
    assert registry.get(ids2[0], run_id="run_1") is None

    # Run 2 不能访问 Run 1 的证据
    assert registry.get(ids1[0], run_id="run_2") is None

    # 各自可以访问自己的
    assert registry.get(ids1[0], run_id="run_1") is not None
    assert registry.get(ids2[0], run_id="run_2") is not None


def test_evidence_registry_dedupes_same_version_and_keeps_sources():
    """同一文档版本代次重复命中时复用 evidence_id，并保留每次来源。"""
    registry = EvidenceRegistry()
    hit = EvidenceHit(
        chunk_id="chk_1",
        document_id="doc_1",
        version_id="ver_1",
        text="迟到三次记旷工",
        locator="page=1",
        index_generation="idx_1",
        embedding_model_version="emb_1",
        retrieval_config_version="ret_1",
    )

    first = registry.register_search_result(
        (hit,), run_id="run_1", tool_call_id="call_1", principal_id="user_1"
    )
    second = registry.register_search_result(
        (hit,), run_id="run_1", tool_call_id="call_2", principal_id="user_1"
    )

    assert first == second
    entry = registry.get(first[0], run_id="run_1")
    assert entry is not None
    assert entry["sources"] == [
        {"tool_call_id": "call_1", "tool": "search_knowledge"},
        {"tool_call_id": "call_2", "tool": "search_knowledge"},
    ]
    assert entry["index_generation"] == "idx_1"
    assert len(registry.list_for_run("run_1")) == 1


def test_evidence_registry_keeps_distinct_versions_and_records_conflict():
    """同一文档的不同版本不合并，并记录版本冲突。"""
    registry = EvidenceRegistry()
    older = EvidenceHit(
        chunk_id="chk_1", document_id="doc_1", version_id="ver_1", text="旧规定"
    )
    newer = EvidenceHit(
        chunk_id="chk_1", document_id="doc_1", version_id="ver_2", text="新规定"
    )

    first = registry.register_search_result(
        (older,), run_id="run_1", tool_call_id="call_1", principal_id="user_1"
    )
    second = registry.register_search_result(
        (newer,), run_id="run_1", tool_call_id="call_2", principal_id="user_1"
    )

    assert first != second
    conflicts = registry.version_conflicts("doc_1", run_id="run_1")
    assert {item["version_id"] for item in conflicts} == {"ver_1", "ver_2"}


def test_evidence_registry_snapshot_round_trip():
    """快照恢复后保留去重身份、来源和配置追踪。"""
    registry = EvidenceRegistry()
    hit = EvidenceHit(
        chunk_id="chk_1",
        document_id="doc_1",
        version_id="ver_1",
        text="原文",
        locator="page=1",
        external_llm_allowed=True,
        index_generation="idx_1",
        embedding_model_version="emb_1",
        retrieval_config_version="ret_1",
    )
    evidence_id = registry.register_search_result(
        (hit,), run_id="run_1", tool_call_id="call_1", principal_id="user_1"
    )[0]

    restored = EvidenceRegistry.restore(
        registry.snapshot(), run_id="run_1", principal_id="user_1"
    )
    entry = restored.get(evidence_id, run_id="run_1")

    assert entry is not None
    assert entry["sources"] == [{"tool_call_id": "call_1", "tool": "search_knowledge"}]
    assert entry["index_generation"] == "idx_1"
    assert entry["embedding_model_version"] == "emb_1"
    assert entry["retrieval_config_version"] == "ret_1"


def test_evidence_registry_rejects_inconsistent_duplicate_identity():
    """相同身份的内容不一致时拒绝覆盖。"""
    registry = EvidenceRegistry()
    original = EvidenceHit(
        chunk_id="chk_1", document_id="doc_1", version_id="ver_1", text="原文"
    )
    changed = EvidenceHit(
        chunk_id="chk_1", document_id="doc_1", version_id="ver_1", text="被改写的原文"
    )
    registry.register_search_result(
        (original,), run_id="run_1", tool_call_id="call_1", principal_id="user_1"
    )

    with pytest.raises(AgentToolError, match="inconsistent"):
        registry.register_search_result(
            (changed,), run_id="run_1", tool_call_id="call_2", principal_id="user_1"
        )


def test_evidence_registry_list_for_run():
    """
    Given: EvidenceRegistry 包含多个 Run 的证据
    When: 查询特定 Run 的证据列表
    Then: 只返回该 Run 的证据
    """
    registry = EvidenceRegistry()
    hit1 = EvidenceHit(
        chunk_id="chk_1", document_id="doc_1", version_id="ver_1", text="内容1"
    )
    hit2 = EvidenceHit(
        chunk_id="chk_2", document_id="doc_2", version_id="ver_2", text="内容2"
    )
    hit3 = EvidenceHit(
        chunk_id="chk_3", document_id="doc_3", version_id="ver_3", text="内容3"
    )

    registry.register_search_result(
        (hit1, hit2), run_id="run_1", tool_call_id="call_1", principal_id="user_1"
    )
    registry.register_search_result(
        (hit3,), run_id="run_2", tool_call_id="call_2", principal_id="user_2"
    )

    # Run 1 应该有 2 个证据
    run1_evidence = registry.list_for_run("run_1")
    assert len(run1_evidence) == 2
    assert all(e["run_id"] == "run_1" for e in run1_evidence)

    # Run 2 应该有 1 个证据
    run2_evidence = registry.list_for_run("run_2")
    assert len(run2_evidence) == 1
    assert run2_evidence[0]["run_id"] == "run_2"


# ====================
# ToolExecutor 测试
# ====================


def test_tool_executor_rejects_unknown_tool():
    """
    Given: ToolExecutor 有白名单
    When: 调用未在白名单中的工具
    Then: 应该抛出 UnknownToolError
    """
    retriever = FakeRetriever(RetrievalResult(status="empty", evidence=()))
    executor = ToolExecutor(retriever)
    registry = EvidenceRegistry()

    with pytest.raises(UnknownToolError) as exc_info:
        executor.execute(
            {"id": "call_1", "name": "execute_shell", "args": {"command": "ls"}},
            run_id="run_1",
            principal_id="user_1",
            scope_type="shared",
            scope_document_id=None,
            evidence_registry=registry,
        )

    assert "execute_shell" in str(exc_info.value)
    assert "not allowed" in str(exc_info.value)


def test_tool_executor_lists_allowed_tools():
    """
    Given: ToolExecutor
    When: 调用未知工具
    Then: 错误消息应该列出允许的工具
    """
    retriever = FakeRetriever(RetrievalResult(status="empty", evidence=()))
    executor = ToolExecutor(retriever)
    registry = EvidenceRegistry()

    with pytest.raises(UnknownToolError) as exc_info:
        executor.execute(
            {"id": "call_1", "name": "unknown_tool", "args": {}},
            run_id="run_1",
            principal_id="user_1",
            scope_type="shared",
            scope_document_id=None,
            evidence_registry=registry,
        )

    error_msg = str(exc_info.value)
    assert "search_knowledge" in error_msg
    assert "read_evidence" in error_msg


def test_tool_executor_returns_tool_message_format():
    """
    Given: ToolExecutor
    When: 执行工具
    Then: 应该返回包含 tool_call_id 的 ToolMessage 格式
    """
    hit = EvidenceHit(
        chunk_id="chk_1", document_id="doc_1", version_id="ver_1", text="内容"
    )
    retriever = FakeRetriever(RetrievalResult(status="found", evidence=(hit,)))
    executor = ToolExecutor(retriever)
    registry = EvidenceRegistry()

    result = executor.execute(
        {"id": "call_abc123", "name": "search_knowledge", "args": {"query": "考勤"}},
        run_id="run_1",
        principal_id="user_1",
        scope_type="shared",
        scope_document_id=None,
        evidence_registry=registry,
    )

    assert "tool_call_id" in result
    assert result["tool_call_id"] == "call_abc123"
    assert "content" in result
    assert isinstance(result["content"], dict)
