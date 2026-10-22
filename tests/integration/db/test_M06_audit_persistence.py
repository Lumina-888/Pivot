"""ND-GAP-02: persistent audit wiring (sqlite stand-in). Not GATE-P0 verified."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pivot.audit.errors import AuditError
from pivot.audit.models import AuditEventRecord
from pivot.audit.ports import Actor
from pivot.audit.service import AuditService
from pivot.auth.ports import AuditEventDraft as AuthAuditDraft
from pivot.db.audit import (
    SqlAlchemyAuditStore,
    SqlAlchemyAuthAuditSink,
    SqlAlchemyDocumentAuditSink,
)
from pivot.db.models import AuditEvent
from pivot.documents.ports import AuditDraft as DocumentAuditDraft


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 10, 22, 3, 0, tzinfo=UTC)


def _record(event_id: str = "audit_1") -> AuditEventRecord:
    return AuditEventRecord(
        id=event_id,
        actor="usr_admin",
        action="auth.login",
        target="usr_admin",
        result="ok",
        request_id="req_1",
        run_id=None,
        metadata={},
        created_at=datetime(2026, 10, 22, 3, 0, tzinfo=UTC),
    )


def test_FR_AUDIT_001_runtime_events_survive_restart(db_session):
    store = SqlAlchemyAuditStore(db_session)
    service = AuditService(store, _Clock())
    service.record(
        actor="usr_admin",
        action="auth.role_change",
        target="usr_alice",
        result="ok",
        request_id="req_1",
    )
    service.record_qa(
        actor="usr_alice",
        request_id="req_2",
        run_id="run_1",
        state="completed",
        hit_documents=("doc_1",),
        citations=("doc_1",),
        model="deepseek-flash",
        prompt_version="pv1",
        role_card_version=None,
        retrieval_params=None,
        index_generation="gen1",
        retry_count=0,
        duration_ms=12,
    )
    SqlAlchemyAuthAuditSink(store).emit(
        AuthAuditDraft(
            actor="usr_alice", action="login", target="usr_alice", result="ok", request_id="req_3"
        )
    )
    SqlAlchemyDocumentAuditSink(store).emit(
        DocumentAuditDraft(
            actor="usr_alice",
            action="document.upload",
            target="ver_1",
            result="ok",
            request_id="req_4",
        )
    )

    # Fresh store and service instances over the same database stand in
    # for a process restart: every runtime stream must still be readable.
    fresh_store = SqlAlchemyAuditStore(db_session)
    actions = [event.action for event in fresh_store.list()]
    assert sorted(actions) == ["auth.login", "auth.role_change", "document.upload", "qa.run"]
    assert fresh_store.query(request_id="req_3")[0].actor == "usr_alice"
    assert fresh_store.query(run_id="run_1")[0].action == "qa.run"


def test_FR_AUDIT_003_run_replay_has_provider_versions(db_session):
    store = SqlAlchemyAuditStore(db_session)
    service = AuditService(store, _Clock())
    service.record_qa(
        actor="usr_alice",
        request_id="req_2",
        run_id="run_9",
        state="completed",
        hit_documents=("doc_1",),
        citations=("doc_1",),
        model="deepseek-flash",
        prompt_version="pv1",
        role_card_version=None,
        retrieval_params=None,
        index_generation="gen1",
        retry_count=1,
        duration_ms=42,
    )

    fresh = AuditService(SqlAlchemyAuditStore(db_session), _Clock())
    admin = Actor(user_id="usr_admin", username="admin", role="admin")
    replayed = fresh.replay(admin, "req_replay", run_id="run_9")
    assert replayed["model"] == "deepseek-flash"
    assert replayed["state"] == "completed"
    assert replayed["run_id"] == "run_9"


def test_FR_AUDIT_002_application_role_cannot_update_delete(db_session):
    store = SqlAlchemyAuditStore(db_session)
    store.append(_record())

    row = db_session.get(AuditEvent, "audit_1")
    assert row is not None
    row.actor = "mallory"
    with pytest.raises(ValueError):
        db_session.flush()
    db_session.rollback()

    row = db_session.get(AuditEvent, "audit_1")
    assert row is not None
    db_session.delete(row)
    with pytest.raises(ValueError):
        db_session.flush()
    db_session.rollback()

    assert store.get("audit_1") is not None


def test_FR_AUDIT_002_sql_store_rejects_duplicate_append(db_session):
    store = SqlAlchemyAuditStore(db_session)
    store.append(_record())
    with pytest.raises(AuditError):
        store.append(_record())
