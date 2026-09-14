"""SQLAlchemy document fact stores (sqlite stand-in). Not GATE-P0 verified."""

from __future__ import annotations

from datetime import UTC, datetime

from pivot.db.documents import (
    SqlAlchemyChunkStore,
    SqlAlchemyDocumentStore,
    SqlAlchemyTaskStore,
    SqlAlchemyVersionStore,
)
from pivot.db.models import User
from pivot.documents.ports import ChunkRecord, DocumentRecord, TaskRecord, VersionRecord


def _seed_user(db_session) -> None:
    db_session.add(
        User(
            id="usr_admin",
            username="admin",
            password_hash="hash",
            role="admin",
            status="active",
        )
    )
    db_session.commit()


def test_M03_sqlalchemy_document_store_persists_spec_fields(db_session):
    _seed_user(db_session)
    store = SqlAlchemyDocumentStore(db_session)
    store.save(
        DocumentRecord(
            id="doc_policy",
            title="Attendance Policy",
            space="hr",
            created_by="usr_admin",
            classification="low",
            created_at=datetime(2026, 9, 10, 12, 0, tzinfo=UTC),
            tags=("leave", "hr"),
        )
    )
    loaded = store.get("doc_policy")
    assert loaded is not None
    assert loaded.title == "Attendance Policy"
    assert loaded.space == "hr"
    assert loaded.created_by == "usr_admin"
    assert loaded.classification == "low"
    assert loaded.tags == ("leave", "hr")
    assert loaded.deleted_at is None
    assert store.get("missing") is None
    active = store.list_active()
    assert [item.id for item in active] == ["doc_policy"]


def test_M03_sqlalchemy_version_store_roundtrip_and_sha(db_session):
    _seed_user(db_session)
    documents = SqlAlchemyDocumentStore(db_session)
    versions = SqlAlchemyVersionStore(db_session)
    documents.save(
        DocumentRecord(
            id="doc_policy",
            title="Attendance Policy",
            space="hr",
            created_by="usr_admin",
        )
    )
    versions.save(
        VersionRecord(
            id="ver_1",
            document_id="doc_policy",
            content_sha256="abc123",
            storage_key="quarantine/doc_policy/ver_1",
            state="uploaded",
            current=False,
        )
    )
    loaded = versions.get("ver_1")
    assert loaded is not None
    assert loaded.content_sha256 == "abc123"
    assert loaded.storage_key == "quarantine/doc_policy/ver_1"
    assert loaded.state == "uploaded"
    assert loaded.external_llm_allowed is False
    assert versions.find_by_sha("abc123") is not None
    assert versions.find_by_sha("missing") is None
    listed = versions.list_for_document("doc_policy")
    assert [item.id for item in listed] == ["ver_1"]
    loaded.state = "ready"
    loaded.current = True
    versions.save(loaded)
    again = versions.get("ver_1")
    assert again is not None
    assert again.state == "ready"
    assert again.current is True


def test_M03_sqlalchemy_version_store_persists_external_llm_allowed(db_session):
    _seed_user(db_session)
    documents = SqlAlchemyDocumentStore(db_session)
    versions = SqlAlchemyVersionStore(db_session)
    documents.save(
        DocumentRecord(
            id="doc_policy",
            title="Attendance Policy",
            space="hr",
            created_by="usr_admin",
        )
    )
    versions.save(
        VersionRecord(
            id="ver_llm",
            document_id="doc_policy",
            content_sha256="def456",
            storage_key="quarantine/doc_policy/ver_llm",
            state="uploaded",
            current=False,
            external_llm_allowed=True,
        )
    )
    loaded = versions.get("ver_llm")
    assert loaded is not None
    assert loaded.external_llm_allowed is True
    loaded.external_llm_allowed = False
    versions.save(loaded)
    again = versions.get("ver_llm")
    assert again is not None
    assert again.external_llm_allowed is False


def test_M03_sqlalchemy_chunk_and_task_roundtrip(db_session):
    _seed_user(db_session)
    documents = SqlAlchemyDocumentStore(db_session)
    versions = SqlAlchemyVersionStore(db_session)
    chunks = SqlAlchemyChunkStore(db_session)
    tasks = SqlAlchemyTaskStore(db_session)
    documents.save(
        DocumentRecord(
            id="doc_policy",
            title="Attendance Policy",
            space="hr",
            created_by="usr_admin",
        )
    )
    versions.save(
        VersionRecord(
            id="ver_1",
            document_id="doc_policy",
            content_sha256="abc123",
            storage_key="quarantine/doc_policy/ver_1",
            state="uploaded",
        )
    )
    chunks.add(
        ChunkRecord(
            id="chk_1",
            version_id="ver_1",
            text="Late arrival policy",
            text_hash="hash-1",
            published=False,
        )
    )
    tasks.save(
        TaskRecord(
            id="task_1",
            entity_id="ver_1",
            entity_type="document_version",
            attempt=1,
            state="queued",
        )
    )
    listed = chunks.list_for_version("ver_1")
    assert len(listed) == 1
    assert listed[0].text == "Late arrival policy"
    listed[0].published = True
    chunks.add(listed[0])
    assert chunks.list_for_version("ver_1")[0].published is True
    loaded = tasks.get("task_1")
    assert loaded is not None
    assert loaded.state == "queued"
    loaded.state = "started"
    tasks.save(loaded)
    assert tasks.get("task_1") is not None
    assert tasks.get("task_1").state == "started"
