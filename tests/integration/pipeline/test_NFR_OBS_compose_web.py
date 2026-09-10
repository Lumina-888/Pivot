"""Compose web fixture. Not GATE-P0-008 verified and not started by CI."""

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
_DOCKERFILE = _ROOT / "Dockerfile.web"
_ENV_EXAMPLE = _ROOT / "ops" / "compose.env.example"
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "compose-web.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_INTENT = _ROOT / "ops" / "compose-intent.md"
_WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"
_GROUPED = _ROOT / "ops" / "run_grouped_tests.py"

_WEB_IMAGE = "pivot-web:0.1.0"
_NODE_PIN = "node:20.19.0"


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


def test_NFR_OBS_web_dockerfile_pins_node_and_next_start():
    assert _DOCKERFILE.is_file(), "Wave 3 must add Dockerfile.web for the web fixture"
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert _NODE_PIN in text
    assert "bookworm-slim" in text
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.upper().startswith("FROM "):
            assert ":latest" not in stripped
    assert "next" in text
    assert "start" in text
    assert "0.0.0.0" in text
    assert "3000" in text
    assert ".env" not in text
    assert "PIVOT_TOKEN_SECRET" not in text
    assert "siliconflow" not in text.lower()
    assert "NEXT_PUBLIC_" not in text


def test_NFR_OBS_compose_web_service_is_profiled_with_healthcheck():
    text = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(text)
    assert "web" in services, "Compose must declare a web service"
    body = services["web"]
    assert "profiles:" in body
    assert "app" in body
    assert _WEB_IMAGE in body
    assert "127.0.0.1:3000" in body
    assert "healthcheck:" in body
    assert "/login" in body
    assert "depends_on:" in body
    assert "api:" in body
    assert "service_healthy" in body
    assert "limits:" in body
    assert "reservations:" in body
    assert "memory:" in body
    assert "cpus:" in body
    assert "4C8G" not in text
    assert "4c8g" not in text.lower()
    assert "worker" not in services


def test_NFR_OBS_compose_web_injects_api_origin_without_production_url():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    body = services["web"]
    assert "PIVOT_API_ORIGIN:" in body
    assert "${PIVOT_API_ORIGIN" in body
    assert re.search(r"PIVOT_API_ORIGIN:\s*https?://", body) is None
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "PIVOT_API_ORIGIN=" in example
    assert "TBD-P0" in example
    assert "siliconflow" not in example.lower()
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "TBD-P0" in evidence or "unverified" in evidence.lower()
    dockerfile = _DOCKERFILE.read_text(encoding="utf-8")
    assert "siliconflow" not in dockerfile.lower()
    assert "NEXT_PUBLIC_" not in dockerfile


def test_NFR_OBS_ci_does_not_build_or_start_compose_web():
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


def test_NFR_OBS_compose_web_login_when_running():
    require = os.environ.get("PIVOT_REQUIRE_COMPOSE_WEB") == "1"
    if not _reachable(3000):
        if require:
            pytest.fail("compose web is not reachable on 127.0.0.1:3000")
        pytest.skip("compose web not running on 127.0.0.1:3000")
    try:
        with urllib.request.urlopen("http://127.0.0.1:3000/login", timeout=1) as response:
            status = response.status
    except (urllib.error.URLError, TimeoutError) as exc:
        if require:
            pytest.fail(f"compose web /login failed: {exc}")
        pytest.skip(f"compose web /login not ready: {exc}")
    assert status == 200


def test_GATE_P0_008_not_verified_by_compose_web():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-008" in evidence
    assert "unverified" in evidence.lower()
    assert "Dockerfile.web" in evidence or "dockerfile.web" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-008" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
