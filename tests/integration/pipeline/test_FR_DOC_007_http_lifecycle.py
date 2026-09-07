"""HTTP document detail, versions, retry and delete. Not GATE-P0 verified."""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline, policy_pdf
from pivot.auth.ports import UserAccount
from pivot.http import create_app


def _with_admin(pipeline: Pipeline) -> Pipeline:
    pipeline.users.save(
        UserAccount(
            id="usr_admin",
            username="admin",
            password_hash=pipeline.hasher.hash("admin-password"),
            role="admin",
            status="active",
            token_version=1,
        )
    )
    return pipeline


def _client(pipeline: Pipeline) -> TestClient:
    return TestClient(
        create_app(auth=pipeline.auth, documents=pipeline.documents),
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


def _upload(client: TestClient, token: str, title: str, extra: bytes = b""):
    response = client.post(
        "/api/v1/documents",
        data={"title": title, "space": "shared"},
        files={"file": (f"{title}.pdf", policy_pdf() + extra, "application/pdf")},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": f"req_up_{title}"},
    )
    assert response.status_code == 201
    return response.json()


def test_FR_RBAC_003_http_document_detail_requires_bearer_and_hides_guessed_id():
    client = _client(_with_admin(Pipeline()))
    missing = client.get("/api/v1/documents/doc_guessed", headers={"X-Request-ID": "req_anon"})
    assert missing.status_code == 401
    assert missing.json()["code"] == "AUTH_INVALID_CREDENTIALS"
    token = _login(client, "alice", "correct-password", "req_alice")
    guessed = client.get(
        "/api/v1/documents/doc_guessed",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_guess"},
    )
    assert guessed.status_code == 404
    assert guessed.json()["code"] == "RESOURCE_NOT_FOUND"
    assert guessed.json()["request_id"] == "req_guess"


def test_FR_DOC_007_http_detail_and_versions_omit_storage_key():
    client = _client(_with_admin(Pipeline()))
    token = _login(client, "admin", "admin-password", "req_admin")
    uploaded = _upload(client, token, "policy")
    detail = client.get(
        f"/api/v1/documents/{uploaded['document_id']}",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_detail"},
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["document_id"] == uploaded["document_id"]
    assert body["title"] == "policy"
    assert body["versions"][0]["version_id"] == uploaded["version_id"]
    assert body["versions"][0]["state"] == "uploaded"
    assert "storage_key" not in body
    assert "quarantine/" not in str(body)
    versions = client.get(
        f"/api/v1/documents/{uploaded['document_id']}/versions",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_vers"},
    )
    assert versions.status_code == 200
    assert versions.json()["pagination"] is None
    assert versions.json()["items"][0]["version_id"] == uploaded["version_id"]


def test_FR_RBAC_004_http_user_can_read_shared_but_not_internal():
    pipeline = _with_admin(Pipeline())
    client = _client(pipeline)
    admin = _login(client, "admin", "admin-password", "req_admin")
    shared = client.post(
        "/api/v1/documents",
        data={"title": "shared-doc", "space": "shared"},
        files={"file": ("shared.pdf", policy_pdf(), "application/pdf")},
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_shared"},
    )
    internal = client.post(
        "/api/v1/documents",
        data={"title": "internal-doc", "space": "internal"},
        files={"file": ("internal.pdf", policy_pdf() + b"\nI", "application/pdf")},
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_internal"},
    )
    assert shared.status_code == 201
    assert internal.status_code == 201
    user = _login(client, "alice", "correct-password", "req_alice")
    ok = client.get(
        f"/api/v1/documents/{shared.json()['document_id']}",
        headers={"Authorization": f"Bearer {user}", "X-Request-ID": "req_ok"},
    )
    hidden = client.get(
        f"/api/v1/documents/{internal.json()['document_id']}",
        headers={"Authorization": f"Bearer {user}", "X-Request-ID": "req_hid"},
    )
    assert ok.status_code == 200
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "RESOURCE_NOT_FOUND"


def test_FR_DOC_006_http_retry_requeues_failed_version():
    pipeline = _with_admin(Pipeline())
    client = _client(pipeline)
    token = _login(client, "admin", "admin-password", "req_admin")
    uploaded = _upload(client, token, "broken", extra=b"\nfail")
    version_id = uploaded["version_id"]
    pipeline.documents.enqueue(version_id, "req_en")
    pipeline.documents.worker_started(version_id, "task_1", "req_ws")
    pipeline.documents.parse_error(version_id, "CORRUPTED_FILE", "req_err")
    user = _login(client, "alice", "correct-password", "req_alice")
    forbidden = client.post(
        f"/api/v1/documents/{uploaded['document_id']}/retry",
        headers={"Authorization": f"Bearer {user}", "X-Request-ID": "req_user_retry"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "AUTH_FORBIDDEN"
    accepted = client.post(
        f"/api/v1/documents/{uploaded['document_id']}/retry",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_retry"},
    )
    assert accepted.status_code == 202
    assert accepted.json() == {"document_id": uploaded["document_id"], "accepted": True}
    assert pipeline.versions.get(version_id).state == "queued"


def test_FR_DOC_007_http_delete_tombstones_and_drops_from_list():
    pipeline = _with_admin(Pipeline())
    client = _client(pipeline)
    admin = _login(client, "admin", "admin-password", "req_admin")
    uploaded = _upload(client, admin, "gone", extra=b"\ngone")
    doc_id = uploaded["document_id"]
    user = _login(client, "alice", "correct-password", "req_alice")
    forbidden = client.post(
        f"/api/v1/documents/{doc_id}/delete",
        headers={"Authorization": f"Bearer {user}", "X-Request-ID": "req_user_del"},
    )
    assert forbidden.status_code == 403
    deleted = client.post(
        f"/api/v1/documents/{doc_id}/delete",
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_del"},
    )
    assert deleted.status_code == 202
    assert deleted.json() == {"document_id": doc_id, "accepted": True}
    listed = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_list"},
    )
    ids = {item["document_id"] for item in listed.json()["items"]}
    assert doc_id not in ids
    admin_detail = client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_admin_d"},
    )
    user_detail = client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {user}", "X-Request-ID": "req_user_d"},
    )
    assert admin_detail.status_code == 200
    assert admin_detail.json()["deleted_at"]
    assert user_detail.status_code == 404
    assert user_detail.json()["code"] == "RESOURCE_NOT_FOUND"
