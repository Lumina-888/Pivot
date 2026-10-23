"""Agent execution binding (W2): graph outcomes drive Run state and SSE.

With PIVOT_QA_ENGINE=agent, HTTP runs execute through the LangGraph agent
and its outcomes land on the existing Run state machine: completed ->
answered, insufficient_evidence -> refused, provider failure -> failed,
with the same publish semantics (persist, token, citation, terminal
events) as the orchestrator. Not GATE-P0 verified.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient
from pivot.http import assemble_runtime
from pivot.qa.agent_model import AgentModel, AgentModelConfig

from tests.integration.pipeline.test_FR_AGENT_009_agent_engine_wiring import (
    QUESTION,
    UPLOAD_TEXT,
    _Client,
    _login,
    _memory_qdrant_client,
    _pdf_bytes,
    _scripted_model,
    _settings,
)

_TERMINAL = {"answered", "refused", "failed", "uncertain", "cancelled"}


def _db_url(tmp_path, name: str = "pivot.db") -> str:
    return f"sqlite+pysqlite:///{(tmp_path / name).as_posix()}"


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


def _headers(token: str, request_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Request-ID": request_id}


def _agent_client(tmp_path, model) -> tuple[TestClient, str]:
    assembly = assemble_runtime(
        _settings(
            _db_url(tmp_path),
            _Client(),
            _memory_qdrant_client(),
            qa_engine="agent",
            agent_model=model,
        )
    )
    http = TestClient(assembly.app, base_url="https://testserver")
    return http, _login(assembly)


def _upload(http: TestClient, token: str) -> None:
    response = http.post(
        "/api/v1/documents",
        data={"title": "出差制度"},
        files={"file": ("travel.pdf", _pdf_bytes(UPLOAD_TEXT), "application/pdf")},
        headers=_headers(token, "req_w2_upload"),
    )
    assert response.status_code == 201


def _conversation(http: TestClient, token: str) -> str:
    response = http.post(
        "/api/v1/conversations",
        json={"title": "出差", "scope_type": "global"},
        headers=_headers(token, "req_w2_conv"),
    )
    assert response.status_code == 201
    return response.json()["conversation_id"]


def _run_until_terminal(http: TestClient, token: str, conversation_id: str, question: str):
    created = http.post(
        "/api/v1/runs",
        json={
            "conversation_id": conversation_id,
            "question": question,
            "idempotency_key": f"w2-{question[:8]}-{time.time_ns()}",
        },
        headers=_headers(token, "req_w2_run"),
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]
    state = ""
    for _ in range(50):
        got = http.get(f"/api/v1/runs/{run_id}", headers=_headers(token, "req_w2_get"))
        assert got.status_code == 200
        state = got.json()["state"]
        if state in _TERMINAL:
            break
        time.sleep(0.05)
    return run_id, state


def test_FR_AGENT_008_agent_run_answers_and_streams(tmp_path):
    pytest.importorskip("llama_index.core")
    sink: list = []
    http, token = _agent_client(tmp_path, _scripted_model(sink))
    _upload(http, token)
    conversation_id = _conversation(http, token)
    run_id, state = _run_until_terminal(http, token, conversation_id, QUESTION)
    assert state == "answered"
    assert len(sink) == 3
    events = http.get(
        f"/api/v1/runs/{run_id}/events", headers=_headers(token, "req_w2_events")
    )
    assert events.status_code == 200
    frames = _parse_sse(events.text)
    names = [name for name, _ in frames]
    assert "token" in names
    assert "citation" in names
    assert names[-1] == "completed"
    token_text = next(
        data["payload"]["text"] for name, data in frames if name == "token"
    )
    assert "travel" in token_text


def test_FR_AGENT_008_agent_run_refuses_without_evidence(tmp_path):
    pytest.importorskip("llama_index.core")
    sink: list = []
    http, token = _agent_client(tmp_path, _scripted_model(sink))
    conversation_id = _conversation(http, token)
    _run_id, state = _run_until_terminal(http, token, conversation_id, QUESTION)
    assert state == "refused"
    assert len(sink) >= 1


class _FailingTransport:
    def invoke(self, messages, tools):
        raise RuntimeError("provider down")


def test_FR_AGENT_008_agent_run_fails_closed_on_provider_error(tmp_path):
    pytest.importorskip("llama_index.core")
    sink: list = []
    model = AgentModel(
        AgentModelConfig("fake-model", "fake-key", None),
        transport=_FailingTransport(),
        attempt_sink=sink.append,
    )
    http, token = _agent_client(tmp_path, model)
    conversation_id = _conversation(http, token)
    run_id, state = _run_until_terminal(http, token, conversation_id, QUESTION)
    assert state == "failed"
    got = http.get(f"/api/v1/runs/{run_id}", headers=_headers(token, "req_w2_get"))
    assert got.json()["error_code"] == "PROVIDER_TEMPORARY_ERROR"
    assert sink and sink[0]["outcome"] == "error"
