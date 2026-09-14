"""HTTP change-password and /admin/users. Not GATE-P0 verified."""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.http import create_app


def _client(pipeline: Pipeline) -> TestClient:
    return TestClient(create_app(auth=pipeline.auth), base_url="https://testserver")


def _login(client: TestClient, username: str, password: str, request_id: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"X-Request-ID": request_id},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_FR_AUTH_004_http_change_password_requires_bearer():
    client = _client(Pipeline())
    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "correct-password", "new_password": "NewPassword9"},
        headers={"X-Request-ID": "req_anon"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_FR_AUTH_004_http_change_password_invalidates_old_session():
    client = _client(Pipeline())
    token = _login(client, "alice", "correct-password", "req_login")
    changed = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "correct-password", "new_password": "NewPassword9"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_change"},
    )
    assert changed.status_code == 204
    assert changed.content in {b"", b"null"}
    stale = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "correct-password"},
        headers={"X-Request-ID": "req_old"},
    )
    assert stale.status_code == 401
    later = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "NewPassword9"},
        headers={"X-Request-ID": "req_new"},
    )
    assert later.status_code == 200
    replay = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "NewPassword9", "new_password": "AnotherPass1"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_stale"},
    )
    assert replay.status_code == 401


def test_FR_RBAC_001_http_admin_users_forbidden_for_user():
    client = _client(Pipeline())
    token = _login(client, "alice", "correct-password", "req_login")
    listed = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_user_list"},
    )
    created = client.post(
        "/api/v1/admin/users",
        json={"username": "carol", "initial_password": "InitialPass1"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_user_create"},
    )
    patched = client.patch(
        "/api/v1/admin/users/usr_bob",
        json={"status": "disabled"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_user_patch"},
    )
    assert listed.status_code == 403
    assert listed.json()["code"] == "AUTH_FORBIDDEN"
    assert created.status_code == 403
    assert patched.status_code == 403
    assert "correct-password" not in str(listed.json())


def test_FR_AUTH_004_http_admin_lists_and_creates_user_without_password():
    client = _client(Pipeline())
    admin = _login(client, "admin", "admin-password", "req_admin")
    listed = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_list"},
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body.get("pagination") is None
    names = {item["username"] for item in body["items"]}
    assert {"alice", "bob", "admin"} <= names
    for item in body["items"]:
        assert "password" not in item
        assert "password_hash" not in item
        assert "initial_password" not in item
        assert item["user_id"]
        assert item["created_at"].endswith("Z")
    created = client.post(
        "/api/v1/admin/users",
        json={"username": "carol", "initial_password": "InitialPass1"},
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_create"},
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["username"] == "carol"
    assert payload["role"] == "user"
    assert payload["status"] == "active"
    assert "InitialPass1" not in str(payload)
    assert "password" not in payload
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "carol", "password": "InitialPass1"},
        headers={"X-Request-ID": "req_carol"},
    )
    assert login.status_code == 200


def test_FR_AUTH_003_http_disable_user_revokes_access():
    client = _client(Pipeline())
    bob_token = _login(client, "bob", "bob-password", "req_bob")
    admin = _login(client, "admin", "admin-password", "req_admin")
    disabled = client.patch(
        "/api/v1/admin/users/usr_bob",
        json={"status": "disabled"},
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_disable"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["user_id"] == "usr_bob"
    assert disabled.json()["status"] == "disabled"
    assert "password" not in disabled.json()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "bob-password"},
        headers={"X-Request-ID": "req_bob_login"},
    )
    assert login.status_code == 401
    stale = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {bob_token}", "X-Request-ID": "req_bob_stale"},
    )
    assert stale.status_code == 403
    enabled = client.patch(
        "/api/v1/admin/users/usr_bob",
        json={"status": "active"},
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_enable"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "active"
    later = client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "bob-password"},
        headers={"X-Request-ID": "req_bob_again"},
    )
    assert later.status_code == 200


def test_FR_AUTH_003_http_admin_patch_role_promotes_and_revokes_access():
    pipeline = Pipeline()
    client = _client(pipeline)
    bob_token = _login(client, "bob", "bob-password", "req_bob")
    admin = _login(client, "admin", "admin-password", "req_admin")
    patched = client.patch(
        "/api/v1/admin/users/usr_bob",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_role"},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["user_id"] == "usr_bob"
    assert body["role"] == "admin"
    assert body["status"] == "active"
    assert "password" not in body
    assert "initial_password" not in body
    stale = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {bob_token}", "X-Request-ID": "req_bob_stale"},
    )
    assert stale.status_code in {401, 403}
    later = client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "bob-password"},
        headers={"X-Request-ID": "req_bob_admin"},
    )
    assert later.status_code == 200
    listed = client.get(
        "/api/v1/admin/users",
        headers={
            "Authorization": f"Bearer {later.json()['access_token']}",
            "X-Request-ID": "req_bob_list",
        },
    )
    assert listed.status_code == 200
    assert any(event.action == "auth.role_change" for event in pipeline.auth_audits.events)


def test_FR_AUTH_003_http_admin_patch_role_forbidden_for_user():
    client = _client(Pipeline())
    token = _login(client, "alice", "correct-password", "req_login")
    patched = client.patch(
        "/api/v1/admin/users/usr_bob",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_user_role"},
    )
    assert patched.status_code == 403
    assert patched.json()["code"] == "AUTH_FORBIDDEN"


def test_FR_AUTH_003_http_reset_password_returns_new_secret_and_revokes_access():
    pipeline = Pipeline()
    client = _client(pipeline)
    bob_token = _login(client, "bob", "bob-password", "req_bob")
    admin = _login(client, "admin", "admin-password", "req_admin")
    reset = client.patch(
        "/api/v1/admin/users/usr_bob",
        json={"reset_password": True},
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_reset"},
    )
    assert reset.status_code == 200
    body = reset.json()
    secret = body["initial_password"]
    assert len(secret) >= 8
    assert secret != "bob-password"
    assert body["user_id"] == "usr_bob"
    assert body["role"] == "user"
    assert "password_hash" not in body
    assert secret not in str(pipeline.auth_audits.events)
    assert all(
        "password" not in event.metadata and secret not in str(event.metadata)
        for event in pipeline.auth_audits.events
    )
    stale = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {bob_token}", "X-Request-ID": "req_bob_stale"},
    )
    assert stale.status_code in {401, 403}
    old = client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "bob-password"},
        headers={"X-Request-ID": "req_old"},
    )
    assert old.status_code == 401
    later = client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": secret},
        headers={"X-Request-ID": "req_new"},
    )
    assert later.status_code == 200
    listed = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_list"},
    )
    assert listed.status_code == 200
    assert secret not in listed.text
    assert all("initial_password" not in item for item in listed.json()["items"])


def test_FR_AUTH_003_http_reset_password_unknown_user_is_not_found():
    client = _client(Pipeline())
    admin = _login(client, "admin", "admin-password", "req_admin")
    missing = client.patch(
        "/api/v1/admin/users/usr_missing",
        json={"reset_password": True},
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_missing"},
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "RESOURCE_NOT_FOUND"
    assert "initial_password" not in missing.json()
