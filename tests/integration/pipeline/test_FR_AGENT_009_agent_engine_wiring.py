"""Agent engine wiring (W1): bootstrap assembles the LangGraph QA agent.

The runtime gains a QA engine switch. The default stays the deterministic
orchestrator pipeline; `agent` assembles the ND-AGENT-05 model adapter,
budget policy and structured finalizer into a runner over the same QA
retriever. Execution binding to Run/SSE is W2. Not GATE-P0 verified.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.qa.agent_model import AgentModel, AgentModelConfig
from test_FR_RAG_llama_qdrant_backend import _seed_admin_user

UPLOAD_TEXT = "business travel requires an application three days in advance."
QUESTION = "business travel application three days"


def _pdf_bytes(text: str) -> bytes:
    return f"%PDF-1.4\n({text}) Tj\n%%EOF".encode("utf-8")


class _Client:
    """In-memory Qdrant client double, shaped like the SDK wrapper."""

    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.points: dict[str, dict[str, tuple[list[float], dict]]] = {}

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, collection_name: str, *, vector_size: int, distance: str) -> None:
        self.collections.add(collection_name)
        self.points.setdefault(collection_name, {})

    def upsert(self, collection_name: str, points) -> None:
        bucket = self.points.setdefault(collection_name, {})
        for point in points:
            bucket[str(point["id"])] = (list(point["vector"]), dict(point["payload"]))

    def search(self, collection_name, query_vector, limit=10, query_filter=None):
        query = list(query_vector)
        hits = [
            SimpleNamespace(
                id=pid,
                score=sum(a * b for a, b in zip(query, vector, strict=False)),
                payload=payload,
            )
            for pid, (vector, payload) in self.points.get(collection_name, {}).items()
        ]
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def delete(self, collection_name, points_selector=None) -> None:
        return None

    def scroll(self, collection_name, *, limit, offset=None):
        items = sorted(self.points.get(collection_name, {}).items())
        start = int(offset) if offset is not None else 0
        page = items[start : start + limit]
        next_offset = start + limit
        return (
            [SimpleNamespace(id=pid, payload=payload) for pid, (_, payload) in page],
            str(next_offset) if next_offset < len(items) else None,
        )


def _memory_qdrant_client():
    qdrant_client = pytest.importorskip("qdrant_client")
    return qdrant_client.QdrantClient(location=":memory:")


def _settings(db_url: str, client: _Client, raw_client, **overrides: object) -> RuntimeSettings:
    values: dict[str, object] = {
        "storage": "postgres",
        "database_url": db_url,
        "create_schema": True,
        "token_secret": "runtime-test-secret",
        "access_ttl": 60,
        "refresh_ttl": 3600,
        "export_ttl": 3600,
        "download_ttl": 300,
        "export_public_base": "https://files.pivot.test",
        "bootstrap_username": "admin",
        "bootstrap_password": "runtime-admin-password",
        "retrieval_k": 4,
        "argon2_time_cost": 1,
        "argon2_memory_cost": 8,
        "argon2_parallelism": 1,
        "vector_store": "qdrant",
        "qdrant_endpoint": "vectors.test:443",
        "qdrant_collection": "pivot-chunks",
        "qdrant_ensure_collection": True,
        "qdrant_vector_size": 4,
        "qdrant_distance": "Cosine",
        "vector_store_client": client,
        "llama_qdrant_client": raw_client,
        "retrieval_backend": "llama",
        "bm25_k1": 1.2,
        "bm25_b": 0.75,
    }
    values.update(overrides)
    return RuntimeSettings(**values)


def _db_url(tmp_path, name: str = "pivot.db") -> str:
    return f"sqlite+pysqlite:///{(tmp_path / name).as_posix()}"


class _ScriptedTransport:
    """Decide protocol double: search, read the first hit, then finalize."""

    def invoke(self, messages, tools):
        tool_contents = [
            message.content
            for message in messages
            if getattr(message, "type", None) == "tool"
        ]
        if not tool_contents:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": QUESTION},
                        "id": "call-search",
                        "type": "tool_call",
                    }
                ],
            )
        last = json.loads(tool_contents[-1])
        if last.get("evidence_ids"):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_evidence",
                        "args": {"evidence_id": last["evidence_ids"][0]},
                        "id": "call-read",
                        "type": "tool_call",
                    }
                ],
            )
        return AIMessage(content="")


def _scripted_model(sink: list) -> AgentModel:
    return AgentModel(
        AgentModelConfig("fake-model", "fake-key", None),
        transport=_ScriptedTransport(),
        attempt_sink=sink.append,
    )


def _login(assembly) -> str:
    client = TestClient(assembly.app, base_url="https://testserver")
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_w1_login"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_FR_AGENT_009_agent_engine_assembles_runner_and_answers(tmp_path):
    pytest.importorskip("llama_index.core")
    sink: list = []
    assembly = assemble_runtime(
        _settings(
            _db_url(tmp_path),
            _Client(),
            _memory_qdrant_client(),
            qa_engine="agent",
            agent_model=_scripted_model(sink),
        )
    )
    # S2: the agent run resolves library visibility from live user facts,
    # so the synthetic "usr_admin" principal must be a real admin account.
    _seed_admin_user(assembly)
    assert assembly.qa_engine == "agent"
    assert assembly.agent_runner is not None
    token = _login(assembly)
    http = TestClient(assembly.app, base_url="https://testserver")
    upload = http.post(
        "/api/v1/documents",
        data={"title": "出差制度"},
        files={"file": ("travel.pdf", _pdf_bytes(UPLOAD_TEXT), "application/pdf")},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_w1"},
    )
    assert upload.status_code == 201
    result = assembly.agent_runner.run(
        QUESTION,
        run_id="run-w1",
        principal_id="usr_admin",
        conversation_id="conv-w1",
    )
    final_answer = result.get("final_answer") or {}
    assert final_answer.get("answer")
    assert "travel" in final_answer["answer"]
    assert len(sink) == 3
    assert all(record["outcome"] == "success" for record in sink)
    assert all(record["role"] == "primary" for record in sink)


def test_FR_AGENT_009_default_engine_is_pipeline_without_runner(tmp_path):
    assembly = assemble_runtime(
        _settings(_db_url(tmp_path), _Client(), _memory_qdrant_client())
    )
    assert assembly.qa_engine == "pipeline"
    assert assembly.agent_runner is None


def test_FR_AGENT_009_agent_engine_requires_model_configuration(tmp_path, monkeypatch):
    for name in (
        "PIVOT_AGENT_MODEL_ENDPOINT",
        "PIVOT_AGENT_MODEL_MODEL",
        "PIVOT_AGENT_MODEL_API_KEY",
        "PIVOT_AGENT_MODEL_FALLBACK_ENDPOINT",
        "PIVOT_AGENT_MODEL_FALLBACK_MODEL",
        "PIVOT_AGENT_MODEL_FALLBACK_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError):
        assemble_runtime(
            _settings(
                _db_url(tmp_path), _Client(), _memory_qdrant_client(), qa_engine="agent"
            )
        )


def test_FR_AGENT_009_qa_engine_setting_rejects_unknown_value(tmp_path):
    with pytest.raises(RuntimeError):
        _settings(_db_url(tmp_path), _Client(), _memory_qdrant_client(), qa_engine="bogus")
