"""SQLAlchemy refresh token store (sqlite stand-in). Not GATE-P0 verified."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pivot.auth.ports import RefreshSession
from pivot.auth.tokens import hash_refresh_token
from pivot.db.models import RefreshToken, User
from pivot.db.refresh import SqlAlchemyRefreshTokenStore


def _seed_user(db_session, user_id: str = "usr_alice") -> None:
    db_session.add(
        User(
            id=user_id,
            username=user_id.removeprefix("usr_"),
            password_hash="hash",
            role="user",
            status="active",
        )
    )
    db_session.commit()


def _session(**overrides: object) -> RefreshSession:
    now = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    values: dict[str, object] = {
        "token_hash": hash_refresh_token("raw-refresh-token"),
        "user_id": "usr_alice",
        "token_version": 1,
        "expires_at": now + timedelta(hours=1),
        "revoked": False,
    }
    values.update(overrides)
    return RefreshSession(**values)  # type: ignore[arg-type]


def test_M03_sqlalchemy_refresh_store_persists_hashed_session(db_session):
    _seed_user(db_session)
    store = SqlAlchemyRefreshTokenStore(db_session)
    raw = "raw-refresh-token"
    token_hash = hash_refresh_token(raw)
    store.save(_session(token_hash=token_hash))

    loaded = store.get(token_hash)
    assert loaded is not None
    assert loaded.token_hash == token_hash
    assert loaded.user_id == "usr_alice"
    assert loaded.token_version == 1
    assert loaded.expires_at == datetime(2026, 9, 14, 9, 0, tzinfo=UTC)
    assert loaded.revoked is False
    row = db_session.get(RefreshToken, token_hash)
    assert row is not None
    assert row.token_hash == token_hash
    assert raw not in row.token_hash
    assert store.get("missing") is None


def test_M03_sqlalchemy_refresh_store_revoke_and_revoke_user(db_session):
    _seed_user(db_session)
    _seed_user(db_session, "usr_bob")
    store = SqlAlchemyRefreshTokenStore(db_session)
    alice_a = hash_refresh_token("alice-a")
    alice_b = hash_refresh_token("alice-b")
    bob = hash_refresh_token("bob-a")
    store.save(_session(token_hash=alice_a))
    store.save(_session(token_hash=alice_b))
    store.save(_session(token_hash=bob, user_id="usr_bob"))

    store.revoke(alice_a)
    revoked = store.get(alice_a)
    assert revoked is not None
    assert revoked.revoked is True
    assert store.get(alice_b) is not None
    assert store.get(alice_b).revoked is False

    store.revoke_user("usr_alice")
    assert store.get(alice_a).revoked is True
    assert store.get(alice_b).revoked is True
    remaining = store.get(bob)
    assert remaining is not None
    assert remaining.revoked is False
    assert remaining.user_id == "usr_bob"
