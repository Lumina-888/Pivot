from __future__ import annotations

from pivot.retrieval.models import RetrievalQuery


def test_FR_SEARCH_001_results_only_ready_current_allowed(service):
    hits = service.search_documents(
        RetrievalQuery(text="迟到", principal_id="usr_alice")
    )
    ids = {hit.document_id for hit in hits}
    assert "doc_a" in ids
    assert "doc_nr" not in ids
    assert "doc_old" not in ids
    assert "doc_secret" not in ids
    assert all(hit.index_generation for hit in hits)


def test_FR_SEARCH_001_space_filter(service):
    hits = service.search_documents(
        RetrievalQuery(text="", principal_id="usr_alice", space="finance")
    )
    assert {hit.document_id for hit in hits} == {"doc_b"}
