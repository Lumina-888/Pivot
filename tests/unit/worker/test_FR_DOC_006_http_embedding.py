"""HTTP ingest embedding. Failure must not publish. Not GATE-P0 verified."""

from __future__ import annotations

from pivot.chunking import ChunkingPolicy, ChunkSplitter
from pivot.retrieval.fakes import ScriptedJsonHttpClient
from pivot.retrieval.providers import HttpQueryEmbedder
from pivot_worker.ingest import IngestRequest, IngestWorker, RecordingSink
from samples import pdf_with_text


def _http_embedder(client, **overrides) -> HttpQueryEmbedder:
    values = dict(
        endpoint="https://embed.test/v1/embeddings",
        model="injected-embed-model",
        api_key="secret-embed-key",
        expected_dimension=4,
    )
    values.update(overrides)
    return HttpQueryEmbedder(client, **values)


def test_FR_DOC_006_http_embedding_failure_does_not_publish():
    sink = RecordingSink()
    worker = IngestWorker(
        sink=sink,
        splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
        embedding=_http_embedder(ScriptedJsonHttpClient(error=RuntimeError("upstream 503"))),
        dimension=4,
    )
    result = worker.run(
        IngestRequest(
            version_id="ver_http_fail",
            document_id="doc_http_fail",
            kind="pdf",
            content=pdf_with_text(),
            message_id="msg_http_fail",
        )
    )
    assert result["status"] == "failed"
    assert result["error_code"] == "PROVIDER_TEMPORARY_ERROR"
    assert result["trace"]["stage"] == "embed"
    assert sink.published == []
    assert worker._index.published_vectors("missing") == ()


def test_FR_DOC_006_http_embedding_does_not_leak_api_key():
    sink = RecordingSink()
    worker = IngestWorker(
        sink=sink,
        splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
        embedding=_http_embedder(
            ScriptedJsonHttpClient(error=RuntimeError("secret-embed-key 503"))
        ),
        dimension=4,
    )
    result = worker.run(
        IngestRequest(
            version_id="ver_http_leak",
            document_id="doc_http_leak",
            kind="pdf",
            content=pdf_with_text(),
            message_id="msg_http_leak",
        )
    )
    dumped = str(result) + repr(result)
    assert "secret-embed-key" not in dumped
    assert result["status"] == "failed"
    assert sink.published == []
