"""HTTP /api/v1/auth assembly. Uses injected AuthService; not GATE-P0 verified."""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.http import create_app


def _client(pipeline: Pipeline | None = None) -> TestClient:
    auth = None if pipeline is None else pipeline.auth
    return TestClient(create_app(auth=auth), base_url="https://testserver")


def test_FR_AUTH_001_http_login_sets_httponly_refresh_cookie():
    pipeline = Pipeline()
    response = _client(pipeline).post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "correct-password"},
        headers={"X-Request-ID": "req_http_login"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["refresh_token_cookie"] is True
    assert "refresh_token" not in body
    assert body["access_token"]
    assert "correct-password" not in body["access_token"]
    set_cookie = response.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "samesite=strict" in set_cookie.lower()
    assert "Path=/api/v1/auth" in set_cookie or "path=/api/v1/auth" in set_cookie.lower()


def test_FR_AUTH_002_http_invalid_credentials_are_uniform():
    client = _client(Pipeline())
    missing = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "whatever"},
        headers={"X-Request-ID": "req_miss"},
    )
    wrong = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "wrong-password"},
        headers={"X-Request-ID": "req_wrong"},
    )
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json()["code"] == "AUTH_INVALID_CREDENTIALS"
    assert wrong.json()["code"] == "AUTH_INVALID_CREDENTIALS"
    assert missing.json()["message"] == wrong.json()["message"] == "账号或密码错误"
    assert missing.json()["request_id"] == "req_miss"
    assert missing.json()["message"] != "用户不存在"
    assert wrong.json()["message"] != "密码错误"


def test_FR_AUTH_003_http_refresh_rotates_session_from_cookie():
    client = _client(Pipeline())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "correct-password"},
        headers={"X-Request-ID": "req_login"},
    )
    first_token = login.json()["access_token"]
    refresh = client.post("/api/v1/auth/refresh", headers={"X-Request-ID": "req_refresh"})
    assert refresh.status_code == 200
    assert refresh.json()["access_token"]
    assert refresh.json()["access_token"] != first_token
    assert refresh.json()["refresh_token_cookie"] is True


def test_FR_AUTH_003_http_logout_requires_bearer_and_clears_cookie():
    client = _client(Pipeline())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "correct-password"},
        headers={"X-Request-ID": "req_login"},
    )
    token = login.json()["access_token"]
    forbidden = client.post("/api/v1/auth/logout", headers={"X-Request-ID": "req_no_bearer"})
    assert forbidden.status_code == 401
    assert forbidden.json()["code"] == "AUTH_INVALID_CREDENTIALS"
    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_logout"},
    )
    assert logout.status_code == 204
    set_cookie = logout.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie.lower()
    refresh = client.post("/api/v1/auth/refresh", headers={"X-Request-ID": "req_after"})
    assert refresh.status_code == 401
