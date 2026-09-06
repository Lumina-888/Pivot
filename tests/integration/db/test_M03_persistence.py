import pytest


def test_M03_uow_rolls_back_on_exception(db_session):
    from pivot.db.models import User
    from pivot.db.uow import UnitOfWork

    with pytest.raises(RuntimeError), UnitOfWork(db_session) as unit:
        unit.session.add(
            User(
                id="usr_rollback",
                username="rollback",
                password_hash="hash",
                role="user",
                status="active",
            )
        )
        raise RuntimeError("abort")

    assert db_session.get(User, "usr_rollback") is None


def test_M03_audit_is_append_only(db_session):
    from pivot.db.models import AuditEvent
    from pivot.db.repositories.protocols import AuditEventRepository

    public = set(dir(AuditEventRepository))
    assert not {"update", "delete", "remove"}.intersection(public)
    assert hasattr(AuditEvent, "__tablename__")

    event = AuditEvent(
        id="aud_1", actor="system", action="test", target="target", result="ok"
    )
    db_session.add(event)
    db_session.commit()
    event.result = "changed"
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()
    db_session.delete(event)
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()


def test_M03_qdrant_payload_traces_version_and_chunk():
    from pivot.storage.adapters.qdrant import build_payload, validate_payload

    payload = build_payload(version_id="ver_1", chunk_id="chk_1", text_hash="hash")
    assert payload["version_id"] == "ver_1"
    assert payload["chunk_id"] == "chk_1"
    assert validate_payload(payload)
    with pytest.raises(ValueError):
        validate_payload({"version_id": "ver_1"})


def test_M03_redis_is_not_business_fact_store():
    from pivot.storage.protocols import CacheStore, QueueStore

    assert hasattr(CacheStore, "get")
    assert hasattr(QueueStore, "enqueue")
    public_names = set(dir(CacheStore)) | set(dir(QueueStore))
    assert not {"save_user", "save_document", "save_run", "write_fact"}.intersection(
        public_names
    )
    assert "business fact" in (CacheStore.__doc__ or "").lower()


def test_M03_uow_commits_successfully(db_session):
    from pivot.db.models import User
    from pivot.db.uow import UnitOfWork

    with UnitOfWork(db_session) as unit:
        unit.session.add(
            User(
                id="usr_commit",
                username="commit",
                password_hash="hash",
                role="user",
                status="active",
            )
        )
    assert db_session.get(User, "usr_commit") is not None
