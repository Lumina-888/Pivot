"""HTTP /api/v1/conversations CRUD and messages. Not GATE-P0 verified."""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline, RetrievalBridge
from pivot.http import create_app
from pivot.qa.orchestrator import QaOrchestrator
from pivot.runs.conversations import ConversationService


def _client(pipeline: Pipeline, *, mount: bool = True) -> TestClient:
    conversations = None
    qa = None
    retrieval = pipeline.retrieval_for_ready_chunks()
    if mount:
        conversations = ConversationService(runs=pipeline.runs)
        pipeline.conversations = conversations
        qa = QaOrchestrator(RetrievalBridge(retrieval))
    return TestClient(
        create_app(
            auth=pipeline.auth,
            retrieval=retrieval,
            runs=pipeline.runs if mount else None,
            qa=qa,
            conversations=conversations,
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


def test_FR_RBAC_002_http_conversations_require_bearer():
    client = _client(Pipeline())
    response = client.get("/api/v1/conversations", headers={"X-Request-ID": "req_anon"})
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_FR_RBAC_002_http_create_list_and_owner_isolation():
    pipeline = Pipeline()
    client = _client(pipeline)
    alice = _login(client, "alice", "correct-password", "req_alice")
    created = client.post(
        "/api/v1/conversations",
        json={"title": "迟到规则", "scope_type": "global"},
        headers={"Authorization": f"Bearer {alice}", "X-Request-ID": "req_create"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "迟到规则"
    assert body["scope_type"] == "global"
    assert body["scope_document_id"] is None
    assert body["owner_id"] == "usr_alice"
    assert body["conversation_id"].startswith("conv_")
    assert body["created_at"].endswith("Z")
    listed = client.get(
        "/api/v1/conversations",
        headers={"Authorization": f"Bearer {alice}", "X-Request-ID": "req_list"},
    )
    assert listed.status_code == 200
    assert listed.json().get("pagination") is None
    ids = {item["conversation_id"] for item in listed.json()["items"]}
    assert body["conversation_id"] in ids
    bob = _login(client, "bob", "bob-password", "req_bob")
    hidden = client.get(
        f"/api/v1/conversations/{body['conversation_id']}",
        headers={"Authorization": f"Bearer {bob}", "X-Request-ID": "req_bob_get"},
    )
    bob_list = client.get(
        "/api/v1/conversations",
        headers={"Authorization": f"Bearer {bob}", "X-Request-ID": "req_bob_list"},
    )
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "RESOURCE_NOT_FOUND"
    bob_ids = {item["conversation_id"] for item in bob_list.json()["items"]}
    assert body["conversation_id"] not in bob_ids


def test_FR_RBAC_002_http_document_scope_requires_document_id():
    client = _client(Pipeline())
    token = _login(client, "alice", "correct-password", "req_login")
    missing = client.post(
        "/api/v1/conversations",
        json={"title": "本文提问", "scope_type": "document"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_scope"},
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "RESOURCE_NOT_FOUND"
    created = client.post(
        "/api/v1/conversations",
        json={
            "title": "本文提问",
            "scope_type": "document",
            "scope_document_id": "doc_handbook",
        },
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_ok"},
    )
    assert created.status_code == 201
    assert created.json()["scope_type"] == "document"
    assert created.json()["scope_document_id"] == "doc_handbook"


def test_FR_STREAM_001_http_messages_come_from_persisted_run():
    pipeline = Pipeline()
    pipeline.ingest_policy_pdf("usr_alice")
    client = _client(pipeline)
    token = _login(client, "alice", "correct-password", "req_login")
    created = client.post(
        "/api/v1/conversations",
        json={"title": "迟到三次", "scope_type": "global"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_conv"},
    )
    conversation_id = created.json()["conversation_id"]
    run = client.post(
        "/api/v1/runs",
        json={
            "conversation_id": conversation_id,
            "question": "late three times written warning?",
            "idempotency_key": "idem-conv-1",
        },
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_run"},
    )
    assert run.status_code == 200
    messages = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_msg"},
    )
    assert messages.status_code == 200
    items = messages.json()["items"]
    senders = [item["sender"] for item in items]
    assert "user" in senders
    assert "assistant" in senders
    blob = str(messages.json())
    assert "SYSTEM_PROMPT" not in blob
    assert "thinking" not in blob.lower()
    user = next(item for item in items if item["sender"] == "user")
    assistant = next(item for item in items if item["sender"] == "assistant")
    assert user["content"] == "late three times written warning?"
    assert assistant["run_id"] == run.json()["run_id"]
    assert assistant["status"] == "answered"
    assert assistant["content"]


def test_FR_RBAC_002_http_delete_hides_conversation():
    client = _client(Pipeline())
    token = _login(client, "alice", "correct-password", "req_login")
    created = client.post(
        "/api/v1/conversations",
        json={"title": "待删", "scope_type": "global"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_create"},
    )
    conversation_id = created.json()["conversation_id"]
    deleted = client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_del"},
    )
    assert deleted.status_code == 204
    missing = client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_get"},
    )
    listed = client.get(
        "/api/v1/conversations",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_list"},
    )
    assert missing.status_code == 404
    ids = {item["conversation_id"] for item in listed.json()["items"]}
    assert conversation_id not in ids


def test_NFR_OBS_auth_only_app_does_not_mount_conversations():
    pipeline = Pipeline()
    app = create_app(auth=pipeline.auth)
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any("/conversations" in path for path in paths)
    response = TestClient(app, base_url="https://testserver").get("/api/v1/conversations")
    assert response.status_code == 404
