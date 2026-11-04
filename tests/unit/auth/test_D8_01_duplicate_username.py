"""D8-01: duplicate username must return a SPEC §5.1 envelope, not a 500.

The 2026-11-04 retest found POST /api/v1/admin/users with an existing
username returning 500 with a non-envelope body, while the server log
printed the failed SQL statement and its parameters, including the
argon2id password hash. The duplicate must surface as
AUTH_USERNAME_TAKEN (409) and the raw integrity failure must never
escape the service layer (its string embeds the statement parameters).
"""

from __future__ import annotations

import pytest
from fakes import InMemoryUserDirectory
from pivot.auth.errors import AuthError
from pivot.auth.http import _STATUS
from pivot.auth.ports import DuplicateUsernameError
from pivot.auth.service import AuthService
from pivot.auth.tokens import TokenService
from pivot.security.rbac import AccessControl


def test_D8_01_duplicate_username_returns_409_envelope(auth_service, users):
    with pytest.raises(AuthError) as error:
        auth_service.create_user(
            actor_id="usr_admin",
            username="alice",
            initial_password="AnotherPass1",
            request_id="req_dup",
        )
    assert error.value.code == "AUTH_USERNAME_TAKEN"
    assert error.value.request_id == "req_dup"
    assert _STATUS["AUTH_USERNAME_TAKEN"] == 409
    # The pre-check must not hash-and-store anything: still one alice.
    assert [user for user in users.list() if user.username == "alice"]


class _RacingDirectory(InMemoryUserDirectory):
    """Simulates the TOCTOU gap: no pre-check hit, but save collides."""

    def get_by_username(self, username: str):
        # Only the admin lookup may resolve; every create pre-check
        # misses, so the collision surfaces at save time.
        if username == "admin":
            return super().get_by_username(username)
        return None

    def save(self, user):
        raise DuplicateUsernameError(user.username)


def test_D8_01_raced_unique_violation_maps_to_409(
    users, hasher, clock, refresh_store, audits, attempts, resources
):
    tokens = TokenService(secret="test-secret", access_ttl=60, clock=clock)
    service = AuthService(
        users=_RacingDirectory(list(users.list())),
        hasher=hasher,
        tokens=tokens,
        refresh_tokens=refresh_store,
        audits=audits,
        attempts=attempts,
        access=AccessControl(resources),
        clock=clock,
        access_ttl=60,
        refresh_ttl=3600,
    )
    with pytest.raises(AuthError) as error:
        service.create_user(
            actor_id="usr_admin",
            username="carol",
            initial_password="RacePass1",
            request_id="req_race",
        )
    assert error.value.code == "AUTH_USERNAME_TAKEN"
    assert error.value.request_id == "req_race"
