"""SQLAlchemy UserDirectory against the PostgreSQL fact model (sqlite stand-in)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pivot.auth.ports import UserAccount
from pivot.db.models import User
from pivot.db.users import SqlAlchemyUserDirectory
from sqlalchemy.exc import IntegrityError


def _account(**overrides: object) -> UserAccount:
    values: dict[str, object] = {
        "id": "usr_alice",
        "username": "alice",
        "password_hash": "$argon2id$v=19$m=8,t=1,p=1$c2FsdHNhbHQ$hash",
        "role": "user",
        "status": "active",
        "token_version": 1,
        "must_change_password": True,
        "created_at": datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return UserAccount(**values)  # type: ignore[arg-type]


def _directory(db_session) -> SqlAlchemyUserDirectory:
    return SqlAlchemyUserDirectory(db_session)


def test_M03_sqlalchemy_user_directory_persists_spec_user_fields(db_session):
    directory = _directory(db_session)
    directory.save(_account())

    loaded = directory.get_by_id("usr_alice")
    assert loaded is not None
    assert loaded.username == "alice"
    assert loaded.password_hash.startswith("$argon2id$")
    assert loaded.role == "user"
    assert loaded.status == "active"
    assert loaded.token_version == 1
    assert loaded.must_change_password is False

    row = db_session.get(User, "usr_alice")
    assert row is not None
    assert row.username == "alice"
    assert row.password_hash == loaded.password_hash
    assert "must_change_password" not in {column.key for column in User.__table__.columns}


def test_M03_sqlalchemy_user_directory_get_by_username(db_session):
    directory = _directory(db_session)
    directory.save(_account())
    assert directory.get_by_username("alice") is not None
    assert directory.get_by_username("missing") is None
    assert directory.get_by_id("missing") is None


def test_M03_sqlalchemy_user_directory_save_updates_same_id(db_session):
    directory = _directory(db_session)
    directory.save(_account())
    directory.save(
        _account(
            password_hash="$argon2id$v=19$m=8,t=1,p=1$c2FsdHNhbHQ$rotated",
            status="disabled",
            token_version=2,
        )
    )
    loaded = directory.get_by_id("usr_alice")
    assert loaded is not None
    assert loaded.password_hash.endswith("rotated")
    assert loaded.status == "disabled"
    assert loaded.token_version == 2
    assert len(tuple(directory.list())) == 1


def test_M03_sqlalchemy_user_directory_rejects_duplicate_username(db_session):
    directory = _directory(db_session)
    directory.save(_account())
    with pytest.raises(IntegrityError):
        directory.save(_account(id="usr_alice_2"))
