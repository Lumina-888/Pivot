from __future__ import annotations

from pathlib import Path

import pytest
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
from pivot_worker.celery_app import CeleryIngestSubmitter, build_ingest_celery
from pivot_worker.index import IndexPublisher
from pivot_worker.runtime import DocumentIngestRunner
from samples import pdf_with_text

_CELERY_SRC = (
    Path(__file__).resolve().parents[3] / "worker" / "src" / "pivot_worker" / "celery_app.py"
)


class _MemoryStore:
    def __init__(self) -> None:
        self.points: list[dict] = []

    def upsert(self, points) -> None:
        self.points.extend(dict(point) for point in points)

    def search(self, vector, *, limit: int, filters=None):
        return []

    def delete(self, *, version_id=None, chunk_id=None) -> None:
        return None


def _service() -> DocumentService:
    return DocumentService(
        documents=MemoryDocuments(),
        versions=MemoryVersions(),
        chunks=MemoryChunks(),
        tasks=MemoryTasks(),
        objects=MemoryDocumentObjects(),
        audits=MemoryDocumentAudits(),
    )


def _runner(documents: DocumentService) -> DocumentIngestRunner:
    return DocumentIngestRunner(
        documents,
        embedding=HashingQueryEmbedder(dimension=4),
        index=IndexPublisher(store=_MemoryStore()),
        dimension=4,
        splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
    )


def _submitter(documents: DocumentService) -> CeleryIngestSubmitter:
    return CeleryIngestSubmitter(
        _runner(documents),
        parse_queue="parse",
        online_queue="online",
        concurrency=1,
        broker_url="memory://",
        always_eager=True,
    )


def test_FR_DOC_005_celery_requires_isolated_parse_and_online_queues():
    with pytest.raises(RuntimeError, match="isolat"):
        build_ingest_celery(
            parse_queue="shared",
            online_queue="shared",
            concurrency=1,
            broker_url="memory://",
            always_eager=True,
        )


def test_FR_DOC_005_celery_requires_broker():
    with pytest.raises(RuntimeError, match="PIVOT_CELERY_BROKER"):
        build_ingest_celery(
            parse_queue="parse",
            online_queue="online",
            concurrency=1,
            broker_url=None,
            always_eager=True,
        )


def test_FR_DOC_005_celery_eager_ingest_reaches_ready():
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
    result = _submitter(documents)(version.id, "req_ingest", "usr_admin")
    assert result is not None
    assert result["status"] == "ok"
    ready = documents._versions.get(version.id)
    assert ready is not None
    assert ready.state == "ready"
    assert ready.current is True


def test_FR_DOC_005_celery_duplicate_message_does_not_reingest():
    documents = _service()
    version = documents.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=pdf_with_text("Late arrival policy"),
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_up",
    )
    submitter = _submitter(documents)
    first = submitter(version.id, "req_one", "usr_admin")
    second = submitter(version.id, "req_two", "usr_admin")
    assert first is not None and first["status"] == "ok"
    assert second is None
    ready = documents._versions.get(version.id)
    assert ready is not None
    assert ready.state == "ready"


def test_FR_DOC_005_celery_task_routes_to_parse_queue():
    submitter = _submitter(_service())
    assert submitter.parse_queue == "parse"
    assert submitter.online_queue == "online"
    assert submitter.task_queue == "parse"
    assert submitter.task_queue != submitter.online_queue


def test_FR_DOC_005_celery_source_has_no_hardcoded_broker():
    text = _CELERY_SRC.read_text(encoding="utf-8").lower()
    assert "localhost" not in text
    assert "127.0.0.1" not in text
    assert "redis://" not in text
    assert "amqp://" not in text
    assert "siliconflow" not in text
    assert "memory://" not in text
