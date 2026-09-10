"""In-memory runtime adapters. Not a production fact store."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pivot.audit.ports import Actor
from pivot.auth.ports import (
    AuditEventDraft,
    ChunkAuthz,
    CitationAuthz,
    DocumentAuthz,
    ExportAuthz,
    RefreshSession,
    UserAccount,
)
from pivot.documents.ports import (
    AuditDraft,
    ChunkRecord,
    DocumentRecord,
    TaskRecord,
    VersionRecord,
)
from pivot.exports.errors import not_found, resource_forbidden
from pivot.exports.models import DocumentExportView, ExportRecord, PersistedAnswer
from pivot.exports.repository import InMemoryExportRepository
from pivot.shared.time import utc_now


class UtcClock:
    def now(self) -> datetime:
        return utc_now()


class InMemoryUserDirectory:
    def __init__(self, users: list[UserAccount] | None = None) -> None:
        self._users = {user.id: user for user in users or []}

    def get_by_id(self, user_id: str) -> UserAccount | None:
        return self._users.get(user_id)

    def get_by_username(self, username: str) -> UserAccount | None:
        for user in self._users.values():
            if user.username == username:
                return user
        return None

    def save(self, user: UserAccount) -> None:
        self._users[user.id] = user

    def list(self) -> tuple[UserAccount, ...]:
        return tuple(self._users.values())


class InMemoryRefreshStore:
    def __init__(self) -> None:
        self._items: dict[str, RefreshSession] = {}

    def save(self, session: RefreshSession) -> None:
        self._items[session.token_hash] = session

    def get(self, token_hash: str) -> RefreshSession | None:
        return self._items.get(token_hash)

    def revoke(self, token_hash: str) -> None:
        self._items.pop(token_hash, None)

    def revoke_user(self, user_id: str) -> None:
        self._items = {
            key: value for key, value in self._items.items() if value.user_id != user_id
        }


class InMemoryAuthAudit:
    def __init__(self) -> None:
        self.events: list[AuditEventDraft] = []

    def emit(self, event: AuditEventDraft) -> None:
        self.events.append(event)


class InMemoryAttempts:
    def __init__(self) -> None:
        self.failures: dict[str, int] = {}

    def record_failure(self, username: str) -> int:
        self.failures[username] = self.failures.get(username, 0) + 1
        return self.failures[username]

    def reset(self, username: str) -> None:
        self.failures.pop(username, None)

    def is_blocked(self, username: str) -> bool:
        # Threshold is TBD-P0; the default policy never locks.
        return False


@dataclass
class InMemoryResources:
    documents: dict[str, DocumentAuthz] = field(default_factory=dict)
    chunks: dict[str, ChunkAuthz] = field(default_factory=dict)
    citations: dict[str, CitationAuthz] = field(default_factory=dict)
    exports: dict[str, ExportAuthz] = field(default_factory=dict)
    conversations: dict[str, str] = field(default_factory=dict)

    def get_document(self, document_id: str) -> DocumentAuthz | None:
        return self.documents.get(document_id)

    def get_chunk(self, chunk_id: str) -> ChunkAuthz | None:
        return self.chunks.get(chunk_id)

    def get_citation(self, citation_id: str) -> CitationAuthz | None:
        return self.citations.get(citation_id)

    def get_export(self, export_id: str) -> ExportAuthz | None:
        return self.exports.get(export_id)

    def get_conversation_owner(self, conversation_id: str) -> str | None:
        return self.conversations.get(conversation_id)

    def claim_conversation(self, conversation_id: str, owner_id: str) -> str:
        current = self.conversations.get(conversation_id)
        if current is None:
            self.conversations[conversation_id] = owner_id
            return owner_id
        return current


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
        return tuple(item for item in self._items.values() if item.document_id == document_id)


class MemoryChunks:
    def __init__(self) -> None:
        self._items: list[ChunkRecord] = []

    def add(self, chunk: ChunkRecord) -> None:
        self._items = [item for item in self._items if item.id != chunk.id]
        self._items.append(chunk)

    def list_for_version(self, version_id: str) -> tuple[ChunkRecord, ...]:
        return tuple(item for item in self._items if item.version_id == version_id)


class MemoryTasks:
    def __init__(self) -> None:
        self._items: dict[str, TaskRecord] = {}

    def get(self, task_id: str) -> TaskRecord | None:
        return self._items.get(task_id)

    def save(self, task: TaskRecord) -> None:
        self._items[task.id] = task


class MemoryDocumentObjects:
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


class MemoryDocumentAudits:
    def __init__(self) -> None:
        self.events: list[AuditDraft] = []

    def emit(self, event: AuditDraft) -> None:
        self.events.append(event)


class MemoryExportObjects:
    def __init__(self, public_base: str) -> None:
        self._items: dict[str, bytes] = {}
        self._base = public_base.rstrip("/")

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        self._items[key] = data

    def get(self, key: str) -> bytes:
        return self._items[key]

    def exists(self, key: str) -> bool:
        return key in self._items

    def presign(self, key: str, *, expires_seconds: int) -> str:
        return f"{self._base}/d/{key}?e={expires_seconds}"


class MemoryAnswerStore:
    def __init__(self) -> None:
        self.answers: dict[str, PersistedAnswer] = {}
        self.documents: dict[str, DocumentExportView] = {}

    def get_exportable_answer(self, conversation_id: str) -> PersistedAnswer | None:
        return self.answers.get(conversation_id)

    def get_document_export(self, document_id: str) -> DocumentExportView | None:
        return self.documents.get(document_id)


class MemoryExportAccess:
    def __init__(self, exports: InMemoryExportRepository, resources: InMemoryResources) -> None:
        self._exports = exports
        self._resources = resources

    def authorize_conversation(self, actor: Actor, conversation_id: str, request_id: str) -> None:
        owner = self._resources.get_conversation_owner(conversation_id)
        if owner is None:
            raise not_found(request_id)
        if owner == actor.user_id:
            return
        if actor.role == "admin":
            raise resource_forbidden(request_id)
        raise not_found(request_id)

    def authorize_document(self, actor: Actor, document_id: str, request_id: str) -> None:
        document = self._resources.get_document(document_id)
        if document is None or document.deleted:
            raise not_found(request_id)
        if document.shared_visible or document.owner_id == actor.user_id:
            return
        raise not_found(request_id)

    def authorize_export(self, actor: Actor, export_id: str, request_id: str) -> None:
        record: ExportRecord | None = self._exports.get(export_id)
        if record is None:
            raise not_found(request_id)
        if record.owner_id == actor.user_id:
            return
        if actor.role == "admin":
            raise resource_forbidden(request_id)
        raise not_found(request_id)
