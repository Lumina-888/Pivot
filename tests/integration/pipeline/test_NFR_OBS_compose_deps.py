"""Wave 3 dependency Compose fixture. Not GATE-P0 verified and not started by CI."""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _ROOT / "docker-compose.yml"
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "compose-deps.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"

_REQUIRED_SERVICES = ("postgres", "minio", "qdrant", "redis")
_PINNED_IMAGES = {
    "postgres": "postgres:16.4",
    "minio": "docker.io/pgsty/silo:RELEASE.2026-09-16T00-00-00Z",
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


def test_D8_02_compose_passes_bm25_parameters_to_api_and_worker():
    """D8-02: the example env file sets PIVOT_BM25_K1/B, but api/worker
    never received them, so the app profile failed at startup with a
    RuntimeError when PIVOT_RETRIEVAL_BACKEND=llama."""
    text = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(text)
    for name in ("api", "worker"):
        assert name in services, f"missing compose service {name}"
        body = services[name]
        assert "PIVOT_BM25_K1" in body, f"{name} must receive PIVOT_BM25_K1"
        assert "PIVOT_BM25_B" in body, f"{name} must receive PIVOT_BM25_B"


def test_D8_03_qdrant_healthcheck_uses_no_wget_or_curl():
    """D8-03: qdrant/qdrant:v1.12.4 ships neither wget nor curl, so the
    old wget probe could never pass and api/worker (depends_on healthy)
    could never start. The probe must speak HTTP over bash /dev/tcp
    (dash, used by CMD-SHELL, cannot) and require a 200 status line
    from GET /readyz, not just a TCP connect."""
    text = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(text)
    body = services["qdrant"]
    assert "healthcheck:" in body
    # Only the probe command itself is asserted: the explanatory comment
    # above it legitimately names the tools the image lacks.
    probe_lines = [
        line for line in body.splitlines()
        if "bash" in line or "/dev/tcp" in line or "readyz" in line
    ]
    probe = "\n".join(probe_lines)
    assert "wget" not in probe, "qdrant image has no wget"
    assert "curl" not in probe, "qdrant image has no curl"
    assert "bash" in probe
    assert "/dev/tcp" in probe
    assert "/readyz" in probe
    assert "200" in probe


def test_D8_03_qdrant_probe_survives_compose_interpolation():
    """D8-03 follow-up: Compose interpolates $VAR at parse time, so the
    original `case "$line"` was rendered as `case "" in *200*)` -- a probe
    that can never match and left qdrant permanently unhealthy even after
    wget was replaced. The shell variable must be escaped as $$line so the
    container receives a literal $line."""
    text = _COMPOSE.read_text(encoding="utf-8")
    body = _service_blocks(text)["qdrant"]
    assert "$$line" in body, "the probe must escape $line as $$line"
    # Only the probe command is scanned: the comment above it legitimately
    # names $line/$$line when explaining why the escape is required.
    command = "\n".join(
        line for line in body.splitlines()
        if "/dev/tcp" in line or "readyz" in line
    )
    assert command, "qdrant probe command not found"
    # A bare $line (however quoted, including inside a YAML \"...\" scalar)
    # is swallowed by Compose interpolation and renders as the empty string.
    bare = re.search(r"(?<!\$)\$line\b", command)
    assert bare is None, (
        "a bare $line is swallowed by Compose interpolation and renders empty"
    )
    # Every $-reference in the probe command must be escaped; only env-file
    # placeholders (${VAR}) may stay unescaped elsewhere in the file.
    assert "$$" in command


def test_D8_03_Q5_qdrant_probe_budget_is_100s():
    """Q5 (2026-11-04 retest v1.2): qdrant needs ~25 s to turn healthy
    on a host with a large recovered history set, against a 5s x 10 =
    50 s budget. retries=20 gives ~100 s so a slow recovery does not
    flap api/worker through depends_on: service_healthy."""
    text = _COMPOSE.read_text(encoding="utf-8")
    body = _service_blocks(text)["qdrant"]
    assert "interval: 5s" in body
    assert "retries: 20" in body
    # The budget change must not regress the $$line escape (D8-03).
    assert "$$line" in body
