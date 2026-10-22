"""ND-GAP-03: first-login password change persistence and enforcement.

sqlite stand-in over the real SQLAlchemy user directory; the migration
itself is exercised on real PostgreSQL by the db_pg suite. Not GATE-P0
verified.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

import pytest
from pivot.auth.errors import AuthError
from pivot.auth.ports import UserAccount
from pivot.auth.service import AuthService
from pivot.auth.tokens import TokenService
from pivot.db.users import SqlAlchemyUserDirectory
from pivot.http.memory import InMemoryResources
from pivot.security.rbac import AccessControl

NOW = datetime(2026, 10, 22, 4, 0, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return NOW


class _Hasher:
    def hash(self, password: str) -> str:
        salt = secrets.token_hex(8)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), 10_000
        ).hex()
        return f"{salt}${digest}"

    def verify(self, password: str, password_hash: str) -> bool:
        salt, digest = password_hash.split("$", 1)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), 10_000
        ).hex()
        return secrets.compare_digest(candidate, digest)


class _RefreshStore:
    def __init__(self) -> None:
        self._items = {}

    def save(self, session) -> None:
        self._items[session.token_hash] = session

    def get(self, token_hash):
        return self._items.get(token_hash)

    def revoke(self, token_hash) -> None:
        self._items.pop(token_hash, None)

    def revoke_user(self, user_id) -> None:
        self._items = {k: v for k, v in self._items.items() if v.user_id != user_id}


class _Audits:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


class _Attempts:
    def record_failure(self, username) -> int:
        return 1

    def reset(self, username) -> None:
        return None

    def is_blocked(self, username) -> bool:
        return False


def _service(db_session) -> AuthService:
    clock = _Clock()
    return AuthService(
        users=SqlAlchemyUserDirectory(db_session),
        hasher=_Hasher(),
        tokens=TokenService(secret="gap03-test-secret", access_ttl=3600, clock=clock),
        refresh_tokens=_RefreshStore(),
        audits=_Audits(),
        attempts=_Attempts(),
        access=AccessControl(InMemoryResources()),
        clock=clock,
        access_ttl=3600,
        refresh_ttl=7200,
    )


def _seed_admin(db_session) -> None:
    hasher = _Hasher()
    SqlAlchemyUserDirectory(db_session).save(
        UserAccount(
            id="usr_admin",
            username="admin",
            password_hash=hasher.hash("admin-password"),
            role="admin",
            status="active",
            token_version=1,
            must_change_password=False,
            created_at=NOW,
            updated_at=NOW,
        )
    )


def test_FR_AUTH_004_first_change_required_after_restart(db_session):
    _seed_admin(db_session)
    first = _service(db_session)
    created = first.create_user("usr_admin", "alice", "initial-password", "req_1")

    # The flag must be read back from the persisted row, not from memory:
    # a fresh directory and service over the same database stand in for a
    # restart or a second instance.
    persisted = SqlAlchemyUserDirectory(db_session).get_by_id(created.id)
    assert persisted is not None
    assert persisted.must_change_password is True

    second = _service(db_session)
    login = second.login("alice", "initial-password", "req_2")
    assert login.must_change_password is True
    assert login.to_login_success()["must_change_password"] is True
    with pytest.raises(AuthError) as blocked:
        second.authenticate(login.access_token, "req_3")
    assert blocked.value.code == "AUTH_PASSWORD_CHANGE_REQUIRED"

    # The change-password path itself stays reachable with the flagged
    # token; afterwards a fresh login is fully usable.
    second.change_password(login.access_token, "initial-password", "new-password-1", "req_4")
    assert SqlAlchemyUserDirectory(db_session).get_by_id(created.id).must_change_password is False
    relogin = second.login("alice", "new-password-1", "req_5")
    assert relogin.must_change_password is False
    principal = second.authenticate(relogin.access_token, "req_6")
    assert principal.username == "alice"

    # An admin reset re-arms the flag and the enforcement.
    second.reset_password("usr_admin", created.id, "reset-password", "req_7")
    assert SqlAlchemyUserDirectory(db_session).get_by_id(created.id).must_change_password is True
    reset_login = second.login("alice", "reset-password", "req_8")
    with pytest.raises(AuthError) as blocked_again:
        second.authenticate(reset_login.access_token, "req_9")
    assert blocked_again.value.code == "AUTH_PASSWORD_CHANGE_REQUIRED"


def test_FR_AUTH_003_reset_revokes_existing_sessions(db_session):
    _seed_admin(db_session)
    service = _service(db_session)
    created = service.create_user("usr_admin", "carol", "initial-password", "req_1")
    service.change_password(
        service.login("carol", "initial-password", "req_2").access_token,
        "initial-password",
        "carol-password-1",
        "req_3",
    )
    live = service.login("carol", "carol-password-1", "req_4")
    assert service.authenticate(live.access_token, "req_5").username == "carol"

    service.reset_password("usr_admin", created.id, "reset-password", "req_6")

    # Old access tokens die on the token_version check and the stored
    # refresh session was revoked by the rotation.
    with pytest.raises(AuthError) as stale:
        service.authenticate(live.access_token, "req_7")
    assert stale.value.code == "AUTH_INVALID_CREDENTIALS"
    with pytest.raises(AuthError):
        service.refresh(live.refresh_token, "req_8")
