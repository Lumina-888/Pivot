from __future__ import annotations

import pytest
from pivot.auth.errors import AuthError
from pivot.auth.service import AuthService


def test_FR_RBAC_003_id_guess_cannot_bypass_authorization(auth_service: AuthService):
    login = auth_service.login("alice", "correct-password", request_id="req_login")
    principal = auth_service.authenticate(login.access_token)
    guessed = {
        "doc_secret": "document",
        "chk_secret": "chunk",
        "cit_secret": "citation",
        "exp_bob": "export",
        "conv_bob": "conversation",
    }
    codes = []
    for identifier, kind in guessed.items():
        with pytest.raises(AuthError) as error:
            auth_service.authorize_resource(principal, kind, identifier)
        codes.append(error.value.code)
    assert set(codes) <= {"RESOURCE_FORBIDDEN", "RESOURCE_NOT_FOUND"}
    assert "AUTH_INVALID_CREDENTIALS" not in codes
