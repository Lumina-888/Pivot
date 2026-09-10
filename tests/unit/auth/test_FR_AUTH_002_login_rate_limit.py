from __future__ import annotations

import pytest
from pivot.auth.attempts import CacheLoginAttempts
from pivot.auth.errors import AuthError


class _MemoryCache:
    def __init__(self) -> None:
        self.items: dict[str, bytes] = {}

    def get(self, key: str) -> bytes | None:
        return self.items.get(key)

    def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.items[key] = value

    def delete(self, key: str) -> None:
        self.items.pop(key, None)


def _limiter(cache: _MemoryCache | None = None) -> CacheLoginAttempts:
    return CacheLoginAttempts(
        cache or _MemoryCache(),
        max_failures=2,
        window_seconds=60,
    )


def test_FR_AUTH_002_cache_attempts_block_after_injected_threshold():
    cache = _MemoryCache()
    limiter = _limiter(cache)
    assert limiter.is_blocked("alice") is False
    assert limiter.record_failure("alice") == 1
    assert limiter.is_blocked("alice") is False
    assert limiter.record_failure("alice") == 2
    assert limiter.is_blocked("alice") is True
    assert cache.items


def test_FR_AUTH_002_cache_attempts_reset_on_success():
    limiter = _limiter()
    limiter.record_failure("alice")
    limiter.record_failure("alice")
    assert limiter.is_blocked("alice") is True
    limiter.reset("alice")
    assert limiter.is_blocked("alice") is False


def test_FR_AUTH_002_missing_threshold_never_blocks(attempts):
    attempts.record_failure("alice")
    attempts.record_failure("alice")
    attempts.record_failure("alice")
    assert attempts.is_blocked("alice") is False


def test_FR_AUTH_002_blocked_login_uses_uniform_error(auth_service, attempts):
    limiter = _limiter()
    auth_service._attempts = limiter
    with pytest.raises(AuthError) as first:
        auth_service.login("alice", "wrong-password", request_id="req_one")
    with pytest.raises(AuthError) as second:
        auth_service.login("alice", "wrong-password", request_id="req_two")
    with pytest.raises(AuthError) as locked:
        auth_service.login("alice", "correct-password", request_id="req_lock")
    assert first.value.code == second.value.code == locked.value.code == "AUTH_INVALID_CREDENTIALS"
    assert first.value.message == locked.value.message == "账号或密码错误"
    assert locked.value.message != "用户不存在"
    assert locked.value.message != "密码错误"
    assert limiter.is_blocked("alice") is True
