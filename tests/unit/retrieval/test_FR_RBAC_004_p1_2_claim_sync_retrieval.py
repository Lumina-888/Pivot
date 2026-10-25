"""S5: pre-sync lag vs leak for FR-RBAC-004 (ADR-017 D3).

After a claim (library unassigned -> dept_eng) and before the worker
reconcile runs, the document's nodes still sit in the unassigned
collection. Retrieval must lag, never leak: the target department's
members cannot retrieve it yet (their selection excludes unassigned),
and neither can anyone else. After reconcile moves the nodes into the
dept_eng collection, target members retrieve it and other departments
still cannot. The stale node is proven present pre-sync by a
super-admin-shaped retriever that sees every library.
"""

from __future__ import annotations

import pytest
from pivot.retrieval.fakes import HashingQueryEmbedder

CHUNK_CLAIMED = "项目认领流程需要部门管理员确认。"
CHUNK_PUB = "一个月内累计迟到三次，视为旷工一天。"
QUESTION_CLAIMED = "认领流程"
QUESTION_PUB = "迟到"

# Live row after the claim: the document belongs to dept_eng now.
LIVE_LIBRARY = {"doc-claimed": "dept_eng", "doc-pub": "pub"}


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


def _retriever(indexes, visible):
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
    from pivot.retrieval.policy import RetrievalPolicy
    from pivot.retrieval.tokenize import SimpleLexTokenizer

    def authorize(principal_id, document_id, version_id):
        # Live-row semantics: the hook judges by the document's current
        # library, never by the collection the node came from.
        return LIVE_LIBRARY.get(document_id) in visible

    return LlamaIndexRetriever(
        indexes=indexes,
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=-1.0,
        authorize=authorize,
        visible_libraries_for=lambda principal_id: visible,
        exception_documents_for=lambda principal_id: (),
    )


def _args():
    return {"scope_type": "global", "scope_document_id": None, "principal_id": "usr_x"}


def test_FR_RBAC_004_claim_sync_lags_without_leaking() -> None:
    client = _client()
    holders = _open_set(
        client,
        [
            _payload("chunk-c1", "ver-c1", "doc-claimed", CHUNK_CLAIMED, "unassigned"),
            _payload("chunk-p1", "ver-p1", "doc-pub", CHUNK_PUB, "pub"),
        ],
    )
    eng = _retriever(holders.indexes, ("pub", "dept_eng"))
    art = _retriever(holders.indexes, ("pub", "dept_art"))
    admin = _retriever(
        holders.indexes, ("pub", "dept_eng", "dept_art", "unassigned")
    )

    # Pre-sync the stale node is really there (super-admin shape sees
    # it), but neither department retrieves it: lag, not leak.
    found = [h.chunk_id for h in admin.retrieve(QUESTION_CLAIMED, **_args()).evidence]
    assert "chunk-c1" in found
    found = [h.chunk_id for h in eng.retrieve(QUESTION_CLAIMED, **_args()).evidence]
    assert "chunk-c1" not in found
    found = [h.chunk_id for h in art.retrieve(QUESTION_CLAIMED, **_args()).evidence]
    assert "chunk-c1" not in found
    # The public control still serves throughout.
    found = [h.chunk_id for h in eng.retrieve(QUESTION_PUB, **_args()).evidence]
    assert "chunk-p1" in found

    # Post-sync: reconcile moves the nodes into the dept_eng collection
    # and sweeps the other collections.
    holders.reconcile_document(
        "doc-claimed",
        library_id="dept_eng",
        current_payloads=[
            _payload("chunk-c1", "ver-c1", "doc-claimed", CHUNK_CLAIMED, "dept_eng")
        ],
        external_llm_allowed=lambda version_id: True,
    )
    found = [h.chunk_id for h in eng.retrieve(QUESTION_CLAIMED, **_args()).evidence]
    assert "chunk-c1" in found
    found = [h.chunk_id for h in art.retrieve(QUESTION_CLAIMED, **_args()).evidence]
    assert "chunk-c1" not in found
