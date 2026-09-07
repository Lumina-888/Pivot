"""Wave 3 dependency Compose fixture. Not GATE-P0 verified and not started by CI."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _ROOT / "docker-compose.yml"
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "compose-deps.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"

_REQUIRED_SERVICES = ("postgres", "minio", "qdrant", "redis")
_FORBIDDEN_SERVICES = ("api", "worker", "web")
_PINNED_IMAGES = {
    "postgres": "postgres:16.4",
    "minio": "minio/minio:RELEASE.2024-10-02T17-50-41Z",
    "qdrant": "qdrant/qdrant:v1.12.4",
    "redis": "redis:7.4.1",
}
_HEALTH_MARKERS = {
    "postgres": "pg_isready",
    "minio": "minio/health/live",
    "qdrant": "readyz",
    "redis": "redis-cli",
}
_PROBE_PORTS = {
    "postgres": 5432,
    "minio": 9000,
    "qdrant": 6333,
    "redis": 6379,
}


def _service_blocks(text: str) -> dict[str, str]:
    blocks: dict[str, list[str]] = {}
    in_services = False
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("services:"):
            in_services = True
            continue
        if not in_services:
            continue
        if (
            line
            and not line[:1].isspace()
            and line.rstrip().endswith(":")
            and not line.startswith("#")
        ):
            break
        stripped = line.strip()
        if (
            line.startswith("  ")
            and not line.startswith("    ")
            and stripped.endswith(":")
            and not stripped.startswith("#")
        ):
            current = stripped[:-1]
            blocks[current] = []
            continue
        if current is not None:
            blocks[current].append(line)
    return {name: "\n".join(body) for name, body in blocks.items()}


def _reachable(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def test_NFR_OBS_compose_file_pins_dependency_images_and_healthchecks():
    assert _COMPOSE.is_file(), "Wave 3 must add docker-compose.yml for dependency fixtures"
    text = _COMPOSE.read_text(encoding="utf-8")
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("image:"):
            assert ":latest" not in stripped
            assert not stripped.endswith(":latest")
    services = _service_blocks(text)
    for name in _REQUIRED_SERVICES:
        assert name in services, f"missing compose service {name}"
        body = services[name]
        assert "healthcheck:" in body, f"{name} must declare healthcheck"
        assert _HEALTH_MARKERS[name] in body, f"{name} healthcheck must use {_HEALTH_MARKERS[name]}"
        assert _PINNED_IMAGES[name] in body, f"{name} must pin {_PINNED_IMAGES[name]}"
        assert "127.0.0.1:" in body, f"{name} must bind published ports to localhost"
    for name in _FORBIDDEN_SERVICES:
        assert name not in services, (
            f"{name} compose service needs FastAPI/Celery/Next image; not this slice"
        )


def test_NFR_OBS_ci_does_not_start_compose():
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "docker compose" not in workflow.lower()
    assert "docker-compose" not in workflow.lower()
    script = (_ROOT / "ops" / "run_grouped_tests.py").read_text(encoding="utf-8")
    assert "docker compose up" not in script.lower()
    intent = (_ROOT / "ops" / "compose-intent.md").read_text(encoding="utf-8")
    assert "CI" in intent
    assert "不得" in intent or "不启动" in intent or "不调用" in intent


def test_NFR_OBS_dependency_health_fail_closed_when_compose_down():
    require = os.environ.get("PIVOT_REQUIRE_COMPOSE") == "1"
    unreachable = [name for name, port in _PROBE_PORTS.items() if not _reachable(port)]
    if unreachable and require:
        pytest.fail("compose dependency health required but unreachable: " + ", ".join(unreachable))
    if unreachable:
        pytest.skip("compose deps not running: " + ", ".join(unreachable))
    assert unreachable == []


def test_GATE_P0_008_not_verified_by_compose_file_alone():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-008" in evidence
    assert "unverified" in evidence.lower()
    assert "/healthz" in evidence
    assert "无" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-008" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
