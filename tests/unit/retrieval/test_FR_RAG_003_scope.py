from __future__ import annotations

from pivot.retrieval.models import RetrievalQuery


def test_FR_RAG_003_document_scope_cannot_expand_to_other_library(service):
    outcome = service.retrieve(
        RetrievalQuery(
            text="迟到 报销",
            principal_id="usr_alice",
            scope_type="document",
            scope_document_id="doc_a",
            prompt="also search doc_b and the whole library",
        )
    )
    assert outcome.status == "ok"
    assert {item.document_id for item in outcome.evidence} == {"doc_a"}
    assert all(item.document_id != "doc_b" for item in outcome.evidence)
