from __future__ import annotations

from pivot.retrieval.models import RetrievalQuery


def test_FR_SEARCH_002_ask_from_search_keeps_question_and_document_scope(service):
    hits = service.search_documents(
        RetrievalQuery(text="报销", principal_id="usr_alice")
    )
    intent = service.ask_from_search("差旅怎么报销", hits[0])
    assert intent.question == "差旅怎么报销"
    assert intent.scope_type == "document"
    assert intent.scope_document_id == "doc_b"
    assert intent.scope_type != "global"
