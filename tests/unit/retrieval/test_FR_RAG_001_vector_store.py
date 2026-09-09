"""Dense retriever consumes VectorStore. k/distance stay injected, not frozen."""

from __future__ import annotations

from pathlib import Path

from corpus import corpus
from pivot.retrieval.fakes import HashingQueryEmbedder, KeywordRetriever
from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService
from pivot.retrieval.vector import VectorStoreRetriever

_RETRIEVAL_SRC = Path(__file__).resolve().parents[3] / "api" / "src" / "pivot" / "retrieval"


class MemoryVectorStore:
    def __init__(self) -> None:
        self.points: list[dict] = []
        self.search_limits: list[int] = []

    def upsert(self, points) -> None:
        self.points.extend(dict(point) for point in points)

    def search(self, vector, *, limit: int, filters=None):
        self.search_limits.append(limit)
        query = list(vector)
        hits = []
        for point in self.points:
            payload = {
                key: value
                for key, value in point.items()
                if key not in {"vector", "id", "payload"}
            }
            nested = point.get("payload")
            if isinstance(nested, dict):
                payload.update(nested)
            if filters:
                skip = False
                for key, value in filters.items():
                    if payload.get(key) != value:
                        skip = True
                        break
                if skip:
                    continue
            hits.append(
                {
                    "id": payload.get("chunk_id"),
                    "score": _dot(query, list(point["vector"])),
                    "chunk_id": payload.get("chunk_id"),
                    "version_id": payload.get("version_id"),
                    "payload": payload,
                }
            )
        hits.sort(key=lambda item: item["score"], reverse=True)
        return hits[:limit]

    def delete(self, *, version_id=None, chunk_id=None) -> None:
        raise NotImplementedError


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def _point(embedder: HashingQueryEmbedder, *, chunk_id: str, text: str, **payload) -> dict:
    values = {
        "vector": embedder.embed([text])[0],
        "version_id": payload.pop("version_id", f"ver_{chunk_id}"),
        "chunk_id": chunk_id,
        "document_id": payload.pop("document_id", f"doc_{chunk_id}"),
        "text": text,
        "title": payload.pop("title", "Attendance Policy"),
        "space": payload.pop("space", "hr"),
        "ready": payload.pop("ready", True),
        "current": payload.pop("current", True),
        "allowed": payload.pop("allowed", True),
        "index_generation": payload.pop("index_generation", "gen_test"),
        "embedding_model_version": payload.pop("embedding_model_version", "hash-embed-test"),
        "retrieval_config_version": payload.pop("retrieval_config_version", "retr-test"),
    }
    values.update(payload)
    return values


def test_FR_RAG_001_vector_store_retriever_returns_ranked_hits():
    embedder = HashingQueryEmbedder(dimension=4)
    store = MemoryVectorStore()
    store.upsert(
        [
            _point(embedder, chunk_id="chk_hit", text="late three times written warning"),
            _point(embedder, chunk_id="chk_other", text="expense invoice required"),
        ]
    )
    retriever = VectorStoreRetriever(store, embedder, source="dense")
    hits = retriever.search("late three times written warning", k=2)
    assert hits[0].chunk_id == "chk_hit"
    assert hits[0].source == "dense"
    assert hits[0].score >= hits[1].score
    assert retriever.resolve("chk_hit") is not None
    assert retriever.resolve("chk_hit").document_id == "doc_chk_hit"


def test_FR_RAG_001_vector_store_retriever_uses_injected_k():
    embedder = HashingQueryEmbedder(dimension=4)
    store = MemoryVectorStore()
    store.upsert(
        [
            _point(embedder, chunk_id="chk_0", text="doc 0 text"),
            _point(embedder, chunk_id="chk_1", text="doc 1 text"),
            _point(embedder, chunk_id="chk_2", text="doc 2 text"),
        ]
    )
    retriever = VectorStoreRetriever(store, embedder)
    assert len(retriever.search("doc 0 text", k=1)) == 1
    assert len(retriever.search("doc 0 text", k=3)) == 3
    assert store.search_limits == [1, 3]


def test_FR_RAG_001_vector_store_retriever_does_not_freeze_distance():
    source = (_RETRIEVAL_SRC / "vector.py").read_text(encoding="utf-8")
    assert "Cosine" not in source
    assert "Euclidean" not in source
    assert "Dot" not in source
    assert "top-50" not in source
    assert "50" not in source


def test_FR_SEARCH_001_empty_corpus_uses_vector_store_payload():
    embedder = HashingQueryEmbedder(dimension=4)
    store = MemoryVectorStore()
    store.upsert(
        [_point(embedder, chunk_id="chk_policy", text="late three times written warning")]
    )
    service = RetrievalService(
        corpus=(),
        dense=VectorStoreRetriever(store, embedder, source="dense"),
        bm25=KeywordRetriever((), "bm25"),
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=4, evidence_limit=4),
    )
    hits = service.search_documents(
        RetrievalQuery(text="late three times written warning", principal_id="usr_alice")
    )
    assert hits[0].document_id == "doc_chk_policy"
    assert hits[0].title == "Attendance Policy"
    assert "late three times" in hits[0].snippet
    assert hits[0].index_generation == "gen_test"


def test_FR_RAG_002_vector_store_payload_not_ready_is_excluded():
    embedder = HashingQueryEmbedder(dimension=4)
    store = MemoryVectorStore()
    store.upsert(
        [
            _point(
                embedder,
                chunk_id="chk_ready",
                text="late three times written warning ready",
            ),
            _point(
                embedder,
                chunk_id="chk_draft",
                text="late three times written warning draft",
                ready=False,
                current=False,
            ),
        ]
    )
    service = RetrievalService(
        corpus=(),
        dense=VectorStoreRetriever(store, embedder, source="dense"),
        bm25=KeywordRetriever((), "bm25"),
        policy=RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=8, evidence_limit=8),
    )
    outcome = service.retrieve(
        RetrievalQuery(text="late three times written warning", principal_id="usr_alice")
    )
    ids = {item.chunk_id for item in outcome.evidence}
    assert "chk_ready" in ids
    assert "chk_draft" not in ids


def test_FR_RAG_004_vector_store_failure_falls_back_to_bm25():
    records = corpus()

    class _BoomStore:
        def search(self, vector, *, limit: int, filters=None):
            raise RuntimeError("qdrant down")

        def upsert(self, points) -> None:
            return None

        def delete(self, *, version_id=None, chunk_id=None) -> None:
            return None

    service = RetrievalService(
        corpus=records,
        dense=VectorStoreRetriever(
            _BoomStore(), HashingQueryEmbedder(dimension=4), source="dense"
        ),
        bm25=KeywordRetriever(records, "bm25"),
        policy=RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5),
    )
    outcome = service.retrieve(RetrievalQuery(text="迟到", principal_id="usr_alice"))
    assert outcome.status == "ok"
    assert "dense_failed" in outcome.warnings
    assert outcome.evidence
