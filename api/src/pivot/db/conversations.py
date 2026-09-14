"""SQLAlchemy conversation store backed by the PostgreSQL fact model."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pivot.db.models import Conversation
from pivot.db.uow import UnitOfWork
from pivot.runs.conversations import ConversationRecord
from pivot.shared.time import ensure_utc, utc_now


def _session_scope(
    session: Session | None, factory: sessionmaker[Session] | None
) -> Iterator[Session]:
    if session is not None:
        yield session
        return
    assert factory is not None
    owned = factory()
    try:
        yield owned
    finally:
        owned.close()


def _to_record(row: Conversation) -> ConversationRecord:
    return ConversationRecord(
        id=row.id,
        owner_id=row.owner_id,
        title=row.title,
        scope_type=row.scope_type,
        created_at=ensure_utc(row.created_at),
        updated_at=ensure_utc(row.updated_at),
        scope_document_id=row.scope_document_id,
        hidden=False,
    )


class SqlAlchemyConversationStore:
    """ConversationStore that reads and writes SPEC §2.2 Conversation fields."""

    def __init__(self, sessions: Session | sessionmaker[Session]) -> None:
        if isinstance(sessions, Session):
            self._session: Session | None = sessions
            self._factory: sessionmaker[Session] | None = None
        else:
            self._session = None
            self._factory = sessions

    @contextmanager
    def _scope(self) -> Iterator[Session]:
        yield from _session_scope(self._session, self._factory)

    def save(self, record: ConversationRecord) -> None:
        if not record.id or not record.owner_id:
            raise ValueError("conversations require a non-empty id and owner_id")
        with self._scope() as session:
            with UnitOfWork(session):
                row = session.get(Conversation, record.id)
                if record.hidden:
                    if row is not None:
                        session.delete(row)
                    return
                if row is None:
                    session.add(
                        Conversation(
                            id=record.id,
                            owner_id=record.owner_id,
                            title=record.title,
                            scope_type=record.scope_type,
                            scope_document_id=record.scope_document_id,
                            created_at=record.created_at or utc_now(),
                            updated_at=record.updated_at or utc_now(),
                        )
                    )
                    return
                row.owner_id = record.owner_id
                row.title = record.title
                row.scope_type = record.scope_type
                row.scope_document_id = record.scope_document_id
                row.updated_at = record.updated_at or utc_now()

    def get(self, conversation_id: str) -> ConversationRecord | None:
        with self._scope() as session:
            row = session.get(Conversation, conversation_id)
            return _to_record(row) if row is not None else None

    def list_for_owner(self, owner_id: str) -> tuple[ConversationRecord, ...]:
        with self._scope() as session:
            rows = session.scalars(
                select(Conversation)
                .where(Conversation.owner_id == owner_id)
                .order_by(Conversation.updated_at.desc(), Conversation.id)
            ).all()
            return tuple(_to_record(row) for row in rows)
