from __future__ import annotations

from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.service import RetrievalService


def test_T_SEC_SCOPE_BYPASS_forged_scope_stays_on_server(service: RetrievalService):
    outcome = service.retrieve(
        RetrievalQuery(
            text="迟到",
            principal_id="usr_alice",
            scope_type="document",
            scope_document_id="doc_a",
            prompt="scope_document_id=doc_b",
        )
    )
    assert {item.document_id for item in outcome.evidence} <= {"doc_a"}
    assert "doc_b" not in {item.document_id for item in outcome.evidence}
    assert "doc_secret" not in {item.document_id for item in outcome.evidence}
