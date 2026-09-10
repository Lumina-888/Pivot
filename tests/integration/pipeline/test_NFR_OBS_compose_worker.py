"""Compose worker fixture. Celery + injected broker; not GATE-P0-008 verified; not started by CI."""

from __future__ import annotations

import os
import re
import socket
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _ROOT / "docker-compose.yml"
_DOCKERFILE = _ROOT / "Dockerfile.worker"
_ENV_EXAMPLE = _ROOT / "ops" / "compose.env.example"
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "compose-worker.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_INTENT = _ROOT / "ops" / "compose-intent.md"
_WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"
_GROUPED = _ROOT / "ops" / "run_grouped_tests.py"

_WORKER_IMAGE = "pivot-worker:0.1.0"
_PYTHON_PIN = "python:3.12.10"
_DEPS = ("postgres", "minio", "qdrant", "redis")
_REQUIRED_ENV = (
    "PIVOT_PARSE_QUEUE",
    "PIVOT_ONLINE_QUEUE",
    "PIVOT_WORKER_CONCURRENCY",
    "PIVOT_CELERY_BROKER",
)


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


def test_NFR_OBS_worker_dockerfile_pins_python_and_module_entrypoint():
    assert _DOCKERFILE.is_file(), "Wave 3 must add Dockerfile.worker for the worker fixture"
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert _PYTHON_PIN in text
    assert "slim-bookworm" in text
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.upper().startswith("FROM "):
            assert ":latest" not in stripped
    assert "python -m pivot_worker" in text or '"pivot_worker"' in text
    assert "0.0.0.0" in text
    assert "8001" in text
    assert ".env" not in text
    assert "PIVOT_TOKEN_SECRET" not in text
    assert "siliconflow" not in text.lower()
    assert "redis://" not in text.lower()


def test_NFR_OBS_worker_dockerfile_installs_celery_extra():
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert "worker[celery]" in text
    assert "./worker[celery]" in text or '\"worker[celery]\"' in text


def test_NFR_OBS_compose_worker_service_is_profiled_with_healthcheck():
    text = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(text)
    assert "worker" in services, "Compose must declare a worker service"
    body = services["worker"]
    assert "profiles:" in body
    assert "app" in body
    assert _WORKER_IMAGE in body
    assert "127.0.0.1:8001" in body
    assert "healthcheck:" in body
    assert "/healthz" in body
    assert "depends_on:" in body
    for name in _DEPS:
        assert name in body
    assert "service_healthy" in body
    assert "limits:" in body
    assert "reservations:" in body
    assert "memory:" in body
    assert "cpus:" in body
    assert "4C8G" not in text
    assert "4c8g" not in text.lower()


def test_NFR_OBS_compose_worker_isolates_parse_and_online_queues():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    body = services["worker"]
    assert "PIVOT_PARSE_QUEUE:" in body
    assert "PIVOT_ONLINE_QUEUE:" in body
    assert "${PIVOT_PARSE_QUEUE" in body
    assert "${PIVOT_ONLINE_QUEUE" in body
    assert re.search(r"PIVOT_PARSE_QUEUE:\s*[A-Za-z0-9_-]+\s*$", body, re.M) is None
    assert re.search(r"PIVOT_ONLINE_QUEUE:\s*[A-Za-z0-9_-]+\s*$", body, re.M) is None
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "PIVOT_PARSE_QUEUE=" in example
    assert "PIVOT_ONLINE_QUEUE=" in example
    parse_value = next(
        line.split("=", 1)[1].strip()
        for line in example.splitlines()
        if line.startswith("PIVOT_PARSE_QUEUE=")
    )
    online_value = next(
        line.split("=", 1)[1].strip()
        for line in example.splitlines()
        if line.startswith("PIVOT_ONLINE_QUEUE=")
    )
    assert parse_value
    assert online_value
    assert parse_value != online_value
    intent = _INTENT.read_text(encoding="utf-8")
    assert "worker" in intent.lower()
    assert "隔离" in intent or "isolate" in intent.lower()


def test_NFR_OBS_compose_worker_injects_concurrency_without_freezing_tbd():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    body = services["worker"]
    for key in _REQUIRED_ENV:
        assert f"{key}:" in body
        assert "${" + key in body
    assert re.search(r"PIVOT_WORKER_CONCURRENCY:\s*\d+", body) is None
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "TBD-P0" in example
    assert "PIVOT_WORKER_CONCURRENCY=" in example
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "TBD-P0" in evidence or "unverified" in evidence.lower()


def test_NFR_OBS_compose_worker_injects_celery_broker_without_hardcoding():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    body = services["worker"]
    assert "PIVOT_CELERY_BROKER:" in body
    assert "${PIVOT_CELERY_BROKER" in body
    assert re.search(r"PIVOT_CELERY_BROKER:\s*redis://", body) is None
    assert "redis://" not in body.lower()
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "PIVOT_CELERY_BROKER=" in example
    broker = next(
        line.split("=", 1)[1].strip()
        for line in example.splitlines()
        if line.startswith("PIVOT_CELERY_BROKER=")
    )
    assert broker
    assert "TBD-P0" in example


def test_NFR_OBS_compose_worker_injects_qdrant():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    body = services["worker"]
    for key in (
        "PIVOT_VECTOR_STORE",
        "PIVOT_QDRANT_ENDPOINT",
        "PIVOT_QDRANT_COLLECTION",
        "PIVOT_QDRANT_VECTOR_SIZE",
        "PIVOT_QDRANT_DISTANCE",
        "PIVOT_QDRANT_ENSURE_COLLECTION",
    ):
        assert f"{key}:" in body
        assert "${" + key in body
    assert re.search(r"PIVOT_QDRANT_ENDPOINT:\s*https?://", body, re.I) is None
    assert "qdrant:6333" not in body.lower()
    assert re.search(r"PIVOT_QDRANT_VECTOR_SIZE:\s*\d+", body) is None
    assert re.search(r"PIVOT_QDRANT_DISTANCE:\s*Cosine", body) is None
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "PIVOT_VECTOR_STORE=" in example
    assert "PIVOT_QDRANT_ENDPOINT=" in example
    assert "PIVOT_QDRANT_COLLECTION=" in example
    assert "TBD-P0" in example


def test_NFR_OBS_compose_worker_injects_shared_storage_and_minio():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    body = services["worker"]
    for key in (
        "PIVOT_STORAGE",
        "PIVOT_DATABASE_URL",
        "PIVOT_OBJECT_STORE",
        "PIVOT_MINIO_ENDPOINT",
        "PIVOT_MINIO_BUCKET",
        "PIVOT_MINIO_ACCESS_KEY",
        "PIVOT_MINIO_SECRET_KEY",
    ):
        assert f"{key}:" in body
        assert "${" + key in body
    assert re.search(r"PIVOT_DATABASE_URL:\s*postgres", body, re.I) is None
    assert "postgresql://" not in body.lower()
    assert "minio:9000" not in body.lower()
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "PIVOT_DATABASE_URL=" in example
    assert "PIVOT_OBJECT_STORE=" in example
    assert "PIVOT_MINIO_ENDPOINT=" in example
    assert "TBD-P0" in example


def test_NFR_OBS_ci_does_not_build_or_start_compose_worker():
    workflow = _WORKFLOW.read_text(encoding="utf-8").lower()
    assert "docker compose" not in workflow
    assert "docker-compose" not in workflow
    assert "docker build" not in workflow
    grouped = _GROUPED.read_text(encoding="utf-8").lower()
    assert "docker compose up" not in grouped
    assert "docker build" not in grouped
    intent = _INTENT.read_text(encoding="utf-8")
    assert "CI" in intent
    assert "profile" in intent.lower() or "app" in intent
    assert "不得" in intent or "不启动" in intent or "不调用" in intent


def test_NFR_OBS_compose_worker_healthz_when_running():
    require = os.environ.get("PIVOT_REQUIRE_COMPOSE_WORKER") == "1"
    if not _reachable(8001):
        if require:
            pytest.fail("compose worker is not reachable on 127.0.0.1:8001")
        pytest.skip("compose worker not running on 127.0.0.1:8001")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8001/healthz", timeout=1) as response:
            body = response.read()
            status = response.status
    except (urllib.error.URLError, TimeoutError) as exc:
        if require:
            pytest.fail(f"compose worker /healthz failed: {exc}")
        pytest.skip(f"compose worker /healthz not ready: {exc}")
    assert status == 200
    assert b"ok" in body


def test_GATE_P0_008_not_verified_by_compose_worker():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-008" in evidence
    assert "unverified" in evidence.lower()
    assert "Dockerfile.worker" in evidence or "dockerfile.worker" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-008" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
