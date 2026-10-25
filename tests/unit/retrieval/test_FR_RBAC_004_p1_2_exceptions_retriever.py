"""S3: retriever selection and node filtering for exceptions (ADR-017 D1).

The retriever's per-node authorize hook is the enforcement that keeps
ungranted nodes out of the scoring corpus. Selection widens to every
library-keyed index when the caller has live exception documents (the
retriever cannot map document ids to libraries), but a node from a
non-visible library still only reaches the corpus when the hook passes
it: same library, granted document in, ungranted document out.
"""

from __future__ import annotations

import pytest
from pivot.retrieval.fakes import HashingQueryEmbedder

CHUNK_PUB = "一个月内累计迟到三次，视为旷工一天。"
CHUNK_GRANTED = "员工出差需要提前三天提交出差申请单。"
CHUNK_UNGRANTED = "出差申请单需要部门负责人签字。"
QUESTION_DEPT = "出差申请单"

DOC_LIBRARY = {
    "doc-pub": "pub",
    "doc-dept-a": "dept_eng",
    "doc-dept-b": "dept_eng",
}


def _payload(chunk_id, version_id, document_id, text, library_id):
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "version_id": version_id,
        "text": text,
        "title": "制度",
        "space": "shared",
        "tags": [],
        "ready": True,
        "current": True,
        "allowed": True,
        "expired": False,
        "deleted": False,
        "index_generation": "gen-1",
        "embedding_model_version": "hash-embed-test",
        "retrieval_config_version": "cfg-1",
        "locator": "第一条",
        "library_id": library_id,
    }


def _client():
    pytest.importorskip("llama_index.core")
    qdrant_client = pytest.importorskip("qdrant_client")
    return qdrant_client.QdrantClient(location=":memory:")


def _embed():
    from pivot.retrieval.llama_embeddings import PivotEmbedding

    return PivotEmbedding(
        HashingQueryEmbedder(4), model_name="hash-embedding", dimension=4
    )


def _open_set(client, payloads):
    from pivot.retrieval.llama_qdrant_index import LlamaLibraryIndexSet

    return LlamaLibraryIndexSet.open(
        client=client,
        native_collection="pivot-chunks",
        embed_model=_embed(),
        vector_size=4,
        distance="Cosine",
        native_payloads=payloads,
        external_llm_allowed=lambda version_id: True,
    )


def _retriever(indexes, visible, exceptions, authorize=None):
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
    from pivot.retrieval.policy import RetrievalPolicy
    from pivot.retrieval.tokenize import SimpleLexTokenizer

    if authorize is None:
        def authorize(principal_id, document_id, version_id):
            library = DOC_LIBRARY.get(document_id)
            return library in visible or document_id in exceptions

    return LlamaIndexRetriever(
        indexes=indexes,
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=-1.0,
        authorize=authorize,
        visible_libraries_for=lambda principal_id: visible,
        exception_documents_for=lambda principal_id: exceptions,
    )


def _payloads():
    return [
        _payload("chunk-p1", "ver-p1", "doc-pub", CHUNK_PUB, "pub"),
        _payload("chunk-d1", "ver-d1", "doc-dept-a", CHUNK_GRANTED, "dept_eng"),
        _payload("chunk-d2", "ver-d2", "doc-dept-b", CHUNK_UNGRANTED, "dept_eng"),
    ]


def _args():
    return {"scope_type": "global", "scope_document_id": None, "principal_id": "usr_dave"}


def test_FR_RBAC_004_exception_retriever_serves_granted_not_ungranted() -> None:
    client = _client()
    holders = _open_set(client, _payloads())
    retriever = _retriever(
        holders.indexes, ("pub",), ("doc-dept-a",),
    )
    found = [h.chunk_id for h in retriever.retrieve(QUESTION_DEPT, **_args()).evidence]
    assert "chunk-d1" in found
    # Same library, ungranted document: never in the corpus, never out.
    assert "chunk-d2" not in found
    assert retriever.resolve_evidence("chunk-d1", **_args()) is not None
    assert retriever.resolve_evidence("chunk-d2", **_args()) is None


def test_FR_RBAC_004_exception_retriever_selection_widens_only_with_grants() -> None:
    client = _client()
    holders = _open_set(client, _payloads())
    with_grant = _retriever(holders.indexes, ("pub",), ("doc-dept-a",))
    assert set(with_grant._selected_indexes("usr_dave")) == {"pub", "dept_eng"}
    without_grant = _retriever(holders.indexes, ("pub",), ())
    assert set(without_grant._selected_indexes("usr_dave")) == {"pub"}
    found = [
        h.chunk_id
        for h in without_grant.retrieve(QUESTION_DEPT, **_args()).evidence
    ]
    assert "chunk-d1" not in found
    assert "chunk-d2" not in found


def test_FR_RBAC_004_exception_resolver_failure_keeps_library_access() -> None:
    client = _client()
    holders = _open_set(client, _payloads())

    def _boom(principal_id):
        raise RuntimeError("exception store down")

    retriever = _retriever(holders.indexes, ("pub",), ("doc-dept-a",))
    retriever._exception_documents_for = _boom
    assert set(retriever._selected_indexes("usr_dave")) == {"pub"}
    found = [
        h.chunk_id
        for h in retriever.retrieve("迟到三次怎么处理？", **_args()).evidence
    ]
    assert "chunk-p1" in found
    assert "chunk-d1" not in found
