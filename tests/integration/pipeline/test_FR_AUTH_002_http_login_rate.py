"""Runtime login rate limit uses Redis CacheStore. Not GATE-P0 verified."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pivot.auth.attempts import CacheLoginAttempts
from pivot.http import RuntimeSettings, assemble_runtime, assemble_runtime_app
from pivot.http.memory import InMemoryAttempts
from pivot.storage.adapters.redis import RedisCacheStore

_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _ROOT / "docker-compose.yml"
_ENV_EXAMPLE = _ROOT / "ops" / "compose.env.example"
_INTENT = _ROOT / "ops" / "compose-intent.md"
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "login-rate-limit.md"
_COMPOSE_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "compose-login-rate.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_LOGIN_LIMIT_ENV = ("PIVOT_LOGIN_MAX_FAILURES", "PIVOT_LOGIN_WINDOW_SECONDS")


class _FakeRedisClient:
    def __init__(self) -> None:
        self.kv: dict[str, bytes] = {}

    def ping(self) -> bool:
        return True

    def get(self, name: str):
        return self.kv.get(name)

    def set(self, name: str, value, ex=None):
        payload = value if isinstance(value, (bytes, bytearray)) else str(value).encode()
        self.kv[name] = bytes(payload)
        return True

    def delete(self, *names: str) -> int:
        removed = 0
        for name in names:
            if name in self.kv:
                self.kv.pop(name, None)
                removed += 1
        return removed

    def rpush(self, name: str, *values) -> int:
        return 0

    def lpop(self, name: str):
        return None


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


def test_NFR_OBS_runtime_login_limit_requires_redis_cache():
    with pytest.raises(RuntimeError, match="PIVOT_CACHE_STORE=redis"):
        assemble_runtime_app(
            _settings(login_max_failures=3, login_window_seconds=60)
        )
    with pytest.raises(RuntimeError, match="PIVOT_LOGIN_WINDOW_SECONDS"):
        RuntimeSettings.from_env(
            {
                "PIVOT_TOKEN_SECRET": "runtime-test-secret",
                "PIVOT_ACCESS_TTL": "60",
                "PIVOT_REFRESH_TTL": "3600",
                "PIVOT_EXPORT_TTL": "3600",
                "PIVOT_DOWNLOAD_TTL": "300",
                "PIVOT_EXPORT_PUBLIC_BASE": "https://files.pivot.test",
                "PIVOT_RETRIEVAL_K": "4",
                "PIVOT_LOGIN_MAX_FAILURES": "3",
            }
        )


def test_NFR_OBS_runtime_redis_login_limiter_uses_cache():
    assembly = assemble_runtime(
        _settings(
            cache_store="redis",
            redis_endpoint="cache.test:6380",
            redis_client=_FakeRedisClient(),
            login_max_failures=2,
            login_window_seconds=60,
        )
    )
    assert isinstance(assembly.cache, RedisCacheStore)
    assert isinstance(assembly.attempts, CacheLoginAttempts)
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "PIVOT_LOGIN_MAX_FAILURES" in example
    assert "PIVOT_LOGIN_WINDOW_SECONDS" in example
    assert "TBD-P0" in example
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "TBD-P0" in evidence


def test_NFR_OBS_runtime_default_login_limiter_never_locks():
    assembly = assemble_runtime(_settings())
    assert isinstance(assembly.attempts, InMemoryAttempts)
    assembly.attempts.record_failure("admin")
    assembly.attempts.record_failure("admin")
    assert assembly.attempts.is_blocked("admin") is False


def test_FR_AUTH_002_http_runtime_lockout_same_error():
    client = TestClient(
        assemble_runtime_app(
            _settings(
                cache_store="redis",
                redis_endpoint="cache.test:6380",
                redis_client=_FakeRedisClient(),
                login_max_failures=2,
                login_window_seconds=60,
            )
        ),
        base_url="https://testserver",
    )
    first = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "nope"},
        headers={"X-Request-ID": "req_fail_1"},
    )
    second = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "nope"},
        headers={"X-Request-ID": "req_fail_2"},
    )
    locked = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_locked"},
    )
    assert first.status_code == second.status_code == locked.status_code == 401
    assert first.json()["code"] == locked.json()["code"] == "AUTH_INVALID_CREDENTIALS"
    assert first.json()["message"] == locked.json()["message"] == "账号或密码错误"


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


def _example_assignment(example: str, key: str) -> str:
    return next(
        line.split("=", 1)[1].strip()
        for line in example.splitlines()
        if line.startswith(f"{key}=")
    )


def test_NFR_OBS_compose_api_injects_login_limit_without_hardcoding():
    compose = _COMPOSE.read_text(encoding="utf-8")
    services = _service_blocks(compose)
    api = services["api"]
    worker = services["worker"]
    for key in _LOGIN_LIMIT_ENV:
        assert f"{key}:" in api
        assert "${" + key in api
        assert f"${{{key}:?" in api
        assert f"${{{key}:-" not in api
        assert re.search(rf"{key}:\s*\d+", api) is None
        assert f"{key}:" not in worker
    example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    failures = _example_assignment(example, "PIVOT_LOGIN_MAX_FAILURES")
    window = _example_assignment(example, "PIVOT_LOGIN_WINDOW_SECONDS")
    assert failures.isdigit() and int(failures) > 0
    assert window.isdigit() and int(window) > 0
    assert "TBD-P0" in example
    intent = _INTENT.read_text(encoding="utf-8")
    assert "PIVOT_LOGIN_MAX_FAILURES" in intent
    assert "PIVOT_LOGIN_WINDOW_SECONDS" in intent
    evidence = _COMPOSE_EVIDENCE.read_text(encoding="utf-8")
    assert "TBD-P0" in evidence
    assert "不写死" in evidence or "禁止写死" in evidence


def test_GATE_P0_005_not_verified_by_compose_login_rate():
    evidence = _COMPOSE_EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-005" in evidence
    assert "unverified" in evidence.lower()
    assert "TBD-P0" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-005" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
