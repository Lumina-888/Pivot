"""Library filtering for FR-RBAC-004 (ADR-016 D4).

A chunk is retrievable only when its library belongs to the query's
library set. A query without a library set keeps the legacy behavior
(no library constraint); an explicit empty set matches nothing. Chunks
that carry no library at all are fail-closed under a constrained query.
"""

from __future__ import annotations

from pivot.retrieval.fakes import KeywordRetriever, OverlapReranker
from pivot.retrieval.filters import passes_filters
from pivot.retrieval.models import ChunkRecord, RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService


def _chunk(chunk_id: str, document_id: str, text: str, library_id: str) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        version_id="ver_1",
        document_id=document_id,
        text=text,
        title=document_id,
        library_id=library_id,
    )


def _query(library_ids, text: str = "手册") -> RetrievalQuery:
    return RetrievalQuery(
        text=text, principal_id="usr_alice", library_ids=library_ids
    )


def _service() -> RetrievalService:
    records = (
        _chunk("chk_pub", "doc_pub", "手册 公共 规则", "pub"),
        _chunk("chk_eng", "doc_eng", "手册 技术 规则", "dept_eng"),
        _chunk("chk_art", "doc_art", "手册 美术 规则", "dept_art"),
    )
    return RetrievalService(
        corpus=records,
        dense=KeywordRetriever(records, "dense"),
        bm25=KeywordRetriever(records, "bm25"),
        policy=RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5),
        reranker=OverlapReranker(),
    )


def test_FR_RBAC_004_library_filter_passes_visible_library():
    chunk = _chunk("chk_1", "doc_eng", "手册", "dept_eng")
    assert passes_filters(chunk, _query(("pub", "dept_eng"))) is True


def test_FR_RBAC_004_library_filter_blocks_other_library():
    chunk = _chunk("chk_1", "doc_art", "手册", "dept_art")
    assert passes_filters(chunk, _query(("pub", "dept_eng"))) is False


def test_FR_RBAC_004_library_filter_unset_means_no_constraint():
    chunk = _chunk("chk_1", "doc_art", "手册", "dept_art")
    assert passes_filters(chunk, _query(None)) is True


def test_FR_RBAC_004_library_filter_empty_set_matches_nothing():
    chunk = _chunk("chk_1", "doc_pub", "手册", "pub")
    assert passes_filters(chunk, _query(())) is False


def test_FR_RBAC_004_library_filter_unclassified_chunk_is_fail_closed():
    chunk = _chunk("chk_1", "doc_old", "手册", "")
    assert passes_filters(chunk, _query(("pub", "dept_eng"))) is False


def test_FR_RBAC_004_library_filter_stacks_with_document_scope():
    chunk = _chunk("chk_1", "doc_eng", "手册", "dept_eng")
    scoped = RetrievalQuery(
        text="手册",
        principal_id="usr_alice",
        scope_type="document",
        scope_document_id="doc_eng",
        library_ids=("pub", "dept_eng"),
    )
    assert passes_filters(chunk, scoped) is True
    wrong_library = RetrievalQuery(
        text="手册",
        principal_id="usr_alice",
        scope_type="document",
        scope_document_id="doc_eng",
        library_ids=("pub",),
    )
    assert passes_filters(chunk, wrong_library) is False


def test_FR_RBAC_004_search_hides_unauthorized_documents():
    service = _service()
    hits = service.search_documents(_query(("pub", "dept_eng")))
    ids = {hit.document_id for hit in hits}
    assert ids == {"doc_pub", "doc_eng"}


def test_FR_RBAC_004_search_only_unauthorized_match_is_empty_without_leak():
    service = _service()
    hits = service.search_documents(_query(("pub",), text="美术"))
    assert hits == ()


def test_FR_RBAC_004_retrieve_hides_unauthorized_documents():
    service = _service()
    outcome = service.retrieve(_query(("pub", "dept_eng")))
    ids = {item.document_id for item in outcome.evidence}
    assert ids == {"doc_pub", "doc_eng"}
    assert outcome.status == "ok"


def test_FR_RBAC_004_retrieve_only_unauthorized_match_is_empty():
    service = _service()
    outcome = service.retrieve(_query(("pub",), text="美术"))
    assert outcome.status == "empty"
    assert outcome.evidence == ()
