"""HTTP /api/v1/runs create, SSE replay and cancel. Not GATE-P0 verified."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from harness import Pipeline, RetrievalBridge
from pivot.http import create_app
from pivot.qa.orchestrator import QaOrchestrator
from pivot.stream.events import TERMINAL_EVENTS


def _client(pipeline: Pipeline, *, mount_runs: bool = True) -> TestClient:
    retrieval = pipeline.retrieval_for_ready_chunks()
    qa = QaOrchestrator(RetrievalBridge(retrieval)) if mount_runs else None
    runs = pipeline.runs if mount_runs else None
    return TestClient(
        create_app(
            auth=pipeline.auth,
            retrieval=retrieval,
            runs=runs,
            qa=qa,
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


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    frames: list[tuple[str, dict]] = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        name = ""
        data = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = line.split(":", 1)[1].strip()
        frames.append((name, json.loads(data)))
    return frames


def test_FR_RBAC_001_http_runs_require_bearer():
    pipeline = Pipeline()
    client = _client(pipeline)
    response = client.post(
        "/api/v1/runs",
        json={
            "conversation_id": "conv_anon",
            "question": "late three times?",
            "idempotency_key": "idem-anon",
        },
        headers={"X-Request-ID": "req_anon"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_FR_STREAM_001_http_create_run_is_idempotent_and_answers():
    pipeline = Pipeline()
    pipeline.ingest_policy_pdf("usr_alice")
    client = _client(pipeline)
    token = _login(client, "alice", "correct-password", "req_login")
    payload = {
        "conversation_id": "conv_alice",
        "question": "late three times written warning?",
        "idempotency_key": "idem-alice-1",
    }
    first = client.post(
        "/api/v1/runs",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_run_1"},
    )
    second = client.post(
        "/api/v1/runs",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_run_2"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["run_id"] == second.json()["run_id"]
    assert first.json()["message_id"] == second.json()["message_id"]
    assert first.json()["request_id"] == "req_run_1"
    assert first.json()["initial_state"]["state"] == "answered"
    detail = client.get(
        f"/api/v1/runs/{first.json()['run_id']}",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_get"},
    )
    assert detail.status_code == 200
    assert detail.json()["state"] == "answered"
    assert "SYSTEM_PROMPT" not in str(detail.json())


def test_FR_STREAM_001_http_same_key_different_question_conflicts():
    pipeline = Pipeline()
    pipeline.ingest_policy_pdf("usr_alice")
    client = _client(pipeline)
    token = _login(client, "alice", "correct-password", "req_login")
    headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req_a"}
    first = client.post(
        "/api/v1/runs",
        json={
            "conversation_id": "conv_alice",
            "question": "late three times?",
            "idempotency_key": "idem-dup",
        },
        headers=headers,
    )
    conflict = client.post(
        "/api/v1/runs",
        json={
            "conversation_id": "conv_alice",
            "question": "another question",
            "idempotency_key": "idem-dup",
        },
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_b"},
    )
    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert conflict.json()["request_id"] == "req_b"


def test_FR_STREAM_002_003_http_sse_is_monotonic_and_replays():
    pipeline = Pipeline()
    pipeline.ingest_policy_pdf("usr_alice")
    client = _client(pipeline)
    token = _login(client, "alice", "correct-password", "req_login")
    created = client.post(
        "/api/v1/runs",
        json={
            "conversation_id": "conv_alice",
            "question": "late three times written warning?",
            "idempotency_key": "idem-sse",
        },
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_sse"},
    )
    run_id = created.json()["run_id"]
    stream = client.get(
        f"/api/v1/runs/{run_id}/events",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_events"},
    )
    assert stream.status_code == 200
    assert "text/event-stream" in stream.headers["content-type"]
    frames = _parse_sse(stream.text)
    seqs = [data["seq"] for _name, data in frames]
    assert seqs == list(range(1, len(seqs) + 1))
    terminals = [name for name, _data in frames if name in TERMINAL_EVENTS]
    assert len(terminals) == 1
    assert frames[-1][0] in TERMINAL_EVENTS
    for _name, data in frames:
        assert "thinking" not in str(data)
        assert "SYSTEM_PROMPT" not in str(data)
    replayed = client.get(
        f"/api/v1/runs/{run_id}/events",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_replay",
            "Last-Event-ID": "2",
        },
    )
    later = _parse_sse(replayed.text)
    assert later
    assert all(data["seq"] > 2 for _name, data in later)


def test_FR_RBAC_002_http_run_owner_isolation():
    pipeline = Pipeline()
    pipeline.ingest_policy_pdf("usr_alice")
    client = _client(pipeline)
    alice = _login(client, "alice", "correct-password", "req_alice")
    created = client.post(
        "/api/v1/runs",
        json={
            "conversation_id": "conv_alice",
            "question": "late three times?",
            "idempotency_key": "idem-alice",
        },
        headers={"Authorization": f"Bearer {alice}", "X-Request-ID": "req_alice_run"},
    )
    run_id = created.json()["run_id"]
    bob = _login(client, "bob", "bob-password", "req_bob")
    hidden = client.get(
        f"/api/v1/runs/{run_id}",
        headers={"Authorization": f"Bearer {bob}", "X-Request-ID": "req_bob_get"},
    )
    events = client.get(
        f"/api/v1/runs/{run_id}/events",
        headers={"Authorization": f"Bearer {bob}", "X-Request-ID": "req_bob_sse"},
    )
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "RESOURCE_NOT_FOUND"
    assert events.status_code == 404


def test_FR_STREAM_004_http_cancel_does_not_rewrite_terminal():
    pipeline = Pipeline()
    pipeline.ingest_policy_pdf("usr_alice")
    client = _client(pipeline)
    token = _login(client, "alice", "correct-password", "req_login")
    created = client.post(
        "/api/v1/runs",
        json={
            "conversation_id": "conv_alice",
            "question": "late three times?",
            "idempotency_key": "idem-cancel",
        },
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_c"},
    )
    run_id = created.json()["run_id"]
    cancelled = client.post(
        f"/api/v1/runs/{run_id}/cancel",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_cancel"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["run_id"] == run_id
    assert cancelled.json()["state"] == "answered"


def test_NFR_OBS_auth_only_app_does_not_mount_runs():
    pipeline = Pipeline()
    app = create_app(auth=pipeline.auth)
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any("/runs" in path for path in paths)
    response = TestClient(app, base_url="https://testserver").post("/api/v1/runs")
    assert response.status_code == 404
