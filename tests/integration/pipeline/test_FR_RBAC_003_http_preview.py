"""HTTP document preview/download. Not GATE-P0 verified."""

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


def _upload(client: TestClient, token: str, title: str, extra: bytes = b"", space: str = "shared"):
    response = client.post(
        "/api/v1/documents",
        data={"title": title, "space": space},
        files={"file": (f"{title}.pdf", policy_pdf() + extra, "application/pdf")},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": f"req_up_{title}"},
    )
    assert response.status_code == 201
    return response.json()


def test_FR_RBAC_003_http_preview_requires_bearer_and_hides_guessed_id():
    client = _client(_with_admin(Pipeline()))
    missing = client.get(
        "/api/v1/documents/doc_guessed/preview",
        headers={"X-Request-ID": "req_anon"},
    )
    assert missing.status_code == 401
    assert missing.json()["code"] == "AUTH_INVALID_CREDENTIALS"
    token = _login(client, "alice", "correct-password", "req_alice")
    guessed = client.get(
        "/api/v1/documents/doc_guessed/preview",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_guess"},
    )
    assert guessed.status_code == 404
    assert guessed.json()["code"] == "RESOURCE_NOT_FOUND"
    assert guessed.json()["request_id"] == "req_guess"


def test_FR_RBAC_003_http_user_can_preview_shared_bytes():
    client = _client(_with_admin(Pipeline()))
    admin = _login(client, "admin", "admin-password", "req_admin")
    uploaded = _upload(client, admin, "policy", extra=b"\nshared")
    user = _login(client, "alice", "correct-password", "req_alice")
    preview = client.get(
        f"/api/v1/documents/{uploaded['document_id']}/preview",
        headers={"Authorization": f"Bearer {user}", "X-Request-ID": "req_preview"},
    )
    assert preview.status_code == 200
    assert preview.content == policy_pdf() + b"\nshared"
    assert preview.headers["content-type"].startswith("application/pdf")
    disposition = preview.headers["content-disposition"]
    assert "inline" in disposition
    assert "quarantine/" not in disposition
    assert "storage_key" not in disposition
    assert "minio" not in preview.headers.get("location", "").lower()
    assert preview.headers.get("cache-control") == "private, no-store"


def test_FR_RBAC_003_http_user_cannot_preview_internal():
    client = _client(_with_admin(Pipeline()))
    admin = _login(client, "admin", "admin-password", "req_admin")
    internal = _upload(client, admin, "internal-doc", extra=b"\nI", space="internal")
    user = _login(client, "alice", "correct-password", "req_alice")
    hidden = client.get(
        f"/api/v1/documents/{internal['document_id']}/preview",
        headers={"Authorization": f"Bearer {user}", "X-Request-ID": "req_hid"},
    )
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_003_http_download_attachment_and_no_minio_url():
    client = _client(_with_admin(Pipeline()))
    admin = _login(client, "admin", "admin-password", "req_admin")
    uploaded = _upload(client, admin, "handbook", extra=b"\ndl")
    user = _login(client, "alice", "correct-password", "req_alice")
    download = client.get(
        f"/api/v1/documents/{uploaded['document_id']}/download",
        headers={"Authorization": f"Bearer {user}", "X-Request-ID": "req_dl"},
    )
    assert download.status_code == 200
    assert download.content == policy_pdf() + b"\ndl"
    disposition = download.headers["content-disposition"]
    assert "attachment" in disposition
    assert "filename=" in disposition.lower()
    joined = str(download.headers).lower() + download.content.decode("latin1", errors="ignore")
    assert "minio" not in joined
    assert "quarantine/" not in joined
    assert ":9000" not in joined


def _publish(pipeline: Pipeline, version_id: str) -> None:
    pipeline.documents.enqueue(version_id, "req_en")
    pipeline.documents.worker_started(version_id, "task_1", "req_ws")
    pipeline.documents.parse_ok(version_id, "req_parse")
    pipeline.documents.apply_chunks(version_id, ["body"], "msg_1", "req_chunk")
    pipeline.documents.embedding_ok(version_id, "req_emb")
    pipeline.documents.publish(version_id, "req_pub")


def test_FR_DOC_007_http_user_cannot_preview_tombstone():
    pipeline = _with_admin(Pipeline())
    client = _client(pipeline)
    admin = _login(client, "admin", "admin-password", "req_admin")
    uploaded = _upload(client, admin, "gone", extra=b"\ngone")
    _publish(pipeline, uploaded["version_id"])
    doc_id = uploaded["document_id"]
    user = _login(client, "alice", "correct-password", "req_alice")
    deleted = client.post(
        f"/api/v1/documents/{doc_id}/delete",
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_del"},
    )
    assert deleted.status_code == 202
    user_preview = client.get(
        f"/api/v1/documents/{doc_id}/preview",
        headers={"Authorization": f"Bearer {user}", "X-Request-ID": "req_user_p"},
    )
    admin_preview = client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_admin_p"},
    )
    assert user_preview.status_code == 404
    assert user_preview.json()["code"] == "RESOURCE_NOT_FOUND"
    assert admin_preview.status_code == 200
    pipeline.documents.cleanup_ok(uploaded["version_id"], "req_clean")
    after_cleanup = client.get(
        f"/api/v1/documents/{doc_id}/preview",
        headers={"Authorization": f"Bearer {admin}", "X-Request-ID": "req_clean_p"},
    )
    assert after_cleanup.status_code == 404
    assert after_cleanup.json()["code"] == "RESOURCE_NOT_FOUND"
