"""Postgres Run / EventLog survive a new runtime assembly. Not GATE-P0 verified."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from pivot.db.runs import SqlAlchemyRunStore
from pivot.http import RuntimeSettings, assemble_runtime, assemble_runtime_app
from pivot.runs.service import InMemoryRunStore, RunService
from pivot.stream.events import TERMINAL_EVENTS

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "postgres-run-eventlog.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"


def _settings(url: str, **overrides: object) -> RuntimeSettings:
    values: dict[str, object] = {
        "storage": "postgres",
        "database_url": url,
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
    }
    values.update(overrides)
    return RuntimeSettings(**values)


def _client(url: str) -> TestClient:
    return TestClient(assemble_runtime_app(_settings(url)), base_url="https://testserver")


def _login(client: TestClient, request_id: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
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


def test_NFR_OBS_runtime_postgres_wires_runs_and_event_log(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    assembly = assemble_runtime(_settings(url))
    assert isinstance(assembly.run_rows, SqlAlchemyRunStore)
    memory = assemble_runtime(
        RuntimeSettings(
            storage="memory",
            token_secret="runtime-test-secret",
            access_ttl=60,
            refresh_ttl=3600,
            export_ttl=3600,
            download_ttl=300,
            export_public_base="https://files.pivot.test",
            retrieval_k=4,
            argon2_time_cost=1,
            argon2_memory_cost=8,
            argon2_parallelism=1,
        )
    )
    assert isinstance(memory.runs, RunService)
    assert isinstance(memory.run_rows, InMemoryRunStore)


def test_FR_STREAM_001_run_survives_new_assembly(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    first = _client(url)
    token = _login(first, "req_pg_run_login_1")
    created = first.post(
        "/api/v1/conversations",
        json={"title": "迟到规则", "scope_type": "global"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_run_conv",
        },
    )
    assert created.status_code == 201
    conversation_id = created.json()["conversation_id"]
    payload = {
        "conversation_id": conversation_id,
        "question": "迟到三次怎么处理",
        "idempotency_key": "idem-pg-run",
    }
    run = first.post(
        "/api/v1/runs",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_run_create",
        },
    )
    assert run.status_code == 200
    run_id = run.json()["run_id"]
    message_id = run.json()["message_id"]
    assert run.json()["initial_state"]["state"] == "received"
    events = first.get(
        f"/api/v1/runs/{run_id}/events",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_run_sse",
        },
    )
    assert events.status_code == 200
    frames = _parse_sse(events.text)
    assert frames[-1][0] in TERMINAL_EVENTS

    second = _client(url)
    replayed = _login(second, "req_pg_run_login_2")
    detail = second.get(
        f"/api/v1/runs/{run_id}",
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_run_get",
        },
    )
    assert detail.status_code == 200
    assert detail.json()["run_id"] == run_id
    assert detail.json()["message_id"] == message_id
    assert detail.json()["conversation_id"] == conversation_id
    assert detail.json()["question"] == "迟到三次怎么处理"
    assert detail.json()["state"] in {"answered", "uncertain", "refused", "failed", "cancelled"}
    same = second.post(
        "/api/v1/runs",
        json=payload,
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_run_idem",
        },
    )
    assert same.status_code == 200
    assert same.json()["run_id"] == run_id
    conflict = second.post(
        "/api/v1/runs",
        json={**payload, "question": "另一问题"},
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_run_conflict",
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_FR_STREAM_002_003_event_log_survives_new_assembly(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    first = _client(url)
    token = _login(first, "req_pg_sse_login_1")
    created = first.post(
        "/api/v1/conversations",
        json={"title": "迟到规则", "scope_type": "global"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_sse_conv",
        },
    )
    conversation_id = created.json()["conversation_id"]
    run = first.post(
        "/api/v1/runs",
        json={
            "conversation_id": conversation_id,
            "question": "迟到三次怎么处理",
            "idempotency_key": "idem-pg-sse",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_sse_create",
        },
    )
    run_id = run.json()["run_id"]
    assert run.json()["initial_state"]["state"] == "received"
    original = first.get(
        f"/api/v1/runs/{run_id}/events",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_sse_orig",
        },
    )
    assert original.status_code == 200
    first_frames = _parse_sse(original.text)
    assert first_frames
    assert [data["seq"] for _name, data in first_frames] == list(
        range(1, len(first_frames) + 1)
    )
    terminals = [name for name, _data in first_frames if name in TERMINAL_EVENTS]
    assert len(terminals) == 1

    second = _client(url)
    replayed = _login(second, "req_pg_sse_login_2")
    stream = second.get(
        f"/api/v1/runs/{run_id}/events",
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_sse_replay",
        },
    )
    assert stream.status_code == 200
    assert "text/event-stream" in stream.headers["content-type"]
    frames = _parse_sse(stream.text)
    assert [name for name, _data in frames] == [name for name, _data in first_frames]
    assert [data["seq"] for _name, data in frames] == [
        data["seq"] for _name, data in first_frames
    ]
    assert frames[-1][0] in TERMINAL_EVENTS
    for _name, data in frames:
        assert "thinking" not in str(data)
        assert "SYSTEM_PROMPT" not in str(data)
    later = second.get(
        f"/api/v1/runs/{run_id}/events",
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_sse_last",
            "Last-Event-ID": "2",
        },
    )
    skipped = _parse_sse(later.text)
    assert skipped
    assert all(data["seq"] > 2 for _name, data in skipped)


def test_FR_RBAC_002_messages_survive_new_assembly(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    first = _client(url)
    token = _login(first, "req_pg_msg_login_1")
    created = first.post(
        "/api/v1/conversations",
        json={"title": "迟到规则", "scope_type": "global"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_msg_conv",
        },
    )
    conversation_id = created.json()["conversation_id"]
    run = first.post(
        "/api/v1/runs",
        json={
            "conversation_id": conversation_id,
            "question": "迟到三次怎么处理",
            "idempotency_key": "idem-pg-msg",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_msg_run",
        },
    )
    run_id = run.json()["run_id"]
    events = first.get(
        f"/api/v1/runs/{run_id}/events",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_msg_sse",
        },
    )
    assert events.status_code == 200
    assert _parse_sse(events.text)[-1][0] in TERMINAL_EVENTS

    second = _client(url)
    replayed = _login(second, "req_pg_msg_login_2")
    messages = second.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_msg_list",
        },
    )
    assert messages.status_code == 200
    items = messages.json()["items"]
    senders = [item["sender"] for item in items]
    assert "user" in senders
    assert "assistant" in senders
    user = next(item for item in items if item["sender"] == "user")
    assistant = next(item for item in items if item["sender"] == "assistant")
    assert user["content"] == "迟到三次怎么处理"
    assert assistant["run_id"] == run_id
    assert assistant["status"] in {"answered", "uncertain", "refused", "failed", "cancelled"}
    assert "SYSTEM_PROMPT" not in str(messages.json())


def test_GATE_P0_003_not_verified_by_postgres_runs():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "sqlite" in evidence.lower() or "SQLAlchemy" in evidence
    assert "redis" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
