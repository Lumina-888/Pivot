from __future__ import annotations

from pivot.auth.cookies import refresh_cookie


def test_FR_AUTH_001_refresh_cookie_is_httponly_secure_samesite():
    cookie = refresh_cookie("opaque-refresh", max_age=3600)
    header = cookie.as_set_cookie()
    assert "HttpOnly" in header
    assert "Secure" in header
    assert "SameSite=Strict" in header
    assert "Path=/api/v1/auth" in header
    assert cookie.httponly is True
    assert cookie.secure is True


def test_NFR_SEC_013_errors_do_not_include_password_or_token():
    from pivot.auth.errors import AuthError

    error = AuthError("AUTH_INVALID_CREDENTIALS", "账号或密码错误", "req_1")
    rendered = error.to_envelope()
    assert "password" not in rendered["message"].lower() or "账号或密码错误" == rendered["message"]
    assert "token" not in rendered["message"].lower()
    assert set(rendered) >= {"code", "message", "request_id"}
