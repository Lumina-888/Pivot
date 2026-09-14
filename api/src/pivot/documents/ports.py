"""Persistence and side-effect ports for the document domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class DocumentRecord:
    id: str
    title: str
    space: str
    created_by: str
    deleted_at: datetime | None = None
    classification: str = ""
    created_at: datetime | None = None
    tags: tuple[str, ...] = ()


@dataclass
class VersionRecord:
    id: str
    document_id: str
    content_sha256: str
    storage_key: str
    state: str = "uploaded"
    current: bool = False
    idempotency_key: str | None = None
    error_code: str | None = None
    external_llm_allowed: bool = False


@dataclass
class ChunkRecord:
    id: str
    version_id: str
    text: str
    text_hash: str
    published: bool = False


@dataclass
class TaskRecord:
    id: str
    entity_id: str
    entity_type: str
    attempt: int = 1
    state: str = "queued"
    retryable: bool = False
    error_code: str | None = None


@dataclass(frozen=True)
class PreparedIngest:
    version: VersionRecord
    document: DocumentRecord
    content: bytes
    kind: str
    task_id: str


@dataclass(frozen=True)
class AuditDraft:
    actor: str
    action: str
    target: str
    result: str
    request_id: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceLimits:
    """Injectable caps. None means unset TBD-P0, not a frozen default."""

    max_bytes: int | None = None
    max_zip_ratio: float | None = None


@dataclass(frozen=True)
class FileContent:
    """Authorized original bytes. Never include storage_key or object URLs."""

    body: bytes
    filename: str
    media_type: str
    disposition: str


class DocumentStore(Protocol):
    def get(self, document_id: str) -> DocumentRecord | None: ...

    def save(self, document: DocumentRecord) -> None: ...

    def list_active(self) -> tuple[DocumentRecord, ...]: ...


class VersionStore(Protocol):
    def get(self, version_id: str) -> VersionRecord | None: ...

    def save(self, version: VersionRecord) -> None: ...

    def find_by_sha(self, content_sha256: str) -> VersionRecord | None: ...

    def find_by_idempotency(self, key: str) -> VersionRecord | None: ...

    def list_for_document(self, document_id: str) -> tuple[VersionRecord, ...]: ...


class ChunkStore(Protocol):
    def add(self, chunk: ChunkRecord) -> None: ...

    def list_for_version(self, version_id: str) -> tuple[ChunkRecord, ...]: ...


class TaskStore(Protocol):
    def get(self, task_id: str) -> TaskRecord | None: ...

    def save(self, task: TaskRecord) -> None: ...


class ObjectStore(Protocol):
    def put(self, key: str, payload: bytes) -> None: ...

    def get(self, key: str) -> bytes | None: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...

    def keys(self) -> tuple[str, ...]: ...


class AuditSink(Protocol):
    def emit(self, event: AuditDraft) -> None: ...
