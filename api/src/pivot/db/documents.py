"""SQLAlchemy document fact stores backed by the PostgreSQL fact model."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pivot.db.models import CeleryTask, Chunk, Document, DocumentVersion
from pivot.db.uow import UnitOfWork
from pivot.documents.ports import ChunkRecord, DocumentRecord, TaskRecord, VersionRecord
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


def _tags_text(tags: tuple[str, ...]) -> str:
    return json.dumps(list(tags), ensure_ascii=False)


def _tags_tuple(raw: object) -> tuple[str, ...]:
    if raw in (None, ""):
        return ()
    if isinstance(raw, (list, tuple)):
        return tuple(str(item) for item in raw)
    loaded = json.loads(str(raw))
    if not isinstance(loaded, list):
        raise ValueError("document tags must be a JSON list")
    return tuple(str(item) for item in loaded)


def _to_document(row: Document) -> DocumentRecord:
    return DocumentRecord(
        id=row.id,
        title=row.title,
        space=row.space,
        created_by=row.created_by,
        deleted_at=row.deleted_at,
        classification=row.classification,
        created_at=row.created_at,
        tags=_tags_tuple(row.tags),
    )


def _to_version(row: DocumentVersion) -> VersionRecord:
    return VersionRecord(
        id=row.id,
        document_id=row.document_id,
        content_sha256=row.content_sha256,
        storage_key=row.storage_key,
        state=row.state,
        current=row.current,
        external_llm_allowed=row.external_llm_allowed,
    )


def _to_chunk(row: Chunk) -> ChunkRecord:
    return ChunkRecord(
        id=row.id,
        version_id=row.version_id,
        text=row.text,
        text_hash=row.text_hash,
        published=row.published,
    )


def _to_task(row: CeleryTask) -> TaskRecord:
    return TaskRecord(
        id=row.id,
        entity_id=row.entity_id,
        entity_type=row.entity_type,
        attempt=row.attempt,
        state=row.state,
        retryable=row.retryable,
        error_code=row.error_code,
    )


class _SessionBound:
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


class SqlAlchemyDocumentStore(_SessionBound):
    def get(self, document_id: str) -> DocumentRecord | None:
        with self._scope() as session:
            row = session.get(Document, document_id)
            return _to_document(row) if row is not None else None

    def save(self, document: DocumentRecord) -> None:
        if not document.id or not document.created_by:
            raise ValueError("documents require a non-empty id and created_by")
        with self._scope() as session:
            with UnitOfWork(session):
                row = session.get(Document, document.id)
                if row is None:
                    session.add(
                        Document(
                            id=document.id,
                            title=document.title,
                            space=document.space,
                            tags=_tags_text(document.tags),
                            classification=document.classification,
                            created_by=document.created_by,
                            deleted_at=document.deleted_at,
                            created_at=document.created_at or utc_now(),
                            updated_at=utc_now(),
                        )
                    )
                    return
                row.title = document.title
                row.space = document.space
                row.tags = _tags_text(document.tags)
                row.classification = document.classification
                row.created_by = document.created_by
                row.deleted_at = document.deleted_at
                row.updated_at = utc_now()

    def list_active(self) -> tuple[DocumentRecord, ...]:
        with self._scope() as session:
            rows = session.scalars(
                select(Document).order_by(Document.created_at, Document.id)
            ).all()
            return tuple(_to_document(row) for row in rows)


class SqlAlchemyVersionStore(_SessionBound):
    def get(self, version_id: str) -> VersionRecord | None:
        with self._scope() as session:
            row = session.get(DocumentVersion, version_id)
            return _to_version(row) if row is not None else None

    def save(self, version: VersionRecord) -> None:
        if not version.id or not version.document_id:
            raise ValueError("versions require a non-empty id and document_id")
        with self._scope() as session:
            with UnitOfWork(session):
                row = session.get(DocumentVersion, version.id)
                if row is None:
                    session.add(
                        DocumentVersion(
                            id=version.id,
                            document_id=version.document_id,
                            version_label=version.id,
                            content_sha256=version.content_sha256,
                            storage_key=version.storage_key,
                            state=version.state,
                            current=version.current,
                            external_llm_allowed=version.external_llm_allowed,
                            created_at=utc_now(),
                        )
                    )
                    return
                row.document_id = version.document_id
                row.content_sha256 = version.content_sha256
                row.storage_key = version.storage_key
                row.state = version.state
                row.current = version.current
                row.external_llm_allowed = version.external_llm_allowed

    def find_by_sha(self, content_sha256: str) -> VersionRecord | None:
        with self._scope() as session:
            row = session.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.content_sha256 == content_sha256
                )
            )
            return _to_version(row) if row is not None else None

    def find_by_idempotency(self, key: str) -> VersionRecord | None:
        return None

    def list_for_document(self, document_id: str) -> tuple[VersionRecord, ...]:
        with self._scope() as session:
            rows = session.scalars(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.created_at, DocumentVersion.id)
            ).all()
            return tuple(_to_version(row) for row in rows)


class SqlAlchemyChunkStore(_SessionBound):
    def add(self, chunk: ChunkRecord) -> None:
        if not chunk.id or not chunk.version_id:
            raise ValueError("chunks require a non-empty id and version_id")
        with self._scope() as session:
            with UnitOfWork(session):
                row = session.get(Chunk, chunk.id)
                if row is None:
                    session.add(
                        Chunk(
                            id=chunk.id,
                            version_id=chunk.version_id,
                            text=chunk.text,
                            text_hash=chunk.text_hash,
                            published=chunk.published,
                            created_at=utc_now(),
                        )
                    )
                    return
                row.version_id = chunk.version_id
                row.text = chunk.text
                row.text_hash = chunk.text_hash
                row.published = chunk.published

    def list_for_version(self, version_id: str) -> tuple[ChunkRecord, ...]:
        with self._scope() as session:
            rows = session.scalars(
                select(Chunk)
                .where(Chunk.version_id == version_id)
                .order_by(Chunk.created_at, Chunk.id)
            ).all()
            return tuple(_to_chunk(row) for row in rows)


class SqlAlchemyTaskStore(_SessionBound):
    def get(self, task_id: str) -> TaskRecord | None:
        with self._scope() as session:
            row = session.get(CeleryTask, task_id)
            return _to_task(row) if row is not None else None

    def save(self, task: TaskRecord) -> None:
        if not task.id or not task.entity_id:
            raise ValueError("tasks require a non-empty id and entity_id")
        with self._scope() as session:
            with UnitOfWork(session):
                row = session.get(CeleryTask, task.id)
                if row is None:
                    session.add(
                        CeleryTask(
                            id=task.id,
                            entity_type=task.entity_type,
                            entity_id=task.entity_id,
                            attempt=task.attempt,
                            state=task.state,
                            retryable=task.retryable,
                            error_code=task.error_code,
                            created_at=utc_now(),
                        )
                    )
                    return
                row.entity_type = task.entity_type
                row.entity_id = task.entity_id
                row.attempt = task.attempt
                row.state = task.state
                row.retryable = task.retryable
                row.error_code = task.error_code
