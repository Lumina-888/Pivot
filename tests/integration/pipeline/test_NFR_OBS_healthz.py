"""Application /healthz and /readyz. Not GATE-P0-008 verified. No /api/v1 routes."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pivot.http import create_app

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "healthz.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"


class RecordingProbes:
    def __init__(self, **results: bool) -> None:
        self.results = {
            "postgres": False,
            "minio": False,
            "qdrant": False,
            "redis": False,
            **results,
        }
        self.called: list[str] = []

    def postgres(self) -> bool:
        self.called.append("postgres")
        return self.results["postgres"]

    def minio(self) -> bool:
        self.called.append("minio")
        return self.results["minio"]

    def qdrant(self) -> bool:
        self.called.append("qdrant")
        return self.results["qdrant"]

    def redis(self) -> bool:
        self.called.append("redis")
        return self.results["redis"]


def test_NFR_OBS_001_healthz_is_alive_without_probing_dependencies():
    probes = RecordingProbes(postgres=False, minio=False, qdrant=False, redis=False)
    client = TestClient(create_app(probes=probes))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert probes.called == []


def test_NFR_OBS_002_readyz_fail_closed_when_probes_missing():
    client = TestClient(create_app())
    response = client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"] == {
        "postgres": False,
        "minio": False,
        "qdrant": False,
        "redis": False,
    }


def test_NFR_OBS_002_readyz_fail_closed_when_a_dependency_is_down():
    probes = RecordingProbes(postgres=True, minio=True, qdrant=False, redis=True)
    client = TestClient(create_app(probes=probes))
    response = client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["qdrant"] is False
    assert body["checks"]["postgres"] is True
    assert set(probes.called) == {"postgres", "minio", "qdrant", "redis"}


def test_NFR_OBS_002_readyz_ok_when_all_injected_probes_pass():
    probes = RecordingProbes(postgres=True, minio=True, qdrant=True, redis=True)
    client = TestClient(create_app(probes=probes))
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"] == {
        "postgres": True,
        "minio": True,
        "qdrant": True,
        "redis": True,
    }


def test_NFR_OBS_health_app_does_not_mount_api_v1_routes():
    app = create_app()
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any(path.startswith("/api/v1") for path in paths)
    response = TestClient(app).get("/api/v1/auth/login")
    assert response.status_code == 404


def test_GATE_P0_008_not_verified_by_healthz_alone():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-008" in evidence
    assert "unverified" in evidence.lower()
    assert "/healthz" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-008" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
