from __future__ import annotations

import pytest
from pivot.auth.errors import AuthError


def test_FR_RBAC_002_owner_can_read_own_conversation(auth_service):
    login = auth_service.login("alice", "correct-password", request_id="req_login")
    principal = auth_service.authenticate(login.access_token)
    auth_service.authorize_conversation(principal, "conv_alice")


def test_FR_RBAC_002_guessed_foreign_conversation_is_not_found(auth_service):
    login = auth_service.login("alice", "correct-password", request_id="req_login")
    principal = auth_service.authenticate(login.access_token)
    with pytest.raises(AuthError) as error:
        auth_service.authorize_conversation(principal, "conv_bob")
    assert error.value.code == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_002_admin_cannot_read_full_conversation_by_default(auth_service):
    login = auth_service.login("admin", "admin-password", request_id="req_login")
    principal = auth_service.authenticate(login.access_token)
    with pytest.raises(AuthError) as error:
        auth_service.authorize_conversation(principal, "conv_alice")
    assert error.value.code in {"RESOURCE_FORBIDDEN", "RESOURCE_NOT_FOUND"}
