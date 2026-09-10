"""Run ingest against DocumentService. Queue execution is still not Celery."""

from __future__ import annotations

from typing import Any

from pivot.chunking import ChunkSplitter
from pivot.documents.ingest import DocumentIngestSink
from pivot.documents.service import DocumentService

from pivot_worker.embedding import EmbeddingPort
from pivot_worker.index import IndexPublisher
from pivot_worker.ingest import IngestRequest, IngestWorker


class DocumentIngestRunner:
    def __init__(
        self,
        documents: DocumentService,
        *,
        embedding: EmbeddingPort | None = None,
        index: IndexPublisher | None = None,
        dimension: int | None = None,
        splitter: ChunkSplitter | None = None,
        embedding_model_version: str = "fake-embed-v1",
        retrieval_config_version: str = "",
    ) -> None:
        self._documents = documents
        self._embedding = embedding
        self._index = index
        self._dimension = dimension
        self._splitter = splitter
        self._embedding_model_version = embedding_model_version
        self._retrieval_config_version = retrieval_config_version

    def __call__(self, version_id: str, request_id: str, actor_id: str) -> dict[str, Any] | None:
        prepared = self._documents.prepare_ingest(version_id, request_id, actor_id)
        if prepared is None:
            return None
        kwargs: dict[str, object] = {
            "sink": DocumentIngestSink(self._documents, request_id),
        }
        if self._embedding is not None:
            kwargs["embedding"] = self._embedding
        if self._index is not None:
            kwargs["index"] = self._index
        if self._dimension is not None:
            kwargs["dimension"] = self._dimension
        if self._splitter is not None:
            kwargs["splitter"] = self._splitter
        worker = IngestWorker(**kwargs)
        return worker.run(
            IngestRequest(
                version_id=prepared.version.id,
                document_id=prepared.document.id,
                kind=prepared.kind,
                content=prepared.content,
                message_id=prepared.task_id,
                title=prepared.document.title,
                space=prepared.document.space,
                tags=prepared.document.tags,
                embedding_model_version=self._embedding_model_version,
                retrieval_config_version=self._retrieval_config_version,
            )
        )
