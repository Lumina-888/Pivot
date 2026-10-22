"""SQLAlchemy audit store and sink adapters backed by audit_events (M03/M06).

All runtime audit streams (unified AuditService, auth sink, document sink)
land in the same append-only fact table so events survive restarts and can
be replayed by request_id or run_id (ND-GAP-02).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pivot.audit.catalog import canonicalize
from pivot.audit.errors import append_only
from pivot.audit.models import AuditEventRecord
from pivot.audit.redaction import redact_metadata
from pivot.auth.ports import AuditEventDraft as AuthAuditDraft
from pivot.db.models import AuditEvent
from pivot.db.uow import UnitOfWork
from pivot.documents.ports import AuditDraft as DocumentAuditDraft
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now


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


def _to_record(row: AuditEvent) -> AuditEventRecord:
    return AuditEventRecord(
        id=row.id,
        actor=row.actor,
        action=row.action,
        target=row.target,
        result=row.result,
        request_id=row.request_id,
        run_id=row.run_id,
        metadata=dict(row.metadata_ or {}),
        created_at=row.created_at,
    )


class SqlAlchemyAuditStore:
    """Append-only audit store over the audit_events fact table."""

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

    def append(self, event: AuditEventRecord) -> None:
        # The duplicate check raises the frozen AuditError outside the
        # unit-of-work context on purpose: contextlib would try to attach
        # a traceback to the frozen exception and mask it. The primary
        # key remains the hard guard against concurrent duplicates.
        if self.get(event.id) is not None:
            raise append_only(event.request_id or "req_audit")
        with self._scope() as session:
            with UnitOfWork(session):
                session.add(
                    AuditEvent(
                        id=event.id,
                        actor=event.actor,
                        action=event.action,
                        target=event.target,
                        result=event.result,
                        request_id=event.request_id,
                        run_id=event.run_id,
                        metadata_=dict(event.metadata),
                        created_at=event.created_at,
                    )
                )

    def get(self, event_id: str) -> AuditEventRecord | None:
        with self._scope() as session:
            row = session.get(AuditEvent, event_id)
            return _to_record(row) if row is not None else None

    def list(self) -> tuple[AuditEventRecord, ...]:
        with self._scope() as session:
            rows = session.scalars(
                select(AuditEvent).order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
            ).all()
            return tuple(_to_record(row) for row in rows)

    def query(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        request_id: str | None = None,
        run_id: str | None = None,
    ) -> tuple[AuditEventRecord, ...]:
        with self._scope() as session:
            stmt = select(AuditEvent)
            if actor is not None:
                stmt = stmt.where(AuditEvent.actor == actor)
            if action is not None:
                stmt = stmt.where(AuditEvent.action == action)
            if request_id is not None:
                stmt = stmt.where(AuditEvent.request_id == request_id)
            if run_id is not None:
                stmt = stmt.where(AuditEvent.run_id == run_id)
            stmt = stmt.order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
            return tuple(_to_record(row) for row in session.scalars(stmt).all())


def _append_draft(
    store: SqlAlchemyAuditStore,
    *,
    actor: str,
    action: str,
    target: str,
    result: str,
    request_id: str,
    metadata: dict[str, Any],
) -> None:
    store.append(
        AuditEventRecord(
            id=new_id("audit"),
            actor=actor,
            action=canonicalize(action),
            target=target,
            result=result,
            request_id=request_id,
            run_id=None,
            metadata=redact_metadata(metadata),
            created_at=utc_now(),
        )
    )


class SqlAlchemyAuthAuditSink:
    """Auth audit sink persisting drafts into audit_events."""

    def __init__(self, store: SqlAlchemyAuditStore) -> None:
        self._store = store

    def emit(self, event: AuthAuditDraft) -> None:
        _append_draft(
            self._store,
            actor=event.actor,
            action=event.action,
            target=event.target,
            result=event.result,
            request_id=event.request_id,
            metadata=event.metadata,
        )


class SqlAlchemyDocumentAuditSink:
    """Document audit sink persisting drafts into audit_events."""

    def __init__(self, store: SqlAlchemyAuditStore) -> None:
        self._store = store

    def emit(self, event: DocumentAuditDraft) -> None:
        _append_draft(
            self._store,
            actor=event.actor,
            action=event.action,
            target=event.target,
            result=event.result,
            request_id=event.request_id,
            metadata=event.metadata,
        )
