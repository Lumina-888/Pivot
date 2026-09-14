"""Compose api fixture. Not GATE-P0-008 verified and not started by CI."""

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
_DOCKERFILE = _ROOT / "Dockerfile"
_ENV_EXAMPLE = _ROOT / "ops" / "compose.env.example"
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "compose-api.md"
_CELERY_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "compose-api-celery.md"
_QDRANT_REDIS_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "compose-qdrant-redis.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_INTENT = _ROOT / "ops" / "compose-intent.md"
_WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"
_GROUPED = _ROOT / "ops" / "run_grouped_tests.py"

_API_IMAGE = "pivot-api:0.1.0"
_PYTHON_PIN = "python:3.12.10"
_REQUIRED_ENV = (
    "PIVOT_TOKEN_SECRET",
    "PIVOT_ACCESS_TTL",
    "PIVOT_REFRESH_TTL",
    "PIVOT_EXPORT_TTL",
    "PIVOT_DOWNLOAD_TTL",
    "PIVOT_EXPORT_PUBLIC_BASE",
    "PIVOT_RETRIEVAL_K",
)
_DEPS = ("postgres", "minio", "qdrant", "redis")


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


def test_NFR_OBS_api_dockerfile_pins_python_and_uvicorn_factory():
    assert _DOCKERFILE.is_file(), "Wave 3 must add a root Dockerfile for the api fixture"
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert _PYTHON_PIN in text
    assert "slim-bookworm" in text
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.upper().startswith("FROM "):
            assert ":latest" not in stripped
    assert "uvicorn" in text
    assert "pivot.http.main:app" in text
    assert "--factory" in text
    assert "0.0.0.0" in text
    assert "8000" in text
    assert ".env" not in text
    assert "PIVOT_TOKEN_SECRET" not in text
    assert "redis://" not in text.lower()
    assert "PIVOT_INGEST" not in text


def test_NFR_OBS_api_dockerfile_installs_celery_extra():
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY worker" in text or "COPY worker/" in text
    assert "worker[celery]" in text
    assert "./worker[celery]" in text or '"worker[celery]"' in text
    assert "uvicorn" in text
    assert "pivot.http.main:app" in text
    assert "--factory" in text
    assert "celery worker" not in text.lower()


def test_NFR_OBS_compose_api_service_is_profiled_with_healthcheck():
    text = _COMPOSE.read_text(encoding="utf-8")
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("image:"):
            assert ":latest" not in stripped
    services = _service_blocks(text)
    assert "api" in services, "Compose must declare an api service"
    body = services["api"]
    assert "profiles:" in body
    assert "app" in body
    assert _API_IMAGE in body
    assert "127.0.0.1:8000" in body
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


def test_NFR_OBS_compose_api_env_injects_ttl_without_freezing_tbd():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    body = services["api"]
    for key in _REQUIRED_ENV:
        assert f"{key}:" in body
        assert "${" + key in body
        assert re.search(rf"{key}:\s*\d+", body) is None
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "TBD-P0" in example
    for key in _REQUIRED_ENV:
        assert key in example
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "TBD-P0" in evidence


_SHARED_STORE_ENV = (
    "PIVOT_STORAGE",
    "PIVOT_DATABASE_URL",
    "PIVOT_OBJECT_STORE",
    "PIVOT_MINIO_ENDPOINT",
    "PIVOT_MINIO_BUCKET",
    "PIVOT_MINIO_ACCESS_KEY",
    "PIVOT_MINIO_SECRET_KEY",
)


def test_NFR_OBS_compose_api_injects_shared_storage_and_minio():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    api = services["api"]
    worker = services["worker"]
    for key in _SHARED_STORE_ENV:
        assert f"{key}:" in api
        assert "${" + key in api
        assert f"{key}:" in worker
        assert "${" + key in worker
    assert re.search(r"PIVOT_DATABASE_URL:\s*postgres", api, re.I) is None
    assert "postgresql://" not in api.lower()
    assert "minio:9000" not in api.lower()
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "PIVOT_DATABASE_URL=" in example
    assert "PIVOT_MINIO_ENDPOINT=" in example
    storage = next(
        line.split("=", 1)[1].strip()
        for line in example.splitlines()
        if line.startswith("PIVOT_STORAGE=")
    )
    objects = next(
        line.split("=", 1)[1].strip()
        for line in example.splitlines()
        if line.startswith("PIVOT_OBJECT_STORE=")
    )
    assert storage == "postgres"
    assert objects == "minio"
    assert "TBD-P0" in example


def test_NFR_OBS_compose_api_does_not_default_storage_to_memory():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    api = services["api"]
    assert "${PIVOT_STORAGE:-memory}" not in api
    assert "${PIVOT_OBJECT_STORE:-memory}" not in api
    assert "${PIVOT_STORAGE:?" in api
    assert "${PIVOT_OBJECT_STORE:?" in api


_CELERY_INGEST_ENV = (
    "PIVOT_INGEST",
    "PIVOT_PARSE_QUEUE",
    "PIVOT_ONLINE_QUEUE",
    "PIVOT_WORKER_CONCURRENCY",
    "PIVOT_CELERY_BROKER",
)


def test_NFR_OBS_compose_api_injects_celery_ingest_without_hardcoding():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    api = services["api"]
    worker = services["worker"]
    for key in _CELERY_INGEST_ENV:
        assert f"{key}:" in api
        assert "${" + key in api
    for key in (
        "PIVOT_PARSE_QUEUE",
        "PIVOT_ONLINE_QUEUE",
        "PIVOT_WORKER_CONCURRENCY",
        "PIVOT_CELERY_BROKER",
    ):
        assert f"{key}:" in worker
        assert "${" + key in worker
    assert re.search(r"PIVOT_CELERY_BROKER:\s*redis://", api) is None
    assert "redis://" not in api.lower()
    assert re.search(r"PIVOT_INGEST:\s*celery\s*$", api, re.M) is None
    assert re.search(r"PIVOT_WORKER_CONCURRENCY:\s*\d+", api) is None
    assert "PIVOT_CELERY_EAGER" not in api
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    ingest = next(
        line.split("=", 1)[1].strip()
        for line in example.splitlines()
        if line.startswith("PIVOT_INGEST=")
    )
    assert ingest == "celery"
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
    assert "PIVOT_CELERY_BROKER=" in example
    assert "TBD-P0" in example
    eager_lines = [
        line
        for line in example.splitlines()
        if line.startswith("PIVOT_CELERY_EAGER=")
    ]
    assert eager_lines == []


def test_NFR_OBS_compose_api_does_not_default_ingest_to_sync():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    api = services["api"]
    assert "${PIVOT_INGEST:-sync}" not in api
    assert "${PIVOT_INGEST:-celery}" not in api
    assert "${PIVOT_INGEST:?" in api
    assert "${PIVOT_CELERY_BROKER:?" in api


_QDRANT_REDIS_ENV = (
    "PIVOT_VECTOR_STORE",
    "PIVOT_QDRANT_ENDPOINT",
    "PIVOT_QDRANT_COLLECTION",
    "PIVOT_QDRANT_VECTOR_SIZE",
    "PIVOT_QDRANT_DISTANCE",
    "PIVOT_QDRANT_ENSURE_COLLECTION",
    "PIVOT_CACHE_STORE",
    "PIVOT_QUEUE_STORE",
    "PIVOT_REDIS_ENDPOINT",
)


def _example_assignment(example: str, key: str) -> str:
    return next(
        line.split("=", 1)[1].strip()
        for line in example.splitlines()
        if line.startswith(f"{key}=")
    )


def test_NFR_OBS_compose_api_injects_qdrant_redis_without_hardcoding():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    api = services["api"]
    worker = services["worker"]
    for key in _QDRANT_REDIS_ENV:
        assert f"{key}:" in api
        assert "${" + key in api
        assert f"{key}:" in worker
        assert "${" + key in worker
    for body in (api, worker):
        assert re.search(r"PIVOT_QDRANT_ENDPOINT:\s*https?://", body, re.I) is None
        assert "qdrant:6333" not in body.lower()
        assert re.search(r"PIVOT_QDRANT_VECTOR_SIZE:\s*\d+", body) is None
        assert re.search(r"PIVOT_QDRANT_DISTANCE:\s*Cosine", body) is None
        assert re.search(r"PIVOT_REDIS_ENDPOINT:\s*redis://", body) is None
        assert "redis:6379" not in body.lower()
        assert "redis://" not in body.lower()
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert _example_assignment(example, "PIVOT_VECTOR_STORE") == "qdrant"
    assert _example_assignment(example, "PIVOT_CACHE_STORE") == "redis"
    assert _example_assignment(example, "PIVOT_QUEUE_STORE") == "redis"
    assert _example_assignment(example, "PIVOT_QDRANT_ENDPOINT")
    assert _example_assignment(example, "PIVOT_QDRANT_COLLECTION")
    assert _example_assignment(example, "PIVOT_REDIS_ENDPOINT")
    assert "TBD-P0" in example
    intent = _INTENT.read_text(encoding="utf-8")
    assert "qdrant" in intent.lower()
    assert "redis" in intent.lower()


def test_NFR_OBS_compose_api_does_not_default_vector_cache_to_memory():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    for name in ("api", "worker"):
        body = services[name]
        assert "${PIVOT_VECTOR_STORE:-memory}" not in body
        assert "${PIVOT_CACHE_STORE:-memory}" not in body
        assert "${PIVOT_QUEUE_STORE:-memory}" not in body
        assert "${PIVOT_VECTOR_STORE:?" in body
        assert "${PIVOT_CACHE_STORE:?" in body
        assert "${PIVOT_QUEUE_STORE:?" in body


def test_NFR_OBS_compose_redis_is_not_business_fact_store():
    compose = _COMPOSE.read_text(encoding="utf-8")
    intent = _INTENT.read_text(encoding="utf-8")
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    evidence = _QDRANT_REDIS_EVIDENCE.read_text(encoding="utf-8")
    for text in (compose, intent, example, evidence):
        assert "不是" in text and "业务事实" in text
    assert "PIVOT_STORAGE" in compose
    assert "postgres" in example


def test_GATE_P0_003_not_verified_by_compose_qdrant_redis():
    evidence = _QDRANT_REDIS_EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "qdrant" in evidence.lower()
    assert "redis" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")


_EMBEDDING_ENV = (
    "PIVOT_EMBEDDING",
    "PIVOT_EMBEDDING_ENDPOINT",
    "PIVOT_EMBEDDING_MODEL",
    "PIVOT_EMBEDDING_API_KEY",
    "PIVOT_EMBEDDING_TIMEOUT",
)


def test_NFR_OBS_compose_api_worker_injects_http_embedding():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    api = services["api"]
    worker = services["worker"]
    for key in _EMBEDDING_ENV:
        assert f"{key}:" in api
        assert "${" + key in api
        assert f"{key}:" in worker
        assert "${" + key in worker
    for body in (api, worker):
        assert "${PIVOT_EMBEDDING:?" in body
        assert "${PIVOT_EMBEDDING:-hash}" not in body
        assert re.search(r"PIVOT_EMBEDDING:\s*http", body) is None
        assert re.search(r"PIVOT_EMBEDDING_ENDPOINT:\s*https?://", body, re.I) is None
        assert "siliconflow" not in body.lower()
        assert "bge-m3" not in body.lower()
        assert "openai.com" not in body.lower()
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert _example_assignment(example, "PIVOT_EMBEDDING") == "hash"
    assert "PIVOT_EMBEDDING_ENDPOINT=" in example
    assert "TBD-P0" in example
    intent = _INTENT.read_text(encoding="utf-8")
    assert "embedding" in intent.lower()


def test_NFR_OBS_ci_does_not_build_or_start_compose_api():
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


def test_NFR_OBS_compose_api_healthz_when_running():
    require = os.environ.get("PIVOT_REQUIRE_COMPOSE_API") == "1"
    if not _reachable(8000):
        if require:
            pytest.fail("compose api is not reachable on 127.0.0.1:8000")
        pytest.skip("compose api not running on 127.0.0.1:8000")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/healthz", timeout=1) as response:
            body = response.read()
            status = response.status
    except (urllib.error.URLError, TimeoutError) as exc:
        if require:
            pytest.fail(f"compose api /healthz failed: {exc}")
        pytest.skip(f"compose api /healthz not ready: {exc}")
    assert status == 200
    assert b"ok" in body


def test_GATE_P0_008_not_verified_by_compose_api():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-008" in evidence
    assert "unverified" in evidence.lower()
    assert "Dockerfile" in evidence or "dockerfile" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-008" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")


def test_GATE_P0_003_not_verified_by_compose_api_celery():
    evidence = _CELERY_EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "PIVOT_INGEST" in evidence
    assert "eager" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
