from __future__ import annotations

import pytest
from pivot.auth.errors import AuthError


def test_FR_AUTH_004_admin_creates_user_without_logging_password(auth_service, hasher, audits):
    created = auth_service.create_user(
        actor_id="usr_admin",
        username="carol",
        initial_password="InitialPass1",
        request_id="req_create",
    )
    assert created.username == "carol"
    assert created.role == "user"
    assert created.status == "active"
    assert created.initial_password == "InitialPass1"
    assert hasher.verify("InitialPass1", created.password_hash)
    assert "InitialPass1" not in created.password_hash
    assert all("InitialPass1" not in event.target for event in audits.events)
    assert all(
        event.metadata.get("password") is None and "InitialPass1" not in str(event.metadata)
        for event in audits.events
    )


def test_FR_AUTH_004_change_password_invalidates_old_refresh(auth_service):
    login = auth_service.login("alice", "correct-password", request_id="req_login")
    auth_service.change_password(
        access_token=login.access_token,
        current_password="correct-password",
        new_password="NewPassword9",
        request_id="req_change",
    )
    with pytest.raises(AuthError):
        auth_service.login("alice", "correct-password", request_id="req_old")
    later = auth_service.login("alice", "NewPassword9", request_id="req_new")
    assert later.access_token
    with pytest.raises(AuthError):
        auth_service.refresh(login.refresh_token, request_id="req_stale")


def test_FR_AUTH_004_reset_password_increments_token_version(auth_service, users):
    login = auth_service.login("bob", "bob-password", request_id="req_login")
    reset = auth_service.reset_password(
        actor_id="usr_admin",
        user_id="usr_bob",
        new_password="ResetPass12",
        request_id="req_reset",
    )
    assert reset.initial_password == "ResetPass12"
    assert users.get_by_id("usr_bob").token_version == 2
    with pytest.raises(AuthError):
        auth_service.authenticate(login.access_token)
    later = auth_service.login("bob", "ResetPass12", request_id="req_after")
    assert later.access_token
