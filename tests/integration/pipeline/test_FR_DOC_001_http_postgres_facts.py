"""Postgres document facts survive a new runtime assembly. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from harness import policy_pdf
from pivot.db.documents import SqlAlchemyDocumentStore
from pivot.http import RuntimeSettings, assemble_runtime, assemble_runtime_app
from pivot.http.memory import MemoryDocuments

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "postgres-document-facts.md"
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


def test_NFR_OBS_runtime_postgres_wires_document_facts(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    assembly = assemble_runtime(_settings(url))
    assert isinstance(assembly.document_rows, SqlAlchemyDocumentStore)
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
    assert isinstance(memory.document_rows, MemoryDocuments)


def test_FR_DOC_001_runtime_postgres_upload_survives_new_assembly(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    first = _client(url)
    token = _login(first, "req_pg_doc_login_1")
    uploaded = first.post(
        "/api/v1/documents",
        data={"title": "Attendance Policy"},
        files={"file": ("handbook.pdf", policy_pdf(), "application/pdf")},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_pg_upload",
        },
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()["document_id"]
    second = _client(url)
    replayed = _login(second, "req_pg_doc_login_2")
    listed = second.get(
        "/api/v1/documents",
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_list",
        },
    )
    assert listed.status_code == 200
    titles = [item["title"] for item in listed.json()["items"]]
    assert "Attendance Policy" in titles
    detail = second.get(
        f"/api/v1/documents/{document_id}",
        headers={
            "Authorization": f"Bearer {replayed}",
            "X-Request-ID": "req_pg_detail",
        },
    )
    assert detail.status_code == 200
    assert detail.json()["title"] == "Attendance Policy"
    assert detail.json()["document_id"] == document_id


def test_GATE_P0_003_not_verified_by_postgres_document_facts():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "sqlite" in evidence.lower() or "SQLAlchemy" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
