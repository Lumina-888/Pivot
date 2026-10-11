"""
ND-AGENT-02-H 单元测试：Finalizer 集成

测试覆盖：
- StructuredFinalizer 答案生成
- 证据绑定
- 验证集成
"""

from __future__ import annotations

from pivot.qa.agent_finalizer import StructuredFinalizer
from pivot.qa.ports import EvidenceHit

# ====================
# Fake DraftWriter
# ====================


class FakeDraftWriter:
    def __init__(self, answer: str, claims: list[dict], citations: list[dict]) -> None:
        self.answer = answer
        self.claims = claims
        self.citations = citations

    def draft(self, question, hits):
        return self.answer, self.claims, self.citations


# ====================
# Fake Verifier
# ====================


class FakeVerifier:
    def __init__(self, result: str = "pass") -> None:
        self.result = result

    def verify(self, claims, citations, evidence):
        return self.result


# ====================
# StructuredFinalizer 测试
# ====================


def test_finalizer_generates_structured_answer():
    """
    Given: 有可用证据
    When: 调用 finalize
    Then: 应该生成结构化答案
    """
    writer = FakeDraftWriter(
        answer="根据考勤规定，迟到三次记为旷工。",
        claims=[
            {"index": 0, "text": "迟到三次记为旷工"},
        ],
        citations=[
            {"claim_index": 0, "evidence_index": 0},
        ],
    )
    finalizer = StructuredFinalizer(writer)

    evidences = [
        {
            "evidence_id": "ev_1",
            "chunk_id": "chk_1",
            "document_id": "doc_1",
            "version_id": "ver_1",
            "text": "迟到三次以上记为旷工",
            "locator": "page=1",
        }
    ]

    result = finalizer.finalize("考勤规定是什么？", evidences)

    assert result["status"] == "completed"
    assert "迟到三次" in result["answer"]
    assert len(result["claims"]) == 1
    assert result["claims"][0]["text"] == "迟到三次记为旷工"
    assert result["claims"][0]["evidence_ids"] == ["ev_1"]


def test_finalizer_handles_no_evidence():
    """
    Given: 没有证据
    When: 调用 finalize
    Then: 应该返回 insufficient_evidence
    """
    writer = FakeDraftWriter("", [], [])
    finalizer = StructuredFinalizer(writer)

    result = finalizer.finalize("不存在的问题", [])

    assert result["status"] == "insufficient_evidence"
    assert "未找到相关证据" in result["answer"]
    assert result["claims"] == []


def test_finalizer_binds_evidence_to_claims():
    """
    Given: 多个证据和多个声明
    When: 生成答案
    Then: 应该正确绑定证据到声明
    """
    writer = FakeDraftWriter(
        answer="考勤规定：迟到三次记为旷工，旷工扣除工资。",
        claims=[
            {"index": 0, "text": "迟到三次记为旷工"},
            {"index": 1, "text": "旷工扣除工资"},
        ],
        citations=[
            {"claim_index": 0, "evidence_index": 0},
            {"claim_index": 1, "evidence_index": 1},
        ],
    )
    finalizer = StructuredFinalizer(writer)

    evidences = [
        {
            "evidence_id": "ev_1",
            "chunk_id": "chk_1",
            "document_id": "doc_1",
            "version_id": "ver_1",
            "text": "迟到三次以上记为旷工",
        },
        {
            "evidence_id": "ev_2",
            "chunk_id": "chk_2",
            "document_id": "doc_1",
            "version_id": "ver_1",
            "text": "旷工扣除当日工资",
        },
    ]

    result = finalizer.finalize("考勤规定", evidences)

    assert result["status"] == "completed"
    assert len(result["claims"]) == 2
    assert result["claims"][0]["evidence_ids"] == ["ev_1"]
    assert result["claims"][1]["evidence_ids"] == ["ev_2"]


def test_finalizer_with_verifier_pass():
    """
    Given: Verifier 验证通过
    When: 生成答案
    Then: 应该返回完整答案
    """
    writer = FakeDraftWriter(
        answer="答案内容",
        claims=[{"index": 0, "text": "声明"}],
        citations=[{"claim_index": 0, "evidence_index": 0}],
    )
    verifier = FakeVerifier(result="pass")
    finalizer = StructuredFinalizer(writer, verifier)

    evidences = [
        {
            "evidence_id": "ev_1",
            "chunk_id": "chk_1",
            "document_id": "doc_1",
            "version_id": "ver_1",
            "text": "证据内容",
        }
    ]

    result = finalizer.finalize("问题", evidences)

    assert result["status"] == "completed"
    assert result["answer"] == "答案内容"


def test_finalizer_with_verifier_fail():
    """
    Given: Verifier 验证失败
    When: 生成答案
    Then: 应该返回保守答案
    """
    writer = FakeDraftWriter(
        answer="可能不可靠的答案",
        claims=[{"index": 0, "text": "声明"}],
        citations=[{"claim_index": 0, "evidence_index": 0}],
    )
    verifier = FakeVerifier(result="fail")
    finalizer = StructuredFinalizer(writer, verifier)

    evidences = [
        {
            "evidence_id": "ev_1",
            "chunk_id": "chk_1",
            "document_id": "doc_1",
            "version_id": "ver_1",
            "text": "证据内容",
        }
    ]

    result = finalizer.finalize("问题", evidences)

    assert result["status"] == "verification_failed"
    assert "无法生成可靠的答案" in result["answer"]
    assert result["claims"] == []


def test_finalizer_handles_multiple_citations_per_claim():
    """
    Given: 一个声明引用多个证据
    When: 生成答案
    Then: 应该包含所有引用的 evidence_ids
    """
    writer = FakeDraftWriter(
        answer="综合考勤规定",
        claims=[
            {"index": 0, "text": "考勤综合规定"},
        ],
        citations=[
            {"claim_index": 0, "evidence_index": 0},
            {"claim_index": 0, "evidence_index": 1},
        ],
    )
    finalizer = StructuredFinalizer(writer)

    evidences = [
        {
            "evidence_id": "ev_1",
            "chunk_id": "chk_1",
            "document_id": "doc_1",
            "version_id": "ver_1",
            "text": "规定1",
        },
        {
            "evidence_id": "ev_2",
            "chunk_id": "chk_2",
            "document_id": "doc_1",
            "version_id": "ver_1",
            "text": "规定2",
        },
    ]

    result = finalizer.finalize("问题", evidences)

    assert result["status"] == "completed"
    assert len(result["claims"]) == 1
    assert set(result["claims"][0]["evidence_ids"]) == {"ev_1", "ev_2"}


def test_finalizer_handles_invalid_evidence_index():
    """
    Given: citation 包含无效的 evidence_index
    When: 生成答案
    Then: 应该跳过无效引用
    """
    writer = FakeDraftWriter(
        answer="答案",
        claims=[
            {"index": 0, "text": "声明"},
        ],
        citations=[
            {"claim_index": 0, "evidence_index": 0},
            {"claim_index": 0, "evidence_index": 99},  # 无效索引
        ],
    )
    finalizer = StructuredFinalizer(writer)

    evidences = [
        {
            "evidence_id": "ev_1",
            "chunk_id": "chk_1",
            "document_id": "doc_1",
            "version_id": "ver_1",
            "text": "证据",
        }
    ]

    result = finalizer.finalize("问题", evidences)

    assert result["status"] == "completed"
    assert result["claims"][0]["evidence_ids"] == ["ev_1"]  # 只包含有效的


def test_finalizer_converts_evidence_format():
    """
    Given: dict 格式的证据
    When: 调用 draft_writer
    Then: 应该转换为 EvidenceHit 格式
    """
    calls = []

    class RecordingWriter:
        def draft(self, question, hits):
            calls.append(hits)
            return "答案", [], []

    finalizer = StructuredFinalizer(RecordingWriter())

    evidences = [
        {
            "evidence_id": "ev_1",
            "chunk_id": "chk_1",
            "document_id": "doc_1",
            "version_id": "ver_1",
            "text": "证据文本",
            "locator": "page=5",
            "external_llm_allowed": True,
        }
    ]

    finalizer.finalize("问题", evidences)

    assert len(calls) == 1
    hits = calls[0]
    assert len(hits) == 1
    assert isinstance(hits[0], EvidenceHit)
    assert hits[0].chunk_id == "chk_1"
    assert hits[0].document_id == "doc_1"
    assert hits[0].text == "证据文本"
    assert hits[0].external_llm_allowed is True
