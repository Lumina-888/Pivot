"""Injected runtime settings. No production URLs or TBD-P0 values are hard-coded."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


def _require(environ: Mapping[str, str], key: str) -> str:
    value = (environ.get(key) or "").strip()
    if not value:
        raise RuntimeError(f"{key} is required for runtime assembly")
    return value


def _require_int(environ: Mapping[str, str], key: str) -> int:
    raw = _require(environ, key)
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{key} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{key} must be a positive integer")
    return value


def _optional_int(environ: Mapping[str, str], key: str, default: int) -> int:
    raw = (environ.get(key) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{key} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{key} must be a positive integer")
    return value


@dataclass(frozen=True)
class RuntimeSettings:
    storage: str
    token_secret: str
    access_ttl: int
    refresh_ttl: int
    export_ttl: int
    download_ttl: int
    export_public_base: str
    retrieval_k: int
    bootstrap_username: str | None = None
    bootstrap_password: str | None = None
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 4

    def __post_init__(self) -> None:
        if not self.token_secret.strip():
            raise RuntimeError("PIVOT_TOKEN_SECRET is required for runtime assembly")
        if (
            min(
                self.access_ttl,
                self.refresh_ttl,
                self.export_ttl,
                self.download_ttl,
                self.retrieval_k,
            )
            <= 0
        ):
            raise RuntimeError("injected TTL and retrieval k must be positive")
        if bool(self.bootstrap_username) != bool(self.bootstrap_password):
            raise RuntimeError(
                "bootstrap username and password must both be set or both omitted"
            )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> RuntimeSettings:
        env = os.environ if environ is None else environ
        username = (env.get("PIVOT_BOOTSTRAP_USERNAME") or "").strip() or None
        password = env.get("PIVOT_BOOTSTRAP_PASSWORD") or None
        if password is not None:
            password = password.strip() or None
        return cls(
            storage=(env.get("PIVOT_STORAGE") or "memory").strip() or "memory",
            token_secret=_require(env, "PIVOT_TOKEN_SECRET"),
            access_ttl=_require_int(env, "PIVOT_ACCESS_TTL"),
            refresh_ttl=_require_int(env, "PIVOT_REFRESH_TTL"),
            export_ttl=_require_int(env, "PIVOT_EXPORT_TTL"),
            download_ttl=_require_int(env, "PIVOT_DOWNLOAD_TTL"),
            export_public_base=_require(env, "PIVOT_EXPORT_PUBLIC_BASE"),
            retrieval_k=_require_int(env, "PIVOT_RETRIEVAL_K"),
            bootstrap_username=username,
            bootstrap_password=password,
            argon2_time_cost=_optional_int(env, "PIVOT_ARGON2_TIME_COST", 3),
            argon2_memory_cost=_optional_int(env, "PIVOT_ARGON2_MEMORY_COST", 65536),
            argon2_parallelism=_optional_int(env, "PIVOT_ARGON2_PARALLELISM", 4),
        )
