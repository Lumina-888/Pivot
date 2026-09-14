"""SQLAlchemy export task store (sqlite stand-in). Not GATE-P0 verified."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pivot.db.exports import SqlAlchemyExportRepository
from pivot.db.models import User
from pivot.exports.models import ExportRecord


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


def _record(**overrides: object) -> ExportRecord:
    now = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    values: dict[str, object] = {
        "id": "exp_policy",
        "owner_id": "usr_admin",
        "source_type": "conversation",
        "source_id": "conv_admin",
        "format": "markdown",
        "state": "ready",
        "expires_at": now + timedelta(hours=1),
        "created_at": now,
        "filename": "policy.md",
        "storage_key": "exports/exp_policy/policy.md",
    }
    values.update(overrides)
    return ExportRecord(**values)  # type: ignore[arg-type]


def test_M03_sqlalchemy_export_repository_persists_spec_fields(db_session):
    _seed_user(db_session)
    store = SqlAlchemyExportRepository(db_session)
    store.add(_record())

    loaded = store.get("exp_policy")
    assert loaded is not None
    assert loaded.id == "exp_policy"
    assert loaded.owner_id == "usr_admin"
    assert loaded.source_type == "conversation"
    assert loaded.source_id == "conv_admin"
    assert loaded.format == "markdown"
    assert loaded.state == "ready"
    assert loaded.storage_key == "exports/exp_policy/policy.md"
    assert loaded.expires_at == datetime(2026, 9, 14, 9, 0, tzinfo=UTC)
    assert loaded.created_at == datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    assert loaded.filename == "policy.md"
    assert store.get("missing") is None


def test_M03_sqlalchemy_export_repository_save_updates_state(db_session):
    _seed_user(db_session)
    store = SqlAlchemyExportRepository(db_session)
    store.add(_record(state="requested", storage_key=None, filename="export.md"))
    loaded = store.get("exp_policy")
    assert loaded is not None
    loaded.state = "expired"
    loaded.storage_key = "exports/exp_policy/policy.md"
    store.save(loaded)
    again = store.get("exp_policy")
    assert again is not None
    assert again.state == "expired"
    assert again.storage_key == "exports/exp_policy/policy.md"
    with pytest.raises(ValueError, match="duplicate export id"):
        store.add(_record())
