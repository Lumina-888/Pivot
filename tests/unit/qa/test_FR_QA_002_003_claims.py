from __future__ import annotations

from fakes import empty_retriever, ok_retriever
from pivot.qa.draft import draft_from_evidence
from pivot.qa.orchestrator import QaOrchestrator
from pivot.qa.ports import EvidenceHit
from pivot.qa.verifier import CandidateVerifier
from pivot.runs.service import RunService


def test_FR_QA_002_claims_require_in_candidate_citations():
    verifier = CandidateVerifier()
    hit = EvidenceHit("chk_a", "doc_a", "ver_a", "迟到三次以上记为旷工")
    _, claims, citations = draft_from_evidence((hit,))
    citations[0]["chunk_id"] = "chk_outside"
    assert verifier.verify(claims, citations, (hit,)) == "refused"
    _, claims, citations = draft_from_evidence((hit,))
    assert verifier.verify(claims, citations, (hit,)) == "answered"


def test_FR_QA_002_draft_citations_stay_in_evidence_set():
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_1",
        request_id="req_1",
        scope_type="document",
        scope_document_id="doc_a",
    )
    retriever = ok_retriever()
    QaOrchestrator(retriever).execute(bundle, runs.log(bundle.run.id), "req_1")
    assert retriever.calls[0]["scope_document_id"] == "doc_a"
    assert all(citation["document_id"] == "doc_a" for citation in bundle.citations)


def test_FR_QA_003_no_evidence_refuses_without_ungrounded_answer():
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="董事会秘密",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    QaOrchestrator(empty_retriever()).execute(bundle, runs.log(bundle.run.id), "req_1")
    assert bundle.run.state == "refused"
    assert bundle.run.answer_markdown is None
    assert runs.log(bundle.run.id).terminal == "refused"
