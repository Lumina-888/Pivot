"""2026-11-03 local-real-deps defect 1: /search dense leg backfill.

The base collection payload is stamped at ingest and never rewritten
by claim/move reconcile (which only updates the per-library LlamaIndex
collections). VectorStoreRetriever must therefore backfill a hit's
library (and folder) from live document facts at build time, or
/search's passes_filters keeps matching the stale payload library and
target-library members see nothing after a claim or move.
"""

from __future__ import annotations

from pivot.retrieval.vector import VectorStoreRetriever


class _Store:
    def __init__(self, hits):
        self._hits = hits

    def search(self, vector, *, limit):
        return self._hits[:limit]


class _Embedder:
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _hit():
    return {
        "chunk_id": "chunk_1",
        "score": 0.9,
        "payload": {
            "chunk_id": "chunk_1",
            "version_id": "version_1",
            "document_id": "document_1",
            "text": "alpha beta",
            "title": "doc",
            "library_id": "dept_old",
        },
    }


def test_dense_backfill_replaces_stale_payload_library():
    retriever = VectorStoreRetriever(
        _Store([_hit()]),
        _Embedder(),
        library_id_for=lambda version_id: "dept_new",
    )
    hits = retriever.search("alpha", 5)
    assert len(hits) == 1
    record = retriever.resolve("chunk_1")
    assert record is not None
    assert record.library_id == "dept_new"


def test_dense_backfill_keeps_payload_when_version_unresolvable():
    retriever = VectorStoreRetriever(
        _Store([_hit()]),
        _Embedder(),
        library_id_for=lambda version_id: None,
    )
    retriever.search("alpha", 5)
    record = retriever.resolve("chunk_1")
    assert record is not None
    assert record.library_id == "dept_old"


def test_dense_backfill_keeps_payload_when_resolver_raises():
    def _boom(version_id):
        raise RuntimeError("facts unavailable")

    retriever = VectorStoreRetriever(
        _Store([_hit()]),
        _Embedder(),
        library_id_for=_boom,
    )
    retriever.search("alpha", 5)
    record = retriever.resolve("chunk_1")
    assert record is not None
    assert record.library_id == "dept_old"


def test_dense_backfill_applies_live_folder():
    retriever = VectorStoreRetriever(
        _Store([_hit()]),
        _Embedder(),
        library_id_for=lambda version_id: "dept_new",
        folder_id_for=lambda version_id: "folder_9",
    )
    retriever.search("alpha", 5)
    record = retriever.resolve("chunk_1")
    assert record is not None
    assert record.folder_id == "folder_9"
