"""SQLAlchemy export task store backed by the PostgreSQL fact model."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from pivot.db.models import ExportTask
from pivot.db.uow import UnitOfWork
from pivot.exports.models import ExportRecord
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


def _filename(row: ExportTask) -> str:
    if row.storage_key:
        name = row.storage_key.replace("\\", "/").rsplit("/", 1)[-1]
        if name:
            return name
    ext = ".md" if row.format == "markdown" else f".{row.format}"
    return f"export{ext}"


def _content_type(fmt: str) -> str | None:
    if fmt == "markdown":
        return "text/markdown; charset=utf-8"
    if fmt == "docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return None


def _to_record(row: ExportTask) -> ExportRecord:
    created_at = ensure_utc(row.created_at)
    expires_at = ensure_utc(row.expires_at) if row.expires_at is not None else created_at
    return ExportRecord(
        id=row.id,
        owner_id=row.owner_id,
        source_type=row.source_type,
        source_id=row.source_id,
        format=row.format,
        state=row.state,
        expires_at=expires_at,
        created_at=created_at,
        filename=_filename(row),
        storage_key=row.storage_key,
        content_type=_content_type(row.format),
    )


def _apply(row: ExportTask, record: ExportRecord) -> None:
    row.owner_id = record.owner_id
    row.source_type = record.source_type
    row.source_id = record.source_id
    row.format = record.format
    row.state = record.state
    row.storage_key = record.storage_key
    row.expires_at = record.expires_at
    row.created_at = record.created_at


class SqlAlchemyExportRepository:
    """ExportRepository that reads and writes the SQLAlchemy ExportTask table."""

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

    def add(self, record: ExportRecord) -> None:
        if not record.id or not record.owner_id:
            raise ValueError("exports require a non-empty id and owner_id")
        with self._scope() as session:
            with UnitOfWork(session):
                if session.get(ExportTask, record.id) is not None:
                    raise ValueError(f"duplicate export id: {record.id}")
                session.add(
                    ExportTask(
                        id=record.id,
                        owner_id=record.owner_id,
                        source_type=record.source_type,
                        source_id=record.source_id,
                        format=record.format,
                        state=record.state,
                        storage_key=record.storage_key,
                        expires_at=record.expires_at,
                        created_at=record.created_at or utc_now(),
                    )
                )

    def get(self, export_id: str) -> ExportRecord | None:
        with self._scope() as session:
            row = session.get(ExportTask, export_id)
            return _to_record(row) if row is not None else None

    def save(self, record: ExportRecord) -> None:
        if not record.id or not record.owner_id:
            raise ValueError("exports require a non-empty id and owner_id")
        with self._scope() as session:
            with UnitOfWork(session):
                row = session.get(ExportTask, record.id)
                if row is None:
                    session.add(
                        ExportTask(
                            id=record.id,
                            owner_id=record.owner_id,
                            source_type=record.source_type,
                            source_id=record.source_id,
                            format=record.format,
                            state=record.state,
                            storage_key=record.storage_key,
                            expires_at=record.expires_at,
                            created_at=record.created_at or utc_now(),
                        )
                    )
                    return
                _apply(row, record)
