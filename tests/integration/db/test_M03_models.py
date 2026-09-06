from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


def test_M03_business_models_have_expected_fact_fields(db_session):
    from pivot.db.models import (
        AuditEvent,
        CeleryTask,
        Chunk,
        Citation,
        Claim,
        Conversation,
        Document,
        DocumentVersion,
        ExportTask,
        IndexGeneration,
        Message,
        ParseError,
        ProviderCall,
        Run,
        User,
    )

    expected = {
        User: {"id", "username", "password_hash", "role", "status", "token_version"},
        Document: {"id", "title", "space", "classification", "created_by"},
        DocumentVersion: {
            "id",
            "document_id",
            "content_sha256",
            "storage_key",
            "state",
            "current",
        },
        Chunk: {
            "id",
            "version_id",
            "text",
            "text_hash",
            "locator",
            "published",
            "index_generation_id",
        },
        IndexGeneration: {"id", "status", "dimension", "embedding_model_version"},
        Conversation: {"id", "owner_id", "title", "scope_type", "scope_document_id"},
        Message: {"id", "conversation_id", "sender", "content", "status", "run_id"},
        Run: {
            "id",
            "conversation_id",
            "message_id",
            "question",
            "idempotency_key",
            "state",
        },
        Claim: {"id", "run_id", "text", "support", "confidence"},
        Citation: {
            "id",
            "run_id",
            "claim_id",
            "document_id",
            "version_id",
            "chunk_id",
            "locator",
        },
        ExportTask: {"id", "owner_id", "source_type", "source_id", "format", "state"},
        CeleryTask: {"id", "entity_type", "entity_id", "attempt", "state", "retryable"},
        ParseError: {"id", "version_id", "code", "message_summary", "retryable"},
        ProviderCall: {"id", "provider", "model", "operation", "status", "run_id"},
        AuditEvent: {"id", "actor", "action", "target", "result", "request_id"},
    }
    for model, fields in expected.items():
        assert fields <= {column.key for column in inspect(model).columns}, (
            model.__name__
        )


def _user():
    from pivot.db.models import User

    return User(
        id="usr_a", username="alice", password_hash="hash", role="user", status="active"
    )


def _document():
    from pivot.db.models import Document

    return Document(
        id="doc_a",
        title="Policy",
        space="shared",
        classification="low",
        created_by="usr_a",
    )


def test_M03_current_version_constraint_allows_one_current(db_session):
    from pivot.db.models import DocumentVersion

    document = _document()
    db_session.add_all([_user(), document])
    db_session.flush()
    version = DocumentVersion(
        id="ver_a",
        document_id=document.id,
        version_label="v1",
        content_sha256="sha-a",
        storage_key="documents/doc_a/v1",
        state="ready",
        current=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(version)
    db_session.commit()
    assert db_session.get(DocumentVersion, "ver_a").current is True


def test_M03_current_version_constraint_rejects_duplicate_current(db_session):
    from pivot.db.models import DocumentVersion

    document = _document()
    db_session.add_all([_user(), document])
    db_session.flush()
    db_session.add_all(
        [
            DocumentVersion(
                id="ver_a",
                document_id=document.id,
                version_label="v1",
                content_sha256="sha-a",
                storage_key="documents/doc_a/v1",
                state="ready",
                current=True,
            ),
            DocumentVersion(
                id="ver_b",
                document_id=document.id,
                version_label="v2",
                content_sha256="sha-b",
                storage_key="documents/doc_a/v2",
                state="ready",
                current=True,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_M03_idempotency_keys_are_unique_in_business_scope(db_session):
    from pivot.db.models import Conversation, Run

    db_session.add(_user())
    db_session.add(
        Conversation(id="conv_a", owner_id="usr_a", title="A", scope_type="global")
    )
    db_session.flush()
    db_session.add_all(
        [
            Run(
                id="run_a",
                conversation_id="conv_a",
                question="Q",
                idempotency_key="key-a",
                state="received",
            ),
            Run(
                id="run_b",
                conversation_id="conv_a",
                question="Q2",
                idempotency_key="key-a",
                state="received",
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
