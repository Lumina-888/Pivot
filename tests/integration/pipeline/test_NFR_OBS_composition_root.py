"""Runtime composition root. Not GATE-P0 verified. Default create_app() stays bare."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pivot.http import (
    RuntimeSettings,
    assemble_runtime,
    assemble_runtime_app,
    create_app,
)

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "composition-root.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"


def _settings(**overrides: object) -> RuntimeSettings:
    values: dict[str, object] = {
        "storage": "memory",
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


def _client(settings: RuntimeSettings | None = None) -> TestClient:
    return TestClient(
        assemble_runtime_app(_settings() if settings is None else settings),
        base_url="https://testserver",
    )


def test_NFR_OBS_001_runtime_app_is_alive_without_injected_services():
    client = _client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "nope"},
        headers={"X-Request-ID": "req_runtime_missing"},
    )
    documents = client.get(
        "/api/v1/documents", headers={"X-Request-ID": "req_runtime_docs_anon"}
    )
    search = client.get(
        "/api/v1/search",
        params={"q": "policy"},
        headers={"X-Request-ID": "req_runtime_search_anon"},
    )
    conversations = client.get(
        "/api/v1/conversations", headers={"X-Request-ID": "req_runtime_conv_anon"}
    )
    assert login.status_code == 401
    assert documents.status_code == 401
    assert search.status_code == 401
    assert conversations.status_code == 401


def test_NFR_OBS_002_runtime_readyz_fail_closed_without_infra_probes():
    response = _client().get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"] == {
        "postgres": False,
        "minio": False,
        "qdrant": False,
        "redis": False,
    }


def test_NFR_SEC_004_runtime_bootstrap_password_is_argon2id():
    assembly = assemble_runtime(_settings())
    user = assembly.users.get_by_username("admin")
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert "runtime-admin-password" not in user.password_hash
    assert assembly.hasher.verify("runtime-admin-password", user.password_hash)
    assert not assembly.hasher.verify("wrong-password", user.password_hash)


def test_FR_AUTH_001_runtime_login_without_test_harness():
    client = _client()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_runtime_login"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["refresh_token_cookie"] is True
    assert "refresh_token" not in body
    assert body["access_token"]
    assert "runtime-admin-password" not in body["access_token"]
    token = body["access_token"]
    listed = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_runtime_docs"},
    )
    assert listed.status_code == 200
    assert listed.json()["items"] == []


def test_NFR_OBS_runtime_rejects_unwired_storage():
    with pytest.raises(RuntimeError, match="memory"):
        assemble_runtime_app(_settings(storage="postgres"))


def test_NFR_OBS_runtime_settings_fail_closed_without_token_secret():
    with pytest.raises(RuntimeError, match="PIVOT_TOKEN_SECRET"):
        RuntimeSettings.from_env(
            {
                "PIVOT_STORAGE": "memory",
                "PIVOT_ACCESS_TTL": "60",
                "PIVOT_REFRESH_TTL": "3600",
                "PIVOT_EXPORT_TTL": "3600",
                "PIVOT_DOWNLOAD_TTL": "300",
                "PIVOT_EXPORT_PUBLIC_BASE": "https://files.pivot.test",
                "PIVOT_RETRIEVAL_K": "4",
            }
        )


def test_NFR_OBS_runtime_factory_reads_settings_from_env(monkeypatch):
    from pivot.http.main import app as runtime_factory

    monkeypatch.setenv("PIVOT_TOKEN_SECRET", "runtime-factory-secret")
    monkeypatch.setenv("PIVOT_ACCESS_TTL", "60")
    monkeypatch.setenv("PIVOT_REFRESH_TTL", "3600")
    monkeypatch.setenv("PIVOT_EXPORT_TTL", "3600")
    monkeypatch.setenv("PIVOT_DOWNLOAD_TTL", "300")
    monkeypatch.setenv("PIVOT_EXPORT_PUBLIC_BASE", "https://files.pivot.test")
    monkeypatch.setenv("PIVOT_RETRIEVAL_K", "4")
    monkeypatch.setenv("PIVOT_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("PIVOT_BOOTSTRAP_PASSWORD", "runtime-admin-password")
    client = TestClient(runtime_factory(), base_url="https://testserver")
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_NFR_OBS_default_create_app_does_not_mount_api_v1():
    app = create_app()
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any(path.startswith("/api/v1") for path in paths)


def test_GATE_P0_008_not_verified_by_runtime_assembly():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-008" in evidence
    assert "unverified" in evidence.lower()
    assert "composition root" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-008" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
