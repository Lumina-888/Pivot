"""HTTP /api/v1/exports and /admin/audit-events. Not GATE-P0 verified."""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.http import create_app


def _client(
    pipeline: Pipeline,
    *,
    mount_exports: bool = True,
    mount_audits: bool = True,
) -> TestClient:
    return TestClient(
        create_app(
            auth=pipeline.auth,
            exports=pipeline.exports if mount_exports else None,
            audits=pipeline.export_audits if mount_audits else None,
        ),
        base_url="https://testserver",
    )


def _login(client: TestClient, username: str, password: str, request_id: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"X-Request-ID": request_id},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _alice_ready_conversation(pipeline: Pipeline) -> None:
    pipeline.ingest_policy_pdf("usr_alice")
    pipeline.ask(
        owner_id="usr_alice",
        question="late three times written warning?",
        conversation_id="conv_alice",
        retrieval=pipeline.retrieval_for_ready_chunks(),
    )


def test_FR_RBAC_001_http_exports_require_bearer():
    pipeline = Pipeline()
    client = _client(pipeline)
    response = client.post(
        "/api/v1/exports",
        json={
            "source_type": "conversation",
            "source_id": "conv_alice",
            "format": "markdown",
        },
        headers={"X-Request-ID": "req_anon"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_FR_EXPORT_001_http_create_returns_requested_and_ready_status():
    pipeline = Pipeline()
    _alice_ready_conversation(pipeline)
    client = _client(pipeline)
    token = _login(client, "alice", "correct-password", "req_login")
    created = client.post(
        "/api/v1/exports",
        json={
            "source_type": "conversation",
            "source_id": "conv_alice",
            "format": "markdown",
        },
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_export"},
    )
    assert created.status_code == 202
    body = created.json()
    assert body["state"] == "requested"
    assert body["export_id"].startswith("exp_")
    assert set(body) == {"export_id", "state"}
    status = client.get(
        f"/api/v1/exports/{body['export_id']}",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_status"},
    )
    assert status.status_code == 200
    payload = status.json()
    assert payload["export_id"] == body["export_id"]
    assert payload["state"] == "ready"
    assert payload["download_url"]
    assert payload["download_url"].startswith("https://files.pivot.test/")
    assert "minio" not in payload["download_url"].lower()
    assert ":9000" not in payload["download_url"]
    assert "X-Amz" not in payload["download_url"]
    assert "storage_key" not in payload
    assert pipeline.answers.qa_invocations == 0
    assert pipeline.export_objects.presign_calls == []


def test_FR_EXPORT_001_http_other_user_cannot_get_foreign_export():
    pipeline = Pipeline()
    _alice_ready_conversation(pipeline)
    client = _client(pipeline)
    alice = _login(client, "alice", "correct-password", "req_alice")
    created = client.post(
        "/api/v1/exports",
        json={
            "source_type": "conversation",
            "source_id": "conv_alice",
            "format": "markdown",
        },
        headers={"Authorization": f"Bearer {alice}", "X-Request-ID": "req_alice_export"},
    )
    export_id = created.json()["export_id"]
    bob = _login(client, "bob", "bob-password", "req_bob")
    hidden = client.get(
        f"/api/v1/exports/{export_id}",
        headers={"Authorization": f"Bearer {bob}", "X-Request-ID": "req_bob_get"},
    )
    guessed = client.get(
        "/api/v1/exports/exp_forged",
        headers={"Authorization": f"Bearer {alice}", "X-Request-ID": "req_guess"},
    )
    forbidden_create = client.post(
        "/api/v1/exports",
        json={
            "source_type": "conversation",
            "source_id": "conv_alice",
            "format": "markdown",
        },
        headers={"Authorization": f"Bearer {bob}", "X-Request-ID": "req_bob_create"},
    )
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "RESOURCE_NOT_FOUND"
    assert guessed.status_code == 404
    assert guessed.json()["code"] == "RESOURCE_NOT_FOUND"
    assert forbidden_create.status_code == 404
    assert forbidden_create.json()["code"] == "RESOURCE_NOT_FOUND"


def test_FR_EXPORT_002_http_status_excludes_prompt_and_internal_storage():
    pipeline = Pipeline()
    _alice_ready_conversation(pipeline)
    client = _client(pipeline)
    token = _login(client, "alice", "correct-password", "req_login")
    created = client.post(
        "/api/v1/exports",
        json={
            "source_type": "conversation",
            "source_id": "conv_alice",
            "format": "docx",
        },
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_docx"},
    )
    status = client.get(
        f"/api/v1/exports/{created.json()['export_id']}",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_docx_get"},
    )
    text = str(status.json())
    assert "SYSTEM_PROMPT" not in text
    assert "hidden thinking" not in text
    assert "storage_key" not in text
    assert "minio" not in text.lower()


def test_FR_EXPORT_003_http_expired_status_has_no_download_url():
    pipeline = Pipeline()
    _alice_ready_conversation(pipeline)
    client = _client(pipeline)
    token = _login(client, "alice", "correct-password", "req_login")
    created = client.post(
        "/api/v1/exports",
        json={
            "source_type": "conversation",
            "source_id": "conv_alice",
            "format": "markdown",
        },
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_ttl"},
    )
    pipeline.export_clock.advance(3601)
    status = client.get(
        f"/api/v1/exports/{created.json()['export_id']}",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_expired"},
    )
    assert status.status_code == 200
    payload = status.json()
    assert payload["state"] == "expired"
    assert payload["download_url"] is None
    assert payload["expires_at"]


def test_FR_AUDIT_002_http_user_cannot_list_audit_events():
    pipeline = Pipeline()
    client = _client(pipeline)
    token = _login(client, "alice", "correct-password", "req_login")
    response = client.get(
        "/api/v1/admin/audit-events",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_user_audit"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH_FORBIDDEN"
    assert response.json()["request_id"] == "req_user_audit"


def test_FR_AUDIT_002_http_admin_lists_redacted_events():
    pipeline = Pipeline()
    _alice_ready_conversation(pipeline)
    client = _client(pipeline)
    alice = _login(client, "alice", "correct-password", "req_alice")
    client.post(
        "/api/v1/exports",
        json={
            "source_type": "conversation",
            "source_id": "conv_alice",
            "format": "markdown",
        },
        headers={"Authorization": f"Bearer {alice}", "X-Request-ID": "req_export_audit"},
    )
    admin = _login(client, "admin", "admin-password", "req_admin")
    listed = client.get(
        "/api/v1/admin/audit-events",
        params={"action": "export.create", "page": 99, "page_size": 1},
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_admin_list"},
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body.get("pagination") is None
    assert body["items"]
    actions = {item["action"] for item in body["items"]}
    assert "export.create" in actions
    blob = str(body)
    assert "password" not in blob
    assert "SYSTEM_PROMPT" not in blob
    assert "correct-password" not in blob


def test_NFR_OBS_auth_only_app_does_not_mount_exports():
    pipeline = Pipeline()
    app = create_app(auth=pipeline.auth)
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any("/exports" in path for path in paths)
    assert not any(path.endswith("/admin/audit-events") for path in paths)
    client = TestClient(app, base_url="https://testserver")
    assert client.post("/api/v1/exports").status_code == 404
    assert client.get("/api/v1/admin/audit-events").status_code == 404
