from __future__ import annotations

from pivot.chunking import ChunkingPolicy, ChunkSplitter
from pivot.documents.service import DocumentService
from pivot.http.memory import (
    MemoryChunks,
    MemoryDocumentAudits,
    MemoryDocumentObjects,
    MemoryDocuments,
    MemoryTasks,
    MemoryVersions,
)
from pivot.retrieval.fakes import HashingQueryEmbedder
from pivot_worker.index import IndexPublisher
from pivot_worker.runtime import DocumentIngestRunner
from samples import pdf_with_text


def _service() -> DocumentService:
    return DocumentService(
        documents=MemoryDocuments(),
        versions=MemoryVersions(),
        chunks=MemoryChunks(),
        tasks=MemoryTasks(),
        objects=MemoryDocumentObjects(),
        audits=MemoryDocumentAudits(),
    )


def test_FR_DOC_001_ingest_runner_reaches_ready():
    documents = _service()
    version = documents.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=pdf_with_text("Late arrival policy"),
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_up",
        space="hr",
    )
    store = _MemoryStore()
    embedder = HashingQueryEmbedder(dimension=4)
    runner = DocumentIngestRunner(
        documents,
        embedding=embedder,
        index=IndexPublisher(store=store),
        dimension=4,
        splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
    )
    result = runner(version.id, "req_ingest", "usr_admin")
    assert result is not None
    assert result["status"] == "ok"
    ready = documents._versions.get(version.id)
    assert ready is not None
    assert ready.state == "ready"
    assert ready.current is True
    assert store.points
    assert store.points[0]["document_id"] == version.document_id
    assert "Late arrival policy" in store.points[0]["text"]


def test_FR_DOC_006_ingest_runner_skips_ready_version():
    documents = _service()
    version = documents.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=pdf_with_text("Late arrival policy"),
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_up",
    )
    runner = DocumentIngestRunner(documents, dimension=4)
    first = runner(version.id, "req_one", "usr_admin")
    second = runner(version.id, "req_two", "usr_admin")
    assert first is not None and first["status"] == "ok"
    assert second is None


class _MemoryStore:
    def __init__(self) -> None:
        self.points: list[dict] = []

    def upsert(self, points) -> None:
        self.points.extend(dict(point) for point in points)

    def search(self, vector, *, limit: int, filters=None):
        return []

    def delete(self, *, version_id=None, chunk_id=None) -> None:
        return None
