from __future__ import annotations

from pivot.chunking import ChunkingPolicy, ChunkSplitter
from pivot_worker.embedding import FakeEmbedding
from pivot_worker.ingest import IngestRequest, IngestWorker, RecordingSink
from samples import pdf_with_text


def test_M07_dimension_mismatch_does_not_publish():
    sink = RecordingSink()
    worker = IngestWorker(
        sink=sink,
        splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
        embedding=FakeEmbedding(dimension=3),
        dimension=8,
    )
    result = worker.run(
        IngestRequest(
            version_id="ver_dim",
            kind="pdf",
            content=pdf_with_text(),
            message_id="msg_dim",
        )
    )
    assert result["status"] == "failed"
    assert result["error_code"] == "RESOURCE_LIMIT"
    assert sink.published == []
    assert worker._index.published_vectors("missing") == ()


def test_M07_retryable_embedding_error(worker):
    assert worker.is_retryable("PROVIDER_TEMPORARY_ERROR") is True
    assert worker.is_retryable("ENCRYPTED_FILE") is False


def test_M07_index_generation_is_atomic_on_success(worker):
    result = worker.run(
        IngestRequest(
            version_id="ver_ok",
            kind="pdf",
            content=pdf_with_text(),
            message_id="msg_ok",
        )
    )
    generation_id = result["content"]["generation_id"]
    vectors = worker._index.published_vectors(generation_id)
    assert result["status"] == "ok"
    assert vectors
    assert all(item.payload["chunk_id"] for item in vectors)
