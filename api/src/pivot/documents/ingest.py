"""M02 IngestSink adapter. Parsing/indexing execution stays in M07."""

from __future__ import annotations

from pivot.documents.service import DocumentService


class DocumentIngestSink:
    def __init__(self, documents: DocumentService, request_id: str) -> None:
        self._documents = documents
        self._request_id = request_id

    def on_parse_ok(self, version_id: str) -> None:
        self._documents.parse_ok(version_id, self._request_id)

    def on_parse_error(self, version_id: str, code: str) -> None:
        self._documents.parse_error(version_id, code, self._request_id)

    def on_chunks(self, version_id: str, texts: list[str], message_id: str) -> list[str]:
        records = self._documents.apply_chunks(
            version_id, texts, message_id, self._request_id
        )
        return [record.id for record in records]

    def on_embedding_ok(self, version_id: str) -> None:
        self._documents.embedding_ok(version_id, self._request_id)

    def on_embedding_error(self, version_id: str) -> None:
        self._documents.embedding_error(version_id, self._request_id)

    def on_publish(self, version_id: str) -> None:
        self._documents.publish(version_id, self._request_id)
