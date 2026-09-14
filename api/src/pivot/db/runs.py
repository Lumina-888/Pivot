"""SQLAlchemy Run / AgentEvent / Message store backed by the PostgreSQL fact model."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from pivot.db.models import AgentEvent, Conversation, Message, Run
from pivot.db.uow import UnitOfWork
from pivot.runs.machine import is_terminal
from pivot.runs.models import RunBundle, RunRecord, run_fingerprint, synthetic_user_message_id
from pivot.shared.ids import new_id
from pivot.shared.time import ensure_utc, utc_now
from pivot.stream.buffer import EventLog
from pivot.stream.events import envelope


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


def _parse_timestamp(value: str) -> datetime:
    return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _summary_of(name: str, data: dict[str, Any]) -> str:
    payload = data.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    return json.dumps(
        {"event": name, "payload": payload},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _parse_summary(summary: str) -> tuple[str, dict[str, Any]]:
    try:
        body = json.loads(summary)
    except json.JSONDecodeError:
        return summary, {}
    if not isinstance(body, dict):
        return summary, {}
    event = body.get("event")
    payload = body.get("payload")
    if not isinstance(event, str):
        return summary, {}
    if not isinstance(payload, dict):
        payload = {}
    return event, payload


def _to_bundle(row: Run, owner_id: str, answer_markdown: str | None) -> RunBundle:
    question = row.question
    scope_type = row.scope_type
    scope_document_id = row.scope_document_id
    return RunBundle(
        run=RunRecord(
            id=row.id,
            conversation_id=row.conversation_id,
            message_id=row.message_id or "",
            owner_id=owner_id,
            question=question,
            idempotency_key=row.idempotency_key,
            fingerprint=run_fingerprint(question, scope_type, scope_document_id),
            scope_type=scope_type,
            scope_document_id=scope_document_id,
            state=row.state,
            error_code=row.error_code,
            answer_markdown=answer_markdown,
            created_at=ensure_utc(row.created_at) if row.created_at is not None else None,
        )
    )


def _owner_id(session: Session, conversation_id: str) -> str:
    conversation = session.get(Conversation, conversation_id)
    return conversation.owner_id if conversation is not None else ""


def _answer_markdown(session: Session, message_id: str | None) -> str | None:
    if not message_id:
        return None
    message = session.get(Message, message_id)
    if message is None:
        return None
    return message.content


class SqlAlchemyRunStore:
    """RunStore that reads and writes SPEC §2.2 Run, AgentEvent and Message fields."""

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

    def save(self, bundle: RunBundle, log: EventLog | None = None) -> None:
        run = bundle.run
        if not run.id or not run.conversation_id:
            raise ValueError("runs require a non-empty id and conversation_id")
        with self._scope() as session:
            with UnitOfWork(session):
                if session.get(Conversation, run.conversation_id) is None:
                    raise ValueError("runs require an existing conversation")
                row = session.get(Run, run.id)
                now = utc_now()
                completed_at = now if is_terminal(run.state) else None
                if row is None:
                    session.add(
                        Run(
                            id=run.id,
                            conversation_id=run.conversation_id,
                            message_id=run.message_id,
                            question=run.question,
                            scope_type=run.scope_type,
                            scope_document_id=run.scope_document_id,
                            idempotency_key=run.idempotency_key,
                            state=run.state,
                            error_code=run.error_code,
                            created_at=run.created_at or now,
                            started_at=run.created_at or now,
                            completed_at=completed_at,
                        )
                    )
                else:
                    row.conversation_id = run.conversation_id
                    row.message_id = run.message_id
                    row.question = run.question
                    row.scope_type = run.scope_type
                    row.scope_document_id = run.scope_document_id
                    row.idempotency_key = run.idempotency_key
                    row.state = run.state
                    row.error_code = run.error_code
                    if completed_at is not None:
                        row.completed_at = completed_at
                self._upsert_messages(session, run)
                if log is not None:
                    self._replace_events(session, run, log)

    def get(self, run_id: str) -> RunBundle | None:
        with self._scope() as session:
            row = session.get(Run, run_id)
            if row is None:
                return None
            return _to_bundle(
                row,
                _owner_id(session, row.conversation_id),
                _answer_markdown(session, row.message_id),
            )

    def get_by_idempotency(self, conversation_id: str, idempotency_key: str) -> RunBundle | None:
        with self._scope() as session:
            row = session.scalars(
                select(Run).where(
                    Run.conversation_id == conversation_id,
                    Run.idempotency_key == idempotency_key,
                )
            ).first()
            if row is None:
                return None
            return _to_bundle(
                row,
                _owner_id(session, row.conversation_id),
                _answer_markdown(session, row.message_id),
            )

    def list_for_conversation(self, conversation_id: str) -> tuple[RunBundle, ...]:
        with self._scope() as session:
            rows = session.scalars(
                select(Run)
                .where(Run.conversation_id == conversation_id)
                .order_by(Run.created_at.asc(), Run.id)
            ).all()
            return tuple(
                _to_bundle(
                    row,
                    _owner_id(session, row.conversation_id),
                    _answer_markdown(session, row.message_id),
                )
                for row in rows
            )

    def get_log(self, run_id: str, message_id: str) -> EventLog | None:
        with self._scope() as session:
            row = session.get(Run, run_id)
            if row is None:
                return None
            events = session.scalars(
                select(AgentEvent)
                .where(AgentEvent.run_id == run_id)
                .order_by(AgentEvent.seq.asc(), AgentEvent.id)
            ).all()
            frames: list[tuple[str, dict[str, Any]]] = []
            for event in events:
                name, payload = _parse_summary(event.summary)
                frames.append(
                    (
                        name,
                        envelope(
                            run_id=run_id,
                            message_id=message_id or row.message_id or "",
                            seq=event.seq,
                            stage=event.stage,
                            payload=payload,
                            timestamp=ensure_utc(event.created_at),
                        ),
                    )
                )
            return EventLog.from_persisted(run_id, message_id or row.message_id or "", frames)

    def _upsert_messages(self, session: Session, run: RunRecord) -> None:
        user_id = synthetic_user_message_id(run.id)
        created = run.created_at or utc_now()
        rows = (
            (user_id, "user", run.question),
            (run.message_id, "assistant", run.answer_markdown or ""),
        )
        for message_id, sender, content in rows:
            if not message_id:
                continue
            message = session.get(Message, message_id)
            if message is None:
                session.add(
                    Message(
                        id=message_id,
                        conversation_id=run.conversation_id,
                        sender=sender,
                        content=content,
                        status=run.state,
                        run_id=run.id,
                        created_at=created,
                    )
                )
                continue
            message.conversation_id = run.conversation_id
            message.sender = sender
            message.content = content
            message.status = run.state
            message.run_id = run.id

    def _replace_events(self, session: Session, run: RunRecord, log: EventLog) -> None:
        session.execute(delete(AgentEvent).where(AgentEvent.run_id == run.id))
        for name, data in log.persistable():
            session.add(
                AgentEvent(
                    id=new_id("event"),
                    run_id=run.id,
                    stage=str(data.get("stage") or run.state),
                    summary=_summary_of(name, data),
                    seq=int(data["seq"]),
                    created_at=_parse_timestamp(str(data["timestamp"])),
                )
            )
