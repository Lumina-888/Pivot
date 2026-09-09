"""Opt-in Redis cache/queue smoke against Compose. Not GATE-P0-003 verified."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "redis-cache-queue.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_FIXTURE_ENDPOINT = "127.0.0.1:6379"


def _require_compose() -> bool:
    return os.environ.get("PIVOT_REQUIRE_COMPOSE") == "1"


def _redis_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 6379), timeout=0.3):
            return True
    except OSError:
        return False


def _redis_available() -> bool:
    try:
        import redis  # noqa: F401
    except ImportError:
        return False
    return True


def _skip_or_fail(reason: str) -> None:
    if _require_compose():
        pytest.fail(reason)
    pytest.skip(reason)


def test_M03_redis_cache_queue_when_compose_up():
    if not _redis_reachable():
        _skip_or_fail("compose redis is not reachable on 127.0.0.1:6379")
    if not _redis_available():
        _skip_or_fail("redis extra is not installed; pip install -e ./api[redis]")

    from pivot.storage.adapters.redis import RedisCacheStore, RedisQueueStore
    from pivot.storage.config import CacheStoreConfig, QueueStoreConfig

    endpoint = os.environ.get("PIVOT_REDIS_ENDPOINT", _FIXTURE_ENDPOINT)
    cache = RedisCacheStore.connect(CacheStoreConfig(endpoint=endpoint, key_prefix="pivot:"))
    queue = RedisQueueStore.connect(
        QueueStoreConfig(endpoint=endpoint, queue_name="parse"),
        key_prefix="pivot:",
    )
    cache.set("compose:nfr", b"ok", ttl_seconds=30)
    message_id = queue.enqueue("parse", {"task": "compose-smoke"})
    try:
        assert cache.get("compose:nfr") == b"ok"
        assert cache.healthy() is True
        assert queue.dequeue("parse") == {"task": "compose-smoke"}
        assert message_id
        assert queue.healthy() is True
    finally:
        cache.delete("compose:nfr")


def test_GATE_P0_003_not_verified_by_redis_cache_queue():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "redis" in evidence.lower() or "缓存" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
