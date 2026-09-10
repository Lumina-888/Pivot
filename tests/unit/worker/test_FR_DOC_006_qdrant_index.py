"""Ingest IndexPublisher writes an injected VectorStore. Dimension stays injected."""

from __future__ import annotations

from pathlib import Path

from pivot.chunking import ChunkingPolicy, ChunkSplitter
from pivot.parsing.errors import ParseError
from pivot.retrieval.fakes import HashingQueryEmbedder
from pivot_worker.index import IndexPublisher
from pivot_worker.ingest import IngestRequest, IngestWorker, RecordingSink
from samples import pdf_with_text

_WORKER_SRC = Path(__file__).resolve().parents[3] / "worker" / "src" / "pivot_worker"


class MemoryVectorStore:
    def __init__(self) -> None:
        self.points: list[dict] = []
        self.upsert_calls = 0

    def upsert(self, points) -> None:
        self.upsert_calls += 1
        self.points.extend(dict(point) for point in points)

    def search(self, vector, *, limit: int, filters=None):
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
            hits.append(
                {
                    "chunk_id": payload.get("chunk_id"),
                    "version_id": payload.get("version_id"),
                    "score": sum(
                        a * b
                        for a, b in zip(query, list(point.get("vector") or ()), strict=False)
                    ),
                    "payload": payload,
                }
            )
        hits.sort(key=lambda item: item["score"], reverse=True)
        return hits[:limit]

    def delete(self, *, version_id=None, chunk_id=None) -> None:
        return None


class BoomVectorStore:
    def upsert(self, points) -> None:
        raise RuntimeError("qdrant down")

    def search(self, vector, *, limit: int, filters=None):
        raise RuntimeError("qdrant down")

    def delete(self, *, version_id=None, chunk_id=None) -> None:
        return None


def test_FR_DOC_006_index_publisher_upserts_injected_vector_store():
    store = MemoryVectorStore()
    publisher = IndexPublisher(store=store)
    publisher.start("gen_1", dimension=4, embedding_model_version="hash-embed-test")
    publisher.add_vector(
        "gen_1",
        version_id="ver_1",
        chunk_id="chk_1",
        vector=[1.0, 0.0, 0.0, 0.0],
        text_hash="hash-1",
        document_id="doc_1",
        text="late three times written warning",
        ready=True,
        current=True,
        allowed=True,
        index_generation="gen_1",
    )
    published = publisher.publish("gen_1")
    assert published.status == "published"
    assert store.upsert_calls == 1
    assert store.points[0]["chunk_id"] == "chk_1"
    assert store.points[0]["document_id"] == "doc_1"
    assert store.points[0]["version_id"] == "ver_1"
    hits = store.search([1.0, 0.0, 0.0, 0.0], limit=1)
    assert hits[0]["payload"]["text"] == "late three times written warning"


def test_FR_DOC_006_index_publisher_requires_document_id_for_vector_store():
    store = MemoryVectorStore()
    publisher = IndexPublisher(store=store)
    publisher.start("gen_missing", dimension=4, embedding_model_version="hash-embed-test")
    publisher.add_vector(
        "gen_missing",
        version_id="ver_1",
        chunk_id="chk_1",
        vector=[1.0, 0.0, 0.0, 0.0],
        text_hash="hash-1",
    )
    try:
        publisher.publish("gen_missing")
    except ParseError as error:
        assert error.code == "RESOURCE_LIMIT"
    else:
        raise AssertionError("missing document_id must fail closed")
    assert store.upsert_calls == 0
    assert publisher.published_vectors("gen_missing") == ()


def test_FR_DOC_006_vector_store_failure_does_not_publish():
    sink = RecordingSink()
    worker = IngestWorker(
        sink=sink,
        splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
        embedding=HashingQueryEmbedder(dimension=4),
        index=IndexPublisher(store=BoomVectorStore()),
        dimension=4,
    )
    result = worker.run(
        IngestRequest(
            version_id="ver_boom",
            document_id="doc_boom",
            kind="pdf",
            content=pdf_with_text(),
            message_id="msg_boom",
            title="Attendance Policy",
        )
    )
    assert result["status"] == "failed"
    assert result["error_code"] == "PROVIDER_TEMPORARY_ERROR"
    assert sink.published == []


def test_FR_DOC_006_ingest_writes_retrieval_payload():
    store = MemoryVectorStore()
    embedder = HashingQueryEmbedder(dimension=4)
    sink = RecordingSink()
    worker = IngestWorker(
        sink=sink,
        splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
        embedding=embedder,
        index=IndexPublisher(store=store),
        dimension=4,
    )
    result = worker.run(
        IngestRequest(
            version_id="ver_policy",
            document_id="doc_policy",
            kind="pdf",
            content=pdf_with_text("Late arrival policy"),
            message_id="msg_policy",
            title="Attendance Policy",
            space="hr",
            embedding_model_version="hash-embed-test",
            retrieval_config_version="retr-test",
        )
    )
    assert result["status"] == "ok"
    assert sink.published == ["ver_policy"]
    generation_id = result["content"]["generation_id"]
    payload = store.points[0]
    assert payload["document_id"] == "doc_policy"
    assert payload["version_id"] == "ver_policy"
    assert payload["chunk_id"]
    assert "Late arrival policy" in payload["text"]
    assert payload["title"] == "Attendance Policy"
    assert payload["space"] == "hr"
    assert payload["ready"] is True
    assert payload["current"] is True
    assert payload["allowed"] is True
    assert payload["index_generation"] == generation_id
    assert payload["embedding_model_version"] == "hash-embed-test"
    assert payload["retrieval_config_version"] == "retr-test"
    query = embedder.embed(["Late arrival policy"])[0]
    hits = store.search(query, limit=1)
    assert hits[0]["payload"]["document_id"] == "doc_policy"


def test_FR_DOC_005_duplicate_message_does_not_duplicate_vector_upsert():
    store = MemoryVectorStore()
    worker = IngestWorker(
        splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
        embedding=HashingQueryEmbedder(dimension=4),
        index=IndexPublisher(store=store),
        dimension=4,
    )
    request = IngestRequest(
        version_id="ver_dup",
        document_id="doc_dup",
        kind="pdf",
        content=pdf_with_text(),
        message_id="msg_dup_store",
        title="Attendance Policy",
    )
    first = worker.run(request)
    second = worker.run(request)
    assert first == second
    assert first["status"] == "ok"
    assert store.upsert_calls == 1
    assert len(store.points) == len(first["content"]["chunk_ids"])


def test_FR_DOC_006_ingest_does_not_freeze_dimension():
    source = (_WORKER_SRC / "index.py").read_text(encoding="utf-8")
    ingest = (_WORKER_SRC / "ingest.py").read_text(encoding="utf-8")
    assert "1024" not in source
    assert "768" not in source
    assert "Cosine" not in source
    assert "top-50" not in source
    assert "1024" not in ingest
    assert "bge-m3" not in ingest
