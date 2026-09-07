"""HTTP GET /api/v1/search. Uses injected RetrievalService; not GATE-P0 verified."""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.http import create_app


def _client(pipeline: Pipeline, *, retrieval=None) -> TestClient:
    return TestClient(
        create_app(auth=pipeline.auth, retrieval=retrieval),
        base_url="https://testserver",
    )


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "correct-password"},
        headers={"X-Request-ID": "req_login"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_FR_RBAC_001_http_search_requires_bearer():
    pipeline = Pipeline()
    client = _client(pipeline, retrieval=pipeline.retrieval_for_ready_chunks())
    response = client.get(
        "/api/v1/search",
        params={"q": "leave"},
        headers={"X-Request-ID": "req_anon"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_FR_SEARCH_001_http_returns_ready_current_hits():
    pipeline = Pipeline()
    _version, _ready, document, _result = pipeline.ingest_policy_pdf("usr_alice")
    client = _client(pipeline, retrieval=pipeline.retrieval_for_ready_chunks())
    token = _login(client)
    response = client.get(
        "/api/v1/search",
        params={"q": "late three times"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_search"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("pagination") is None
    assert body["items"]
    hit = body["items"][0]
    assert hit["document_id"] == document.id
    assert hit["title"] == "Attendance Policy"
    assert "late three times" in hit["snippet"]
    assert hit["version_id"]
    assert "storage_key" not in hit
    assert "quarantine/" not in str(body)


def test_FR_SEARCH_001_http_excludes_tombstone():
    pipeline = Pipeline()
    _version, _ready, document, _result = pipeline.ingest_policy_pdf("usr_alice")
    pipeline.documents.request_delete(document.id, "req_del", "usr_alice")
    client = _client(pipeline, retrieval=pipeline.retrieval_for_ready_chunks())
    token = _login(client)
    response = client.get(
        "/api/v1/search",
        params={"q": "late three times"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_deleted"},
    )
    assert response.status_code == 200
    ids = {item["document_id"] for item in response.json()["items"]}
    assert document.id not in ids


def test_NFR_OBS_auth_only_app_does_not_mount_search():
    pipeline = Pipeline()
    app = create_app(auth=pipeline.auth)
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any(path.startswith("/api/v1/search") for path in paths)
    response = TestClient(app, base_url="https://testserver").get(
        "/api/v1/search", params={"q": "leave"}
    )
    assert response.status_code == 404
