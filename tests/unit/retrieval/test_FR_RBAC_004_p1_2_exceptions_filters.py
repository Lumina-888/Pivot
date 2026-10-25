"""S3: search-scope exception rule for FR-RBAC-004 (ADR-017 D1).

passes_filters is the single scope rule shared by the corpus search
path and the retriever search path: a chunk passes when its library
is visible OR its document carries a live exception grant for the
caller. The search router derives both sets server-side from the
Principal, never from the request.
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pivot.auth.ports import Principal
from pivot.retrieval.filters import passes_filters
from pivot.retrieval.http import build_search_router
from pivot.retrieval.models import ChunkRecord, RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService


def _chunk(chunk_id, document_id, library_id, text):
    return ChunkRecord(
        chunk_id=chunk_id,
        version_id="ver-1",
        document_id=document_id,
        text=text,
        title="制度",
        library_id=library_id,
    )


def _query(library_ids, exception_ids):
    return RetrievalQuery(
        text="出差",
        principal_id="usr_dave",
        library_ids=library_ids,
        exception_document_ids=exception_ids,
    )


def test_FR_RBAC_004_search_filter_passes_exception_doc_only() -> None:
    granted = _chunk("c1", "doc-a", "dept_eng", "出差申请单。")
    ungranted = _chunk("c2", "doc-b", "dept_eng", "出差申请单。")
    visible = _chunk("c3", "doc-pub", "pub", "出差申请单。")
    query = _query(("pub",), ("doc-a",))
    assert passes_filters(granted, query) is True
    assert passes_filters(ungranted, query) is False
    assert passes_filters(visible, query) is True
    # No library constraint (QA path): the exception rule is not consulted.
    qa_query = RetrievalQuery(text="出差", principal_id="usr_dave")
    assert passes_filters(ungranted, qa_query) is True


def test_FR_RBAC_004_search_corpus_scoped_by_library_plus_exceptions() -> None:
    corpus = (
        _chunk("c1", "doc-a", "dept_eng", "出差申请单需要提前提交。"),
        _chunk("c2", "doc-b", "dept_eng", "出差申请单需要签字。"),
        _chunk("c3", "doc-pub", "pub", "出差申请单。"),
    )
    service = RetrievalService(
        corpus=corpus,
        dense=SimpleNamespace(search=lambda text, k: ()),
        bm25=SimpleNamespace(search=lambda text, k: ()),
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
    )
    hits = service.search_documents(_query(("pub",), ("doc-a",)))
    found = {hit.document_id for hit in hits}
    assert "doc-a" in found
    assert "doc-b" not in found
    assert "doc-pub" in found


def test_FR_RBAC_004_search_router_derives_exception_scope() -> None:
    corpus = (
        _chunk("c1", "doc-a", "dept_eng", "出差申请单需要提前提交。"),
        _chunk("c2", "doc-b", "dept_eng", "出差申请单需要签字。"),
    )
    service = RetrievalService(
        corpus=corpus,
        dense=SimpleNamespace(search=lambda text, k: ()),
        bm25=SimpleNamespace(search=lambda text, k: ()),
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
    )

    class _FakeAuth:
        def authenticate(self, token, request_id):
            return Principal(
                user_id="usr_dave", username="dave", role="user",
                token_version=1,
            )

        def visible_libraries(self, principal):
            return frozenset({"pub"})

        def exception_document_ids(self, principal):
            return frozenset({"doc-a"})

    app = FastAPI()
    app.include_router(build_search_router(service, _FakeAuth()))
    client = TestClient(app, base_url="https://testserver")
    response = client.get(
        "/search", params={"q": "出差"},
        headers={"Authorization": "Bearer token", "X-Request-ID": "req_search"},
    )
    assert response.status_code == 200
    found = {item["document_id"] for item in response.json()["items"]}
    assert "doc-a" in found
    assert "doc-b" not in found
