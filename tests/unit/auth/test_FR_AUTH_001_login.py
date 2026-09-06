from __future__ import annotations

import pytest
from pivot.auth.errors import AuthError


def test_FR_AUTH_001_login_returns_access_token_and_httponly_refresh(auth_service):
    result = auth_service.login("alice", "correct-password", request_id="req_login")

    assert result.access_token
    assert result.token_type == "Bearer"
    assert result.expires_in == 60
    assert result.refresh_token_cookie is True
    assert result.cookie.name == "refresh_token"
    assert result.cookie.httponly is True
    assert result.cookie.secure is True
    assert result.cookie.samesite == "Strict"
    assert result.cookie.path == "/api/v1/auth"
    assert "correct-password" not in result.access_token
    principal = auth_service.authenticate(result.access_token)
    assert principal.user_id == "usr_alice"
    assert principal.role == "user"


def test_FR_AUTH_001_login_does_not_store_refresh_in_response_body(auth_service):
    result = auth_service.login("alice", "correct-password", request_id="req_login")
    payload = result.to_login_success()
    assert set(payload) == {"access_token", "token_type", "expires_in", "refresh_token_cookie"}
    assert "refresh_token" not in payload
    assert result.refresh_token not in (payload["access_token"],)


def test_FR_AUTH_002_invalid_credentials_are_uniform(auth_service, audits):
    with pytest.raises(AuthError) as missing:
        auth_service.login("nobody", "whatever", request_id="req_miss")
    with pytest.raises(AuthError) as wrong:
        auth_service.login("alice", "wrong-password", request_id="req_wrong")

    assert missing.value.code == "AUTH_INVALID_CREDENTIALS"
    assert wrong.value.code == "AUTH_INVALID_CREDENTIALS"
    assert missing.value.message == wrong.value.message == "账号或密码错误"
    assert missing.value.message != "用户不存在"
    assert missing.value.message != "密码错误"
    assert {event.action for event in audits.events} == {"auth.login_failed"}
