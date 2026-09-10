from __future__ import annotations

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
from pivot_worker.index import IndexPublisher
from pivot_worker.queue import IngestQueueConsumer
from pivot_worker.runtime import DocumentIngestRunner
from pivot_worker.settings import WorkerSettings
from samples import pdf_with_text


class _MemoryQueueStore:
    def __init__(self) -> None:
        self._queues: dict[str, list[dict]] = {}

    def enqueue(self, queue: str, payload: dict) -> str:
        self._queues.setdefault(queue, []).append(dict(payload))
        return f"qmsg_{queue}_{len(self._queues[queue])}"

    def dequeue(self, queue: str) -> dict | None:
        items = self._queues.get(queue) or []
        if not items:
            return None
        return items.pop(0)


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


def test_FR_DOC_006_queue_consumer_runs_parse_queue_ingest():
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
    queue = _MemoryQueueStore()
    queue.enqueue(
        "parse",
        {
            "version_id": version.id,
            "request_id": "req_ingest",
            "actor_id": "usr_admin",
        },
    )
    consumer = IngestQueueConsumer(
        queue,
        _runner(documents),
        parse_queue="parse",
        online_queue="online",
        concurrency=1,
    )
    result = consumer.consume_once()
    assert result is not None
    assert result["status"] == "ok"
    ready = documents._versions.get(version.id)
    assert ready is not None
    assert ready.state == "ready"
    assert queue.dequeue("parse") is None


def test_FR_DOC_006_queue_consumer_ignores_online_queue():
    documents = _service()
    version = documents.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=pdf_with_text("Late arrival policy"),
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_up",
    )
    queue = _MemoryQueueStore()
    payload = {
        "version_id": version.id,
        "request_id": "req_online",
        "actor_id": "usr_admin",
    }
    queue.enqueue("online", payload)
    consumer = IngestQueueConsumer(
        queue,
        _runner(documents),
        parse_queue="parse",
        online_queue="online",
        concurrency=1,
    )
    assert consumer.consume_once() is None
    leftover = queue.dequeue("online")
    assert leftover is not None
    assert leftover["version_id"] == version.id
    pending = documents._versions.get(version.id)
    assert pending is not None
    assert pending.state == "uploaded"


def test_FR_DOC_006_worker_settings_reject_shared_parse_and_online_queue():
    with pytest.raises(RuntimeError, match="isolat"):
        WorkerSettings.from_env(
            {
                "PIVOT_PARSE_QUEUE": "shared",
                "PIVOT_ONLINE_QUEUE": "shared",
                "PIVOT_WORKER_CONCURRENCY": "2",
            }
        )
    settings = WorkerSettings.from_env(
        {
            "PIVOT_PARSE_QUEUE": "parse",
            "PIVOT_ONLINE_QUEUE": "online",
            "PIVOT_WORKER_CONCURRENCY": "2",
        }
    )
    assert settings.parse_queue == "parse"
    assert settings.online_queue == "online"
    assert settings.concurrency == 2
