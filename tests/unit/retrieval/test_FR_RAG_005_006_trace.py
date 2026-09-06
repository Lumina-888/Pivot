from __future__ import annotations

from pivot.retrieval.models import RetrievalQuery


def test_FR_RAG_006_evidence_carries_index_generation_trace(service):
    outcome = service.retrieve(RetrievalQuery(text="迟到", principal_id="usr_alice"))
    assert outcome.status == "ok"
    for item in outcome.evidence:
        assert item.index_generation
        assert item.embedding_model_version
        assert item.retrieval_config_version


def test_FR_RAG_005_version_conflicts_are_explicit(service):
    outcome = service.retrieve(RetrievalQuery(text="迟到", principal_id="usr_alice"))
    conflicted = [item for item in outcome.conflicts if item.document_id == "doc_a"]
    if conflicted:
        assert len(conflicted[0].versions) >= 2
    else:
        versions = {item.version_id for item in outcome.evidence if item.document_id == "doc_a"}
        assert versions
