from __future__ import annotations

from corpus import corpus
from pivot.retrieval.fakes import FailingRetriever, KeywordRetriever, OverlapReranker
from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService


def _policy() -> RetrievalPolicy:
    return RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5)


def test_FR_RAG_004_dense_failure_falls_back_to_bm25():
    records = corpus()
    service = RetrievalService(
        corpus=records,
        dense=FailingRetriever(),
        bm25=KeywordRetriever(records, "bm25"),
        policy=_policy(),
        reranker=OverlapReranker(),
    )
    outcome = service.retrieve(RetrievalQuery(text="迟到", principal_id="usr_alice"))
    assert outcome.status == "ok"
    assert "dense_failed" in outcome.warnings
    assert any(
        call.provider == "dense" and call.status == "failed"
        for call in service.provider_calls
    )
    assert outcome.evidence


def test_FR_RAG_004_both_paths_failed_yields_no_ungrounded_answer():
    records = corpus()
    service = RetrievalService(
        corpus=records,
        dense=FailingRetriever(),
        bm25=FailingRetriever(),
        policy=_policy(),
    )
    outcome = service.retrieve(RetrievalQuery(text="迟到", principal_id="usr_alice"))
    assert outcome.status == "failed"
    assert outcome.evidence == ()
    assert outcome.error_code == "PROVIDER_TEMPORARY_ERROR"
