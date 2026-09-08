"""Persistence and side-effect ports used by M01. Implementations live with callers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class UserAccount:
    id: str
    username: str
    password_hash: str
    role: str
    status: str
    token_version: int = 0
    must_change_password: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    role: str
    token_version: int
    status: str = "active"


@dataclass
class RefreshSession:
    token_hash: str
    user_id: str
    token_version: int
    expires_at: datetime
    revoked: bool = False


@dataclass(frozen=True)
class AuditEventDraft:
    actor: str
    action: str
    target: str
    result: str
    request_id: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentAuthz:
    id: str
    deleted: bool
    shared_visible: bool
    export_allowed: bool
    owner_id: str | None = None


@dataclass(frozen=True)
class ChunkAuthz:
    id: str
    document_id: str
    published: bool


@dataclass(frozen=True)
class CitationAuthz:
    id: str
    document_id: str
    chunk_id: str


@dataclass(frozen=True)
class ExportAuthz:
    id: str
    owner_id: str


class UserDirectory(Protocol):
    def get_by_id(self, user_id: str) -> UserAccount | None: ...

    def get_by_username(self, username: str) -> UserAccount | None: ...

    def save(self, user: UserAccount) -> None: ...

    def list(self) -> tuple[UserAccount, ...]: ...


class RefreshTokenStore(Protocol):
    def save(self, session: RefreshSession) -> None: ...

    def get(self, token_hash: str) -> RefreshSession | None: ...

    def revoke(self, token_hash: str) -> None: ...

    def revoke_user(self, user_id: str) -> None: ...


class AuditSink(Protocol):
    def emit(self, event: AuditEventDraft) -> None: ...


class LoginAttemptLimiter(Protocol):
    def record_failure(self, username: str) -> int: ...

    def reset(self, username: str) -> None: ...

    def is_blocked(self, username: str) -> bool: ...


class ResourceCatalog(Protocol):
    def get_document(self, document_id: str) -> DocumentAuthz | None: ...

    def get_chunk(self, chunk_id: str) -> ChunkAuthz | None: ...

    def get_citation(self, citation_id: str) -> CitationAuthz | None: ...

    def get_export(self, export_id: str) -> ExportAuthz | None: ...

    def get_conversation_owner(self, conversation_id: str) -> str | None: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...
