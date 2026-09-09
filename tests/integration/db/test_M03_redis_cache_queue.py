"""Redis CacheStore/QueueStore adapter. Default CI uses an injected client."""

from __future__ import annotations

from pathlib import Path
from time import monotonic

import pytest
from pivot.storage.adapters.redis import RedisCacheStore, RedisQueueStore
from pivot.storage.config import CacheStoreConfig, QueueStoreConfig


class FakeRedisClient:
    def __init__(self) -> None:
        self.kv: dict[str, tuple[bytes, float | None]] = {}
        self.lists: dict[str, list[bytes]] = {}

    def ping(self) -> bool:
        return True

    def get(self, name: str):
        item = self.kv.get(name)
        if item is None:
            return None
        value, expires = item
        if expires is not None and monotonic() >= expires:
            self.kv.pop(name, None)
            return None
        return value

    def set(self, name: str, value, ex=None):
        payload = value if isinstance(value, (bytes, bytearray)) else str(value).encode()
        expires = None if ex is None else monotonic() + int(ex)
        self.kv[name] = (bytes(payload), expires)
        return True

    def delete(self, *names: str) -> int:
        removed = 0
        for name in names:
            existed = name in self.kv or name in self.lists
            self.kv.pop(name, None)
            self.lists.pop(name, None)
            if existed:
                removed += 1
        return removed

    def rpush(self, name: str, *values) -> int:
        bucket = self.lists.setdefault(name, [])
        for value in values:
            payload = value if isinstance(value, (bytes, bytearray)) else str(value).encode()
            bucket.append(bytes(payload))
        return len(bucket)

    def lpop(self, name: str):
        bucket = self.lists.get(name) or []
        if not bucket:
            return None
        return bucket.pop(0)


def _stores(
    client: FakeRedisClient | None = None,
) -> tuple[FakeRedisClient, RedisCacheStore, RedisQueueStore]:
    fake = client or FakeRedisClient()
    cache = RedisCacheStore(fake, prefix="pivot:")
    queue = RedisQueueStore(fake, prefix="pivot:")
    return fake, cache, queue


def test_M03_redis_cache_roundtrip_with_injected_client():
    fake, cache, _queue = _stores()
    cache.set("rate:alice", b"2", ttl_seconds=60)
    assert cache.get("rate:alice") == b"2"
    assert cache.healthy() is True
    cache.delete("rate:alice")
    assert cache.get("rate:alice") is None
    assert any(key.startswith("pivot:") for key in fake.kv) is False


def test_M03_redis_cache_get_missing_returns_none():
    _fake, cache, _queue = _stores()
    assert cache.get("missing") is None


def test_M03_redis_cache_requires_positive_ttl():
    _fake, cache, _queue = _stores()
    with pytest.raises(ValueError, match="ttl_seconds"):
        cache.set("rate:alice", b"1", ttl_seconds=0)


def test_M03_redis_cache_prefixes_keys():
    fake, cache, _queue = _stores()
    cache.set("nfr", b"ok", ttl_seconds=30)
    assert "pivot:nfr" in fake.kv
    assert "nfr" not in fake.kv


def test_M03_redis_queue_enqueue_dequeue_fifo():
    _fake, _cache, queue = _stores()
    first = queue.enqueue("parse", {"task": "parse", "version_id": "ver_1"})
    second = queue.enqueue("parse", {"task": "parse", "version_id": "ver_2"})
    assert first != second
    assert queue.dequeue("parse") == {"task": "parse", "version_id": "ver_1"}
    assert queue.dequeue("parse") == {"task": "parse", "version_id": "ver_2"}
    assert queue.healthy() is True


def test_M03_redis_queue_dequeue_empty_returns_none():
    _fake, _cache, queue = _stores()
    assert queue.dequeue("parse") is None


def test_M03_redis_stores_are_not_business_fact_store():
    public = set(dir(RedisCacheStore)) | set(dir(RedisQueueStore))
    assert not {"save_user", "save_document", "save_run", "write_fact"}.intersection(public)
    docs = f"{RedisCacheStore.__doc__} {RedisQueueStore.__doc__}".lower()
    assert "business fact" in docs


def test_M03_redis_adapter_source_has_no_hardcoded_endpoint():
    root = Path(__file__).resolve().parents[3]
    source = (root / "api" / "src" / "pivot" / "storage" / "adapters" / "redis.py").read_text(
        encoding="utf-8"
    )
    assert "127.0.0.1" not in source
    assert "localhost" not in source
    assert ":6379" not in source
    cache_config = CacheStoreConfig(endpoint="cache.test:6380", key_prefix="pivot:")
    queue_config = QueueStoreConfig(endpoint="cache.test:6380", queue_name="parse")
    assert cache_config.endpoint == "cache.test:6380"
    assert queue_config.endpoint == "cache.test:6380"
