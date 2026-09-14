from __future__ import annotations

import pytest
from pivot.auth.errors import AuthError


def test_FR_AUTH_003_refresh_issues_new_access_token(auth_service):
    login = auth_service.login("alice", "correct-password", request_id="req_login")
    refreshed = auth_service.refresh(login.refresh_token, request_id="req_refresh")
    assert refreshed.access_token != login.access_token
    assert refreshed.cookie.httponly is True
    principal = auth_service.authenticate(refreshed.access_token)
    assert principal.user_id == "usr_alice"


def test_FR_AUTH_003_logout_revokes_refresh_cookie(auth_service):
    login = auth_service.login("alice", "correct-password", request_id="req_login")
    cleared = auth_service.logout(login.refresh_token, request_id="req_logout")
    assert cleared.clears_cookie is True
    with pytest.raises(AuthError) as error:
        auth_service.refresh(login.refresh_token, request_id="req_after")
    assert error.value.code == "AUTH_INVALID_CREDENTIALS"


def test_FR_AUTH_003_disabled_user_tokens_fail_immediately(auth_service, users):
    login = auth_service.login("alice", "correct-password", request_id="req_login")
    auth_service.disable_user(
        actor_id="usr_admin",
        user_id="usr_alice",
        request_id="req_disable",
    )
    user = users.get_by_id("usr_alice")
    assert user is not None
    assert user.status == "disabled"
    assert user.token_version == 2
    with pytest.raises(AuthError) as access:
        auth_service.authenticate(login.access_token)
    with pytest.raises(AuthError) as refresh:
        auth_service.refresh(login.refresh_token, request_id="req_refresh")
    with pytest.raises(AuthError) as relogin:
        auth_service.login("alice", "correct-password", request_id="req_relogin")
    assert {access.value.code, refresh.value.code, relogin.value.code} == {
        "AUTH_INVALID_CREDENTIALS",
        "AUTH_FORBIDDEN",
    }


def test_FR_AUTH_002_disabled_user_login_does_not_reveal_status(auth_service):
    with pytest.raises(AuthError) as disabled:
        auth_service.login("disabled", "disabled-password", request_id="req_disabled")
    with pytest.raises(AuthError) as missing:
        auth_service.login("ghost", "x", request_id="req_ghost")
    assert disabled.value.code == missing.value.code == "AUTH_INVALID_CREDENTIALS"
    assert disabled.value.message == missing.value.message


def test_FR_AUTH_003_change_role_invalidates_tokens_and_audits(
    auth_service, users, audits
):
    login = auth_service.login("bob", "bob-password", request_id="req_login")
    updated = auth_service.change_role(
        actor_id="usr_admin",
        user_id="usr_bob",
        role="admin",
        request_id="req_role",
    )
    assert updated.role == "admin"
    assert users.get_by_id("usr_bob").role == "admin"
    assert users.get_by_id("usr_bob").token_version == 2
    with pytest.raises(AuthError):
        auth_service.authenticate(login.access_token)
    with pytest.raises(AuthError):
        auth_service.refresh(login.refresh_token, request_id="req_stale")
    later = auth_service.login("bob", "bob-password", request_id="req_again")
    principal = auth_service.authenticate(later.access_token)
    assert principal.role == "admin"
    assert any(
        event.action == "auth.role_change"
        and event.target == "usr_bob"
        and event.metadata.get("from") == "user"
        and event.metadata.get("to") == "admin"
        for event in audits.events
    )


def test_FR_AUTH_003_change_role_forbidden_for_user(auth_service):
    with pytest.raises(AuthError) as error:
        auth_service.change_role(
            actor_id="usr_alice",
            user_id="usr_bob",
            role="admin",
            request_id="req_user_role",
        )
    assert error.value.code == "AUTH_FORBIDDEN"


def test_FR_AUTH_003_change_role_unknown_user_is_not_found(auth_service):
    with pytest.raises(AuthError) as error:
        auth_service.change_role(
            actor_id="usr_admin",
            user_id="usr_missing",
            role="user",
            request_id="req_missing",
        )
    assert error.value.code == "RESOURCE_NOT_FOUND"
