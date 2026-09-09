"""Redis-backed cache and queue. Endpoint and key prefix are injected.

Redis is not a business fact store. Queue loss and cache expiry must not make
PostgreSQL facts unrecoverable (SPEC §2.1).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol
from uuid import uuid4

from pivot.storage.config import CacheStoreConfig, QueueStoreConfig
from pivot.storage.protocols import CacheStore, QueueStore

__all__ = [
    "CacheStore",
    "QueueStore",
    "RedisCacheStore",
    "RedisQueueStore",
    "connect_redis_client",
]


class RedisClient(Protocol):
    def ping(self) -> bool: ...
    def get(self, name: str): ...
    def set(self, name: str, value, ex=None): ...
    def delete(self, *names: str) -> int: ...
    def rpush(self, name: str, *values) -> int: ...
    def lpop(self, name: str): ...


def _normalize_endpoint(endpoint: str) -> str:
    raw = endpoint.strip()
    if not raw:
        raise RuntimeError("PIVOT_REDIS_ENDPOINT is required when a Redis store is selected")
    if "://" not in raw:
        return f"redis://{raw.rstrip('/')}"
    return raw.rstrip("/")


def connect_redis_client(
    *,
    endpoint: str,
    password: str | None = None,
    db: int | None = None,
):
    url = _normalize_endpoint(endpoint)
    try:
        import redis
    except ImportError as exc:
        raise RuntimeError("redis extra is not installed; pip install -e ./api[redis]") from exc
    kwargs: dict[str, object] = {}
    if password:
        kwargs["password"] = password
    if db is not None:
        kwargs["db"] = db
    return redis.Redis.from_url(url, **kwargs)


def _require_token(value: str, *, label: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise ValueError(f"{label} must be non-empty")
    return token


def _as_bytes(value) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode()
    raise TypeError("redis value must be bytes")


class RedisCacheStore:
    """Short-term cache/rate-limit state; not a business fact store."""

    def __init__(self, client: RedisClient, *, prefix: str) -> None:
        self._client = client
        self._prefix = _require_token(prefix, label="prefix")

    @classmethod
    def connect(
        cls,
        config: CacheStoreConfig,
        *,
        password: str | None = None,
        db: int | None = None,
    ) -> "RedisCacheStore":
        client = connect_redis_client(endpoint=config.endpoint, password=password, db=db)
        return cls(client, prefix=config.key_prefix)

    def healthy(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def get(self, key: str) -> bytes | None:
        value = self._client.get(self._namespaced(key))
        if value is None:
            return None
        return _as_bytes(value)

    def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._client.set(self._namespaced(key), _as_bytes(value), ex=ttl_seconds)

    def delete(self, key: str) -> None:
        self._client.delete(self._namespaced(key))

    def _namespaced(self, key: str) -> str:
        return f"{self._prefix}{_require_token(key, label='cache key')}"


class RedisQueueStore:
    """Short-lived task queue; queue loss must not lose business facts."""

    def __init__(self, client: RedisClient, *, prefix: str) -> None:
        self._client = client
        self._prefix = _require_token(prefix, label="prefix")

    @classmethod
    def connect(
        cls,
        config: QueueStoreConfig,
        *,
        password: str | None = None,
        db: int | None = None,
        key_prefix: str = "pivot:",
    ) -> "RedisQueueStore":
        client = connect_redis_client(endpoint=config.endpoint, password=password, db=db)
        return cls(client, prefix=key_prefix)

    def healthy(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def enqueue(self, queue: str, payload: Mapping) -> str:
        if not isinstance(payload, Mapping):
            raise ValueError("queue payload must be a mapping")
        message_id = f"qmsg_{uuid4().hex}"
        body = json.dumps(
            {"message_id": message_id, "payload": dict(payload)},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self._client.rpush(self._queue_key(queue), body.encode())
        return message_id

    def dequeue(self, queue: str) -> Mapping | None:
        raw = self._client.lpop(self._queue_key(queue))
        if raw is None:
            return None
        try:
            decoded = json.loads(_as_bytes(raw).decode())
        except (TypeError, ValueError, UnicodeDecodeError) as exc:
            raise ValueError("queue payload must be JSON") from exc
        if not isinstance(decoded, Mapping):
            raise ValueError("queue payload must be a mapping")
        body = decoded.get("payload", decoded)
        if not isinstance(body, Mapping):
            raise ValueError("queue payload must be a mapping")
        return dict(body)

    def _queue_key(self, queue: str) -> str:
        return f"{self._prefix}queue:{_require_token(queue, label='queue')}"
