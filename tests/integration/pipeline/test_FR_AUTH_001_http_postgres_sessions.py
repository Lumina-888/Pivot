"""Postgres refresh and conversations survive a new runtime assembly."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pivot.db.conversations import SqlAlchemyConversationStore
from pivot.db.refresh import SqlAlchemyRefreshTokenStore
from pivot.http import RuntimeSettings, assemble_runtime, assemble_runtime_app
from pivot.http.memory import InMemoryRefreshStore
from pivot.runs.conversations import ConversationService, InMemoryConversationStore

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "postgres-refresh-conversations.md"
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


def test_NFR_OBS_runtime_postgres_wires_refresh_and_conversations(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    assembly = assemble_runtime(_settings(url))
    assert isinstance(assembly.refresh_tokens, SqlAlchemyRefreshTokenStore)
    assert isinstance(assembly.conversation_rows, SqlAlchemyConversationStore)
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
    assert isinstance(memory.refresh_tokens, InMemoryRefreshStore)
    assert isinstance(memory.conversations, ConversationService)
    assert isinstance(memory.conversation_rows, InMemoryConversationStore)


def test_FR_AUTH_001_refresh_survives_new_assembly(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    first = _client(url)
    login = first.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_pg_refresh_login"},
    )
    assert login.status_code == 200
    first_access = login.json()["access_token"]
    refresh_cookie = login.cookies.get("refresh_token")
    assert refresh_cookie
    assert "refresh_token" not in login.json()

    second = _client(url)
    second.cookies.set("refresh_token", refresh_cookie)
    refreshed = second.post(
        "/api/v1/auth/refresh",
        headers={"X-Request-ID": "req_pg_refresh"},
    )
    assert refreshed.status_code == 200
    payload = refreshed.json()
    assert payload["token_type"] == "Bearer"
    assert payload["refresh_token_cookie"] is True
    assert payload["access_token"]
    assert payload["access_token"] != first_access
    listed = second.get(
        "/api/v1/conversations",
        headers={
            "Authorization": f"Bearer {payload['access_token']}",
            "X-Request-ID": "req_pg_refresh_list",
        },
    )
    assert listed.status_code == 200

    replay_client = _client(url)
    replay_client.cookies.set("refresh_token", refresh_cookie)
    replay = replay_client.post(
        "/api/v1/auth/refresh",
        headers={"X-Request-ID": "req_pg_refresh_old"},
    )
    assert replay.status_code == 401
    assert replay.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_FR_RBAC_002_conversation_survives_new_assembly(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    first = _client(url)
    token = _login(first, "req_pg_conv_login_1")
    created = first.post(
        "/api/v1/conversations",
        json={"title": "迟到规则", "scope_type": "global"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_conv_create",
        },
    )
    assert created.status_code == 201
    conversation_id = created.json()["conversation_id"]
    assert created.json()["title"] == "迟到规则"
    assert created.json()["scope_type"] == "global"

    second = _client(url)
    replayed = _login(second, "req_pg_conv_login_2")
    detail = second.get(
        f"/api/v1/conversations/{conversation_id}",
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_conv_get",
        },
    )
    assert detail.status_code == 200
    assert detail.json()["conversation_id"] == conversation_id
    assert detail.json()["title"] == "迟到规则"
    listed = second.get(
        "/api/v1/conversations",
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_conv_list",
        },
    )
    assert listed.status_code == 200
    ids = {item["conversation_id"] for item in listed.json()["items"]}
    assert conversation_id in ids

    deleted = second.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_conv_del",
        },
    )
    assert deleted.status_code == 204
    third = _client(url)
    after = _login(third, "req_pg_conv_login_3")
    missing = third.get(
        f"/api/v1/conversations/{conversation_id}",
        headers={
            "Authorization": f"Bearer {after}",
            "X-Request-ID": "req_pg_conv_missing",
        },
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "RESOURCE_NOT_FOUND"


def test_GATE_P0_003_not_verified_by_postgres_sessions():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "sqlite" in evidence.lower() or "SQLAlchemy" in evidence
    assert "redis" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
