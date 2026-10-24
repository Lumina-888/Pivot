from __future__ import annotations

import pytest
from pivot.auth.errors import AuthError


def test_FR_RBAC_004_only_visible_library_documents_are_authorized_for_users(auth_service):
    login = auth_service.login("alice", "correct-password", request_id="req_login")
    principal = auth_service.authenticate(login.access_token)
    auth_service.authorize_document(principal, "doc_shared")
    with pytest.raises(AuthError) as error:
        auth_service.authorize_document(principal, "doc_secret")
    assert error.value.code in {"RESOURCE_FORBIDDEN", "RESOURCE_NOT_FOUND"}


def test_FR_RBAC_004_admin_may_manage_department_document(auth_service):
    login = auth_service.login("admin", "admin-password", request_id="req_login")
    principal = auth_service.authenticate(login.access_token)
    auth_service.authorize_document(principal, "doc_secret", action="manage")
