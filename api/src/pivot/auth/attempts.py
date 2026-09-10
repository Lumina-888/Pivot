"""Login failure limiter. Threshold and window are injected, not frozen TBD-P0."""

from __future__ import annotations

from pivot.storage.protocols import CacheStore


class CacheLoginAttempts:
    def __init__(
        self,
        cache: CacheStore,
        *,
        max_failures: int,
        window_seconds: int,
    ) -> None:
        if max_failures <= 0:
            raise ValueError("max_failures must be a positive integer")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be a positive integer")
        self._cache = cache
        self._max_failures = max_failures
        self._window_seconds = window_seconds

    def record_failure(self, username: str) -> int:
        key = self._key(username)
        raw = self._cache.get(key)
        count = _as_count(raw) + 1
        self._cache.set(key, str(count).encode(), ttl_seconds=self._window_seconds)
        return count

    def reset(self, username: str) -> None:
        self._cache.delete(self._key(username))

    def is_blocked(self, username: str) -> bool:
        raw = self._cache.get(self._key(username))
        if raw is None:
            return False
        return _as_count(raw) >= self._max_failures

    def _key(self, username: str) -> str:
        token = username.strip()
        if not token:
            raise ValueError("username must be non-empty")
        return f"login-attempts:{token}"


def _as_count(raw: bytes | None) -> int:
    if raw is None:
        return 0
    try:
        value = int(raw.decode())
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("login attempt counter must be an integer") from exc
    if value < 0:
        raise ValueError("login attempt counter must be non-negative")
    return value
