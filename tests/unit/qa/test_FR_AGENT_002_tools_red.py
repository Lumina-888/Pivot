"""
ND-AGENT-02-D Red 用例：只读工具与 EvidenceRegistry

测试策略：先写失败的测试，明确预期行为，等待 02-A/B/C 签认后实现。
当前状态：RED - 这些测试应该失败，因为 LangGraph 工具尚未实现。

测试覆盖：
- FR-AGENT-002: 白名单只读工具
- FR-RAG-003: 工具 scope 不可扩展
- 工具参数严格验证
- EvidenceRegistry 证据追踪
"""

from __future__ import annotations

import pytest

# ====================
# RED: 工具白名单测试
# ====================


def test_FR_AGENT_002_only_whitelisted_tools_allowed():
    """
    Given: Agent 尝试调用未在白名单中的工具
    When: 工具执行器处理调用
    Then: 应该拒绝并返回明确错误，不执行任意工具

    当前状态: RED - 工具注册系统尚未实现
    """
    # TODO: 实现工具白名单检查
    # tool_call = {"id": "call_1", "name": "execute_shell", "args": {"command": "ls"}}
    # with pytest.raises(UnknownToolError):
    #     tool_executor.execute(tool_call, run_context)
    pytest.skip("等待 02-A Contract 签认和工具系统实现")


def test_FR_AGENT_002_search_knowledge_strict_parameters():
    """
    Given: search_knowledge 工具调用包含额外参数
    When: 参数验证
    Then: 应该拒绝额外参数，不执行搜索

    当前状态: RED - 严格参数验证尚未实现
    """
    # TODO: 实现严格参数验证
    # tool_call = {
    #     "id": "call_1",
    #     "name": "search_knowledge",
    #     "args": {"query": "考勤", "extra_field": "should_fail"}
    # }
    # with pytest.raises(ExtraParametersError):
    #     tool_executor.execute(tool_call, run_context)
    pytest.skip("等待 02-A Contract 签认")


def test_FR_AGENT_002_read_evidence_requires_valid_id():
    """
    Given: read_evidence 调用使用空字符串或无效 evidence_id
    When: 参数验证
    Then: 应该拒绝空白或格式错误的 ID

    当前状态: RED - EvidenceRegistry 尚未实现
    """
    # TODO: 实现 evidence_id 验证
    # invalid_ids = ["", "  ", None, "invalid@format"]
    # for invalid_id in invalid_ids:
    #     tool_call = {
    #         "id": "call_1",
    #         "name": "read_evidence",
    #         "args": {"evidence_id": invalid_id}
    #     }
    #     with pytest.raises(InvalidParameterError):
    #         tool_executor.execute(tool_call, run_context)
    pytest.skip("等待 02-A Contract 签认")


# ====================
# RED: EvidenceRegistry 测试
# ====================


def test_FR_AGENT_002_evidence_registry_tracks_search_origin():
    """
    Given: search_knowledge 返回证据候选
    When: 记录到 EvidenceRegistry
    Then: 应该包含完整的来源追踪信息：
         - document_id, version_id, chunk_id
         - 检索代次、Embedding 版本
         - 工具调用 ID 和授权时点

    当前状态: RED - EvidenceRegistry 尚未实现
    """
    # TODO: 实现 EvidenceRegistry
    # registry = EvidenceRegistry()
    # search_result = perform_search("考勤", run_context)
    # evidence_id = registry.register(search_result, tool_call_id="call_1")
    #
    # entry = registry.get(evidence_id)
    # assert entry.document_id is not None
    # assert entry.version_id is not None
    # assert entry.chunk_id is not None
    # assert entry.retrieval_generation is not None
    # assert entry.embedding_version is not None
    # assert entry.tool_call_id == "call_1"
    # assert entry.authorized_at is not None
    pytest.skip("等待 02-A Contract 签认")


def test_FR_AGENT_002_foreign_run_evidence_rejected():
    """
    Given: 模型尝试使用另一个 Run 的 evidence_id
    When: read_evidence 执行
    Then: 应该拒绝并且不泄露文档存在性

    当前状态: RED - Run 隔离尚未实现
    """
    # TODO: 实现 Run 隔离检查
    # other_run_evidence_id = "evidence_from_run_xyz"
    # tool_call = {
    #     "id": "call_1",
    #     "name": "read_evidence",
    #     "args": {"evidence_id": other_run_evidence_id}
    # }
    # with pytest.raises(EvidenceNotFoundError):  # 不泄露是否存在
    #     tool_executor.execute(tool_call, current_run_context)
    pytest.skip("等待 02-A Contract 签认")


def test_FR_AGENT_002_evidence_reauthorization_on_read():
    """
    Given: 文档在搜索后被删除或权限改变
    When: read_evidence 尝试读取
    Then: 应该重新检查授权，拒绝已删除/无权限的证据

    当前状态: RED - 动态授权检查尚未实现
    """
    # TODO: 实现读取时重新授权
    # 1. 搜索时文档可访问
    # search_result = perform_search("考勤", run_context)
    # evidence_id = registry.register(search_result, "call_1")
    #
    # 2. 模拟文档被删除
    # document_service.delete(search_result.document_id)
    #
    # 3. 尝试读取应该失败
    # tool_call = {
    #     "id": "call_2",
    #     "name": "read_evidence",
    #     "args": {"evidence_id": evidence_id}
    # }
    # with pytest.raises(DocumentNoLongerAvailableError):
    #     tool_executor.execute(tool_call, run_context)
    pytest.skip("等待 02-A Contract 签认")


# ====================
# RED: Scope 和安全测试
# ====================


def test_FR_RAG_003_tool_scope_cannot_expand():
    """
    Given: 用户只有 scope=['dept_a'] 的访问权限
    When: 工具执行时服务端注入 scope
    Then: 搜索结果必须限制在 dept_a，模型无法扩展到其他部门

    当前状态: RED - Scope 注入和过滤尚未实现
    """
    # TODO: 实现 scope 控制
    # restricted_context = RunContext(
    #     principal_id="user_1",
    #     scope=["dept_a"],
    #     ...
    # )
    #
    # tool_call = {
    #     "id": "call_1",
    #     "name": "search_knowledge",
    #     "args": {"query": "salary"}  # 模型无法指定 scope
    # }
    #
    # result = tool_executor.execute(tool_call, restricted_context)
    # # 验证结果中所有文档都属于 dept_a
    # for evidence in result.evidences:
    #     assert evidence.document_scope == "dept_a"
    pytest.skip("等待 02-A Contract 签认和 02-E 可信上下文实现")


def test_FR_AGENT_003_model_cannot_forge_principal():
    """
    Given: 模型尝试在工具参数中伪造 principal_id
    When: 工具执行器处理
    Then: 应该忽略模型提供的身份，只使用服务端注入的可信身份

    当前状态: RED - 可信上下文注入尚未实现
    """
    # TODO: 实现可信上下文
    # tool_call = {
    #     "id": "call_1",
    #     "name": "search_knowledge",
    #     "args": {
    #         "query": "考勤",
    #         "principal_id": "admin_user"  # 模型尝试伪造
    #     }
    # }
    #
    # # 工具应该拒绝额外参数，或者忽略伪造的 principal
    # result = tool_executor.execute(tool_call, actual_user_context)
    # # 验证使用的是服务端注入的真实身份，不是模型提供的
    pytest.skip("等待 02-E 可信上下文实现")


# ====================
# RED: 版本和去重测试
# ====================


def test_FR_AGENT_002_evidence_deduplication_preserves_source():
    """
    Given: 同一个文档在多次搜索中出现
    When: 注册到 EvidenceRegistry
    Then: 应该去重但保留所有来源调用 ID

    当前状态: RED - 去重逻辑尚未实现
    """
    # TODO: 实现证据去重
    # registry = EvidenceRegistry()
    #
    # # 第一次搜索
    # result1 = perform_search("考勤规则", run_context)
    # evidence_id_1 = registry.register(result1, "call_1")
    #
    # # 第二次搜索返回相同文档
    # result2 = perform_search("迟到处理", run_context)
    # evidence_id_2 = registry.register(result2, "call_2")
    #
    # # 如果是同一文档/版本，应该返回相同 evidence_id
    # if result1.chunk_id == result2.chunk_id:
    #     assert evidence_id_1 == evidence_id_2
    #     entry = registry.get(evidence_id_1)
    #     assert "call_1" in entry.source_call_ids
    #     assert "call_2" in entry.source_call_ids
    pytest.skip("等待 02-A Contract 签认")


def test_FR_AGENT_002_version_conflict_metadata_preserved():
    """
    Given: 搜索返回同一文档的不同版本
    When: 注册证据
    Then: 不应该混合版本，应该保留版本冲突元数据

    当前状态: RED - 版本冲突处理尚未实现
    """
    # TODO: 实现版本冲突检测
    # result_v1 = SearchResult(document_id="doc_1", version_id="v1", ...)
    # result_v2 = SearchResult(document_id="doc_1", version_id="v2", ...)
    #
    # evidence_id_1 = registry.register(result_v1, "call_1")
    # evidence_id_2 = registry.register(result_v2, "call_2")
    #
    # # 不同版本应该是不同的证据
    # assert evidence_id_1 != evidence_id_2
    #
    # # 应该有版本冲突标记
    # conflict_info = registry.get_version_conflicts("doc_1")
    # assert len(conflict_info) == 2
    pytest.skip("等待 02-A Contract 签认")


# ====================
# RED: 观察限长测试
# ====================


def test_FR_AGENT_002_observation_length_limited():
    """
    Given: 搜索返回大量结果
    When: 构建 Observation
    Then: 应该限制摘要长度，不传输完整文档内容

    当前状态: RED - 观察限长尚未实现
    """
    # TODO: 实现观察限长
    # large_result = perform_search("制度", run_context)
    # observation = build_observation(large_result)
    #
    # # 验证观察长度在合理范围内（具体数值待 02-B 冻结）
    # assert len(observation.summary) < MAX_OBSERVATION_LENGTH
    # # 应该有截断标记
    # if large_result.total_chunks > MAX_CHUNKS_IN_OBSERVATION:
    #     assert observation.truncated is True
    pytest.skip("等待 02-B 预算 Contract 冻结观察限长策略")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
