"""HTTP /api/v1/documents upload and list. Uses injected services; not GATE-P0 verified."""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline, policy_pdf
from pivot.auth.ports import UserAccount
from pivot.http import create_app


def _with_admin(pipeline: Pipeline) -> Pipeline:
    hasher = pipeline.hasher
    pipeline.users.save(
        UserAccount(
            id="usr_admin",
            username="admin",
            password_hash=hasher.hash("admin-password"),
            role="admin",
            status="active",
            token_version=1,
        )
    )
    return pipeline


def _client(pipeline: Pipeline | None = None, *, mount_documents: bool = True) -> TestClient:
    if pipeline is None:
        return TestClient(create_app(), base_url="https://testserver")
    documents = pipeline.documents if mount_documents else None
    return TestClient(
        create_app(auth=pipeline.auth, documents=documents),
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


def _pdf_form(title: str = "Attendance Policy", filename: str = "handbook.pdf"):
    return {"title": title}, {"file": (filename, policy_pdf(), "application/pdf")}


def test_FR_DOC_001_http_admin_upload_returns_uploaded_version():
    client = _client(_with_admin(Pipeline()))
    token = _login(client, "admin", "admin-password", "req_admin_login")
    data, files = _pdf_form()
    response = client.post(
        "/api/v1/documents",
        data=data,
        files=files,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_http_upload",
            "Idempotency-Key": "idem-upload-1",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "uploaded"
    assert body["document_id"]
    assert body["version_id"]
    assert "quarantine/" not in str(body)
    assert "storage_key" not in body


def test_FR_DOC_001_http_user_upload_forbidden():
    client = _client(_with_admin(Pipeline()))
    token = _login(client, "alice", "correct-password", "req_user_login")
    data, files = _pdf_form()
    response = client.post(
        "/api/v1/documents",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_user_up"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH_FORBIDDEN"
    assert response.json()["request_id"] == "req_user_up"


def test_FR_RBAC_001_http_documents_require_bearer():
    client = _client(_with_admin(Pipeline()))
    listed = client.get("/api/v1/documents", headers={"X-Request-ID": "req_list_anon"})
    assert listed.status_code == 401
    assert listed.json()["code"] == "AUTH_INVALID_CREDENTIALS"
    data, files = _pdf_form()
    uploaded = client.post(
        "/api/v1/documents",
        data=data,
        files=files,
        headers={"X-Request-ID": "req_up_anon"},
    )
    assert uploaded.status_code == 401
    assert uploaded.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_FR_DOC_002_http_legacy_office_rejected():
    client = _client(_with_admin(Pipeline()))
    token = _login(client, "admin", "admin-password", "req_admin_login")
    response = client.post(
        "/api/v1/documents",
        data={"title": "legacy"},
        files={
            "file": (
                "old.doc",
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32,
                "application/msword",
            )
        },
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_doc"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "UNSUPPORTED_EXTENSION"
    assert response.json()["request_id"] == "req_doc"


def test_FR_DOC_005_http_duplicate_sha_idempotent():
    client = _client(_with_admin(Pipeline()))
    token = _login(client, "admin", "admin-password", "req_admin_login")
    headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req_first"}
    first = client.post(
        "/api/v1/documents",
        data={"title": "one"},
        files=_pdf_form()[1],
        headers=headers,
    )
    second = client.post(
        "/api/v1/documents",
        data={"title": "two"},
        files=_pdf_form()[1],
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_second"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["document_id"] == second.json()["document_id"]
    assert first.json()["version_id"] == second.json()["version_id"]


def test_FR_DOC_007_http_list_excludes_tombstone():
    pipeline = _with_admin(Pipeline())
    client = _client(pipeline)
    token = _login(client, "admin", "admin-password", "req_admin_login")
    auth = {"Authorization": f"Bearer {token}"}
    kept = client.post(
        "/api/v1/documents",
        data={"title": "kept"},
        files=_pdf_form()[1],
        headers={**auth, "X-Request-ID": "req_kept"},
    )
    removed = client.post(
        "/api/v1/documents",
        data={"title": "removed"},
        files={"file": ("removed.pdf", policy_pdf() + b"\n", "application/pdf")},
        headers={**auth, "X-Request-ID": "req_removed"},
    )
    assert kept.status_code == 201
    assert removed.status_code == 201
    pipeline.documents.request_delete(removed.json()["document_id"], "req_del", "usr_admin")
    listed = client.get("/api/v1/documents", headers={**auth, "X-Request-ID": "req_list"})
    assert listed.status_code == 200
    body = listed.json()
    assert "items" in body
    assert body.get("pagination") is None
    ids = {item["document_id"] for item in body["items"]}
    assert kept.json()["document_id"] in ids
    assert removed.json()["document_id"] not in ids
    kept_id = kept.json()["document_id"]
    kept_item = next(item for item in body["items"] if item["document_id"] == kept_id)
    assert kept_item["title"] == "kept"
    assert kept_item["current_version"] is None
    assert "storage_key" not in kept_item
    assert "quarantine/" not in str(body)


def test_FR_RBAC_004_http_list_hides_non_shared_from_user():
    pipeline = _with_admin(Pipeline())
    client = _client(pipeline)
    admin_token = _login(client, "admin", "admin-password", "req_admin_login")
    shared = client.post(
        "/api/v1/documents",
        data={"title": "shared-doc", "space": "shared"},
        files=_pdf_form()[1],
        headers={"Authorization": f"Bearer {admin_token}", "X-Request-ID": "req_shared"},
    )
    internal = client.post(
        "/api/v1/documents",
        data={"title": "internal-doc", "space": "internal"},
        files={"file": ("internal.pdf", policy_pdf() + b"\nX", "application/pdf")},
        headers={"Authorization": f"Bearer {admin_token}", "X-Request-ID": "req_internal"},
    )
    assert shared.status_code == 201
    assert internal.status_code == 201
    user_token = _login(client, "alice", "correct-password", "req_alice")
    listed = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": "req_user_list"},
    )
    assert listed.status_code == 200
    ids = {item["document_id"] for item in listed.json()["items"]}
    assert shared.json()["document_id"] in ids
    assert internal.json()["document_id"] not in ids


def test_NFR_OBS_auth_only_app_does_not_mount_documents():
    pipeline = Pipeline()
    app = create_app(auth=pipeline.auth)
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any(path.startswith("/api/v1/documents") for path in paths)
    response = TestClient(app, base_url="https://testserver").get("/api/v1/documents")
    assert response.status_code == 404
