"""In-memory fakes for M01 unit tests. Not a production fact store."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from pivot.auth.ports import (
    AuditEventDraft,
    ChunkAuthz,
    CitationAuthz,
    DocumentAuthz,
    ExportAuthz,
    RefreshSession,
    UserAccount,
)


class TestPasswordHasher:
    """Deterministic PBKDF2 hasher for tests; production must use Argon2id."""

    def hash(self, password: str) -> str:
        if not password:
            raise ValueError("password required")
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), 120_000
        ).hex()
        return f"pbkdf2${salt}${digest}"

    def verify(self, password: str, password_hash: str) -> bool:
        parts = password_hash.split("$")
        if len(parts) != 3 or parts[0] != "pbkdf2":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(parts[1]), 120_000
        ).hex()
        return hmac.compare_digest(expected, parts[2])


class FakeClock:
    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 9, 6, 8, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: int) -> None:
        self._now = self._now + timedelta(seconds=seconds)


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


class InMemoryAudit:
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
