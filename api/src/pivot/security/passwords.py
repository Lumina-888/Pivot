"""Password hashing ports (NFR-SEC-004). Production uses Argon2id."""

from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class Argon2idHasher:
    """Argon2id hasher. Requires argon2-cffi (see M01 change request)."""

    def __init__(
        self,
        time_cost: int = 3,
        memory_cost: int = 65536,
        parallelism: int = 4,
    ) -> None:
        self._time_cost = time_cost
        self._memory_cost = memory_cost
        self._parallelism = parallelism

    def _backend(self):
        try:
            from argon2 import PasswordHasher as _PasswordHasher
            from argon2.exceptions import InvalidHash, VerifyMismatchError
        except ImportError as exc:  # pragma: no cover - production extra
            raise RuntimeError(
                "argon2-cffi is required for Argon2idHasher; "
                "see progress/changes/20260906-M01-auth-dependencies.md"
            ) from exc
        hasher = _PasswordHasher(
            time_cost=self._time_cost,
            memory_cost=self._memory_cost,
            parallelism=self._parallelism,
        )
        return hasher, InvalidHash, VerifyMismatchError

    def hash(self, password: str) -> str:
        if not password:
            raise ValueError("password required")
        hasher, _, _ = self._backend()
        digest = hasher.hash(password)
        if not digest.startswith("$argon2id$"):
            raise RuntimeError("password hasher did not produce Argon2id")
        return digest

    def verify(self, password: str, password_hash: str) -> bool:
        hasher, invalid_hash, mismatch = self._backend()
        try:
            return bool(hasher.verify(password_hash, password))
        except (invalid_hash, mismatch, ValueError, TypeError):
            return False
