from __future__ import annotations

import pytest
from pivot.auth.errors import AuthError


def test_FR_RBAC_001_user_cannot_access_admin_api(auth_service, audits):
    login = auth_service.login("alice", "correct-password", request_id="req_login")
    principal = auth_service.authenticate(login.access_token)
    with pytest.raises(AuthError) as error:
        auth_service.require_admin(principal, path="/api/v1/admin/users", request_id="req_admin")
    assert error.value.code == "AUTH_FORBIDDEN"
    assert any(event.action == "auth.admin_forbidden" for event in audits.events)


def test_FR_RBAC_001_admin_can_access_admin_api(auth_service):
    login = auth_service.login("admin", "admin-password", request_id="req_login")
    principal = auth_service.authenticate(login.access_token)
    auth_service.require_admin(principal, path="/api/v1/admin/users", request_id="req_admin")
