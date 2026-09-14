"""Postgres export tasks survive a new runtime assembly. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pivot.db.exports import SqlAlchemyExportRepository
from pivot.exports.models import PersistedAnswer
from pivot.exports.repository import InMemoryExportRepository
from pivot.http import RuntimeSettings, assemble_runtime, assemble_runtime_app

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "postgres-export-tasks.md"
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


def _login(client: TestClient, request_id: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": request_id},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _seed_answer(assembly) -> None:
    user = assembly.users.get_by_username("admin")
    assert user is not None
    assembly.resources.conversations["conv_admin"] = user.id
    assembly.answers.answers["conv_admin"] = PersistedAnswer(
        conversation_id="conv_admin",
        run_id="run_admin",
        state="answered",
        answer_markdown="late three times written warning.",
        title="policy",
    )


def test_NFR_OBS_runtime_postgres_wires_export_tasks(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    assembly = assemble_runtime(_settings(url))
    assert isinstance(assembly.export_rows, SqlAlchemyExportRepository)
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
    assert isinstance(memory.export_rows, InMemoryExportRepository)


def test_FR_EXPORT_001_postgres_task_survives_assembly(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    first = assemble_runtime(_settings(url))
    _seed_answer(first)
    client = TestClient(first.app, base_url="https://testserver")
    token = _login(client, "req_pg_export_login_1")
    created = client.post(
        "/api/v1/exports",
        json={
            "source_type": "conversation",
            "source_id": "conv_admin",
            "format": "markdown",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_export",
        },
    )
    assert created.status_code == 202
    export_id = created.json()["export_id"]
    ready = client.get(
        f"/api/v1/exports/{export_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_export_status_1",
        },
    )
    assert ready.status_code == 200
    assert ready.json()["state"] == "ready"

    second = TestClient(assemble_runtime_app(_settings(url)), base_url="https://testserver")
    replayed = _login(second, "req_pg_export_login_2")
    status = second.get(
        f"/api/v1/exports/{export_id}",
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_export_status_2",
        },
    )
    assert status.status_code == 200
    payload = status.json()
    assert payload["export_id"] == export_id
    assert payload["state"] == "ready"
    assert payload["download_url"].startswith("https://files.pivot.test/")
    assert "storage_key" not in payload


def test_FR_EXPORT_001_download_url_does_not_leak_minio(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    assembly = assemble_runtime(_settings(url))
    _seed_answer(assembly)
    client = TestClient(assembly.app, base_url="https://testserver")
    token = _login(client, "req_pg_export_leak_login")
    created = client.post(
        "/api/v1/exports",
        json={
            "source_type": "conversation",
            "source_id": "conv_admin",
            "format": "markdown",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_export_leak",
        },
    )
    assert created.status_code == 202
    export_id = created.json()["export_id"]
    status = client.get(
        f"/api/v1/exports/{export_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_export_leak_status",
        },
    )
    assert status.status_code == 200
    payload = status.json()
    assert payload["state"] == "ready"
    download_url = payload["download_url"]
    assert download_url.startswith("https://files.pivot.test/")
    assert "storage_key" not in payload
    dumped = download_url.lower() + str(status.headers).lower() + str(payload).lower()
    assert "minio" not in dumped
    assert ":9000" not in dumped
    assert "x-amz" not in dumped
    assert "objects.test" not in dumped
    assert "pivotminio" not in dumped


def test_GATE_P0_003_not_verified_by_postgres_export_tasks():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "sqlite" in evidence.lower() or "SQLAlchemy" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
