"""HTTP signed export download consumer (ND-GAP-04). Not GATE-P0 verified."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.http import create_app


def _client(pipeline: Pipeline) -> TestClient:
    return TestClient(
        create_app(
            auth=pipeline.auth,
            exports=pipeline.exports,
            audits=pipeline.export_audits,
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


def _ready_link(pipeline: Pipeline, client: TestClient, token: str) -> tuple[str, int, str]:
    pipeline.ingest_policy_pdf("usr_alice")
    pipeline.ask(
        owner_id="usr_alice",
        question="late three times written warning?",
        conversation_id="conv_alice",
        retrieval=pipeline.retrieval_for_ready_chunks(),
    )
    created = client.post(
        "/api/v1/exports",
        json={"source_type": "conversation", "source_id": "conv_alice", "format": "markdown"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_export"},
    )
    assert created.status_code == 202
    status = client.get(
        f"/api/v1/exports/{created.json()['export_id']}",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_status"},
    )
    url = status.json()["download_url"]
    assert url
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    return parsed.path.rsplit("/", 1)[-1], int(query["e"][0]), query["s"][0]


def test_FR_EXPORT_003_signed_download_expiry_and_authorization():
    pipeline = Pipeline()
    client = _client(pipeline)
    alice = _login(client, "alice", "correct-password", "req_alice")
    export_id, expiry, signature = _ready_link(pipeline, client, alice)
    path = f"/api/v1/d/{export_id}?e={expiry}&s={signature}"

    # Valid signature plus the owner's bearer token downloads the bytes.
    ok = client.get(path, headers={"Authorization": f"Bearer {alice}"})
    assert ok.status_code == 200
    assert ok.content
    assert "attachment" in ok.headers.get("content-disposition", "")

    # The link alone is not enough: no bearer token, no download.
    anonymous = client.get(path)
    assert anonymous.status_code == 401
    assert anonymous.json()["code"] == "AUTH_INVALID_CREDENTIALS"

    # Another user's token does not unlock someone else's export.
    bob = _login(client, "bob", "bob-password", "req_bob")
    foreign = client.get(path, headers={"Authorization": f"Bearer {bob}"})
    assert foreign.status_code == 404

    # An admin token does (ADR-012, ND-GAP-04).
    admin = _login(client, "admin", "admin-password", "req_admin")
    admin_ok = client.get(path, headers={"Authorization": f"Bearer {admin}"})
    assert admin_ok.status_code == 200
    assert admin_ok.content == ok.content

    # A tampered signature is refused before any authorization check.
    forged = signature[:-1] + ("0" if signature[-1] != "0" else "1")
    tampered = client.get(
        f"/api/v1/d/{export_id}?e={expiry}&s={forged}",
        headers={"Authorization": f"Bearer {alice}"},
    )
    assert tampered.status_code == 403
    assert tampered.json()["code"] == "RESOURCE_FORBIDDEN"

    # Missing link parameters are treated as a forged link.
    bare = client.get(f"/api/v1/d/{export_id}", headers={"Authorization": f"Bearer {alice}"})
    assert bare.status_code == 403
