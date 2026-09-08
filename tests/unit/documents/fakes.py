"""In-memory fakes for M02 unit tests."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from pivot.documents.ports import (
    AuditDraft,
    ChunkRecord,
    DocumentRecord,
    TaskRecord,
    VersionRecord,
)


def ooxml(kind: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        if kind == "docx":
            archive.writestr("word/document.xml", "<w:document/>")
        elif kind == "pptx":
            archive.writestr("ppt/presentation.xml", "<p:presentation/>")
        else:
            archive.writestr("xl/workbook.xml", "<workbook/>")
    return buffer.getvalue()


def pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


class MemoryDocuments:
    def __init__(self) -> None:
        self._items: dict[str, DocumentRecord] = {}

    def get(self, document_id: str) -> DocumentRecord | None:
        return self._items.get(document_id)

    def save(self, document: DocumentRecord) -> None:
        self._items[document.id] = document

    def list_active(self) -> tuple[DocumentRecord, ...]:
        return tuple(self._items.values())


class MemoryVersions:
    def __init__(self) -> None:
        self._items: dict[str, VersionRecord] = {}

    def get(self, version_id: str) -> VersionRecord | None:
        return self._items.get(version_id)

    def save(self, version: VersionRecord) -> None:
        self._items[version.id] = version

    def find_by_sha(self, content_sha256: str) -> VersionRecord | None:
        for version in self._items.values():
            if version.content_sha256 == content_sha256:
                return version
        return None

    def find_by_idempotency(self, key: str) -> VersionRecord | None:
        for version in self._items.values():
            if version.idempotency_key == key:
                return version
        return None

    def list_for_document(self, document_id: str) -> tuple[VersionRecord, ...]:
        return tuple(v for v in self._items.values() if v.document_id == document_id)


class MemoryChunks:
    def __init__(self) -> None:
        self._items: list[ChunkRecord] = []

    def add(self, chunk: ChunkRecord) -> None:
        self._items.append(chunk)

    def list_for_version(self, version_id: str) -> tuple[ChunkRecord, ...]:
        return tuple(c for c in self._items if c.version_id == version_id)


class MemoryTasks:
    def __init__(self) -> None:
        self._items: dict[str, TaskRecord] = {}

    def get(self, task_id: str) -> TaskRecord | None:
        return self._items.get(task_id)

    def save(self, task: TaskRecord) -> None:
        self._items[task.id] = task


class MemoryObjects:
    def __init__(self) -> None:
        self._items: dict[str, bytes] = {}

    def put(self, key: str, payload: bytes) -> None:
        self._items[key] = payload

    def get(self, key: str) -> bytes | None:
        return self._items.get(key)

    def exists(self, key: str) -> bool:
        return key in self._items

    def delete(self, key: str) -> None:
        self._items.pop(key, None)

    def keys(self) -> tuple[str, ...]:
        return tuple(self._items)


class MemoryAudits:
    def __init__(self) -> None:
        self.events: list[AuditDraft] = []

    def emit(self, event: AuditDraft) -> None:
        self.events.append(event)
