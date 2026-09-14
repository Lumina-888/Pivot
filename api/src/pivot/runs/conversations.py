"""Conversation directory used by HTTP CRUD (FR-RBAC-002)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pivot.runs.errors import not_found
from pivot.runs.models import synthetic_user_message_id
from pivot.runs.service import RunService
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now

_SCOPE_TYPES = frozenset({"global", "document"})


def format_utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ConversationRecord:
    id: str
    owner_id: str
    title: str
    scope_type: str
    created_at: datetime
    updated_at: datetime
    scope_document_id: str | None = None
    hidden: bool = False


class ConversationStore(Protocol):
    def save(self, record: ConversationRecord) -> None: ...

    def get(self, conversation_id: str) -> ConversationRecord | None: ...

    def list_for_owner(self, owner_id: str) -> tuple[ConversationRecord, ...]: ...


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._items: dict[str, ConversationRecord] = {}

    def save(self, record: ConversationRecord) -> None:
        self._items[record.id] = record

    def get(self, conversation_id: str) -> ConversationRecord | None:
        return self._items.get(conversation_id)

    def list_for_owner(self, owner_id: str) -> tuple[ConversationRecord, ...]:
        items = [record for record in self._items.values() if record.owner_id == owner_id]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return tuple(items)


class ConversationService:
    def __init__(
        self,
        runs: RunService | None = None,
        store: ConversationStore | None = None,
    ) -> None:
        self._store = store or InMemoryConversationStore()
        self._runs = runs

    def create(
        self,
        *,
        owner_id: str,
        title: str,
        request_id: str,
        scope_type: str = "global",
        scope_document_id: str | None = None,
    ) -> ConversationRecord:
        if scope_type not in _SCOPE_TYPES:
            raise not_found(request_id)
        document_id = (scope_document_id or "").strip() or None
        if scope_type == "document" and document_id is None:
            raise not_found(request_id)
        if scope_type == "global":
            document_id = None
        now = utc_now()
        record = ConversationRecord(
            id=new_id("conversation"),
            owner_id=owner_id,
            title=title,
            scope_type=scope_type,
            scope_document_id=document_id,
            created_at=now,
            updated_at=now,
        )
        self._store.save(record)
        return record

    def lookup(self, conversation_id: str) -> ConversationRecord | None:
        return self._store.get(conversation_id)

    def get(self, conversation_id: str, request_id: str) -> ConversationRecord:
        record = self.lookup(conversation_id)
        if record is None or record.hidden:
            raise not_found(request_id)
        return record

    def list_for_owner(self, owner_id: str) -> tuple[ConversationRecord, ...]:
        return tuple(
            record for record in self._store.list_for_owner(owner_id) if not record.hidden
        )

    def hide(self, conversation_id: str, request_id: str) -> None:
        record = self.get(conversation_id, request_id)
        record.hidden = True
        record.updated_at = utc_now()
        self._store.save(record)

    def to_summary(self, record: ConversationRecord) -> dict[str, str | None]:
        return {
            "conversation_id": record.id,
            "owner_id": record.owner_id,
            "title": record.title,
            "scope_type": record.scope_type,
            "scope_document_id": record.scope_document_id,
            "created_at": format_utc(record.created_at),
            "updated_at": format_utc(record.updated_at),
        }

    def list_messages(self, conversation_id: str, request_id: str) -> list[dict[str, str | None]]:
        self.get(conversation_id, request_id)
        if self._runs is None:
            return []
        messages: list[dict[str, str | None]] = []
        for bundle in self._runs.list_for_conversation(conversation_id):
            created = bundle.run.created_at or utc_now()
            stamp = format_utc(created)
            messages.append(
                {
                    "message_id": synthetic_user_message_id(bundle.run.id),
                    "conversation_id": conversation_id,
                    "sender": "user",
                    "content": bundle.run.question,
                    "status": bundle.run.state,
                    "run_id": bundle.run.id,
                    "created_at": stamp,
                }
            )
            answer = bundle.run.answer_markdown or ""
            messages.append(
                {
                    "message_id": bundle.run.message_id,
                    "conversation_id": conversation_id,
                    "sender": "assistant",
                    "content": answer,
                    "status": bundle.run.state,
                    "run_id": bundle.run.id,
                    "created_at": stamp,
                }
            )
        return messages
