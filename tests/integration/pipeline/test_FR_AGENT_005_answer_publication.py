"""Real HTTP Run/SSE/message/export boundaries with a controlled model transport."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from harness import Pipeline, persisted_from_run
from pivot.http import create_app
from pivot.qa.orchestrator import QaOrchestrator
from pivot.qa.ports import EvidenceHit, RetrievalResult
from pivot.qa.writer import HttpDraftWriter
from pivot.retrieval.fakes import ScriptedJsonHttpClient

FACT = "迟到三次以上记为旷工。"
UNVERIFIED = "Every employee receives a million-dollar bonus."


class RetrievalFixture:
    def retrieve(self, question, *, scope_type, scope_document_id, principal_id):
        return RetrievalResult("ok", (
            EvidenceHit("chk_attendance", "doc_attendance", "ver_attendance", FACT,
                        "page=1", external_llm_allowed=True),
        ))


@pytest.mark.parametrize("kind", ["plain", "unsupported", "mixed", "verified"])
def test_FR_AGENT_005_http_sse_messages_and_exports_never_publish_unverified_text(kind):
    pipeline = Pipeline()
    conversation = pipeline.conversations.create(
        owner_id="usr_alice", title="Answer safety", request_id="req_conv"
    )
    pipeline.resources.conversations[conversation.id] = "usr_alice"
    claims = [{"text": FACT, "evidence_index": 0}]
    if kind == "unsupported":
        claims = [{"text": UNVERIFIED, "evidence_index": 0}]
    elif kind == "mixed":
        claims.append({"text": UNVERIFIED, "evidence_index": 0})
    content = UNVERIFIED if kind == "plain" else json.dumps({
        "markdown": UNVERIFIED, "claims": claims,
    })
    transport = ScriptedJsonHttpClient([
        {"choices": [{"message": {"content": content}}]}
    ])
    writer = HttpDraftWriter(
        transport, endpoint="https://llm.test/v1/chat/completions",
        model="fixture-model", api_key="fixture-model-key",
    )
    client = TestClient(create_app(
        auth=pipeline.auth, runs=pipeline.runs,
        qa=QaOrchestrator(RetrievalFixture(), writer=writer),
        conversations=pipeline.conversations, exports=pipeline.exports,
    ), base_url="https://testserver")
    token = client.post("/api/v1/auth/login", json={
        "username": "alice", "password": "correct-password",
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"conversation_id": conversation.id, "question": "迟到怎么处理？",
               "idempotency_key": "idem_answer_safety"}
    created = client.post("/api/v1/runs", json=payload, headers=headers)
    assert created.status_code == 200
    run_id = created.json()["run_id"]
    run = client.get(f"/api/v1/runs/{run_id}", headers=headers).json()
    assert run["state"] == ("answered" if kind == "verified" else "uncertain")
    stream = client.get(f"/api/v1/runs/{run_id}/events", headers=headers)
    assert stream.status_code == 200
    assert UNVERIFIED not in stream.text
    if kind != "verified":
        assert "event: token" not in stream.text
        assert "event: citation" not in stream.text
        assert "event: completed" not in stream.text
    else:
        frames = pipeline.runs.log(run_id).replay()
        text = "".join(data["payload"]["text"] for name, data in frames if name == "token")
        assert text == FACT
        assert frames[-1][0] == "completed"
    messages = client.get(
        f"/api/v1/conversations/{conversation.id}/messages", headers=headers,
    )
    assert messages.status_code == 200
    assert UNVERIFIED not in messages.text
    bundle = pipeline.runs.get(run_id, "req_export")
    # Controlled persistence fixture; export must consume the final result, never rerun QA.
    pipeline.answers.add_answer(persisted_from_run(bundle))
    pipeline.export_access.conversation_owners[conversation.id] = "usr_alice"
    exported = client.post("/api/v1/exports", json={
        "source_type": "conversation", "source_id": conversation.id, "format": "markdown",
    }, headers=headers)
    assert exported.status_code == 202
    export_id = exported.json()["export_id"]
    task = pipeline.export_repo.get(export_id)
    assert task is not None and task.storage_key is not None
    document = pipeline.export_objects.get(task.storage_key).decode("utf-8")
    assert UNVERIFIED not in document
    assert pipeline.answers.qa_invocations == 0
    repeated = client.post("/api/v1/runs", json=payload, headers=headers)
    assert repeated.json()["run_id"] == run_id
    assert len(transport.calls) == 1
