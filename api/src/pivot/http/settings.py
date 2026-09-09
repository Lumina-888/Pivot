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
    return _positive_int(raw, key)


def _optional_int_or_none(environ: Mapping[str, str], key: str) -> int | None:
    raw = (environ.get(key) or "").strip()
    if not raw:
        return None
    return _positive_int(raw, key)


def _optional_non_negative_int(environ: Mapping[str, str], key: str) -> int | None:
    raw = (environ.get(key) or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{key} must be a non-negative integer") from exc
    if value < 0:
        raise RuntimeError(f"{key} must be a non-negative integer")
    return value


def _positive_int(raw: str, key: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{key} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{key} must be a positive integer")
    return value


def _optional_positive_float(environ: Mapping[str, str], key: str) -> float | None:
    raw = (environ.get(key) or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{key} must be a positive number") from exc
    if value <= 0:
        raise RuntimeError(f"{key} must be a positive number")
    return value


def _optional_unit_float(environ: Mapping[str, str], key: str) -> float | None:
    raw = (environ.get(key) or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{key} must be between 0 and 1") from exc
    if value < 0 or value > 1:
        raise RuntimeError(f"{key} must be between 0 and 1")
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
    database_url: str | None = None
    create_schema: bool = False
    object_store: str = "memory"
    minio_endpoint: str | None = None
    minio_bucket: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_secure: bool = False
    minio_ensure_bucket: bool = False
    object_store_client: object | None = None
    vector_store: str = "memory"
    qdrant_endpoint: str | None = None
    qdrant_collection: str | None = None
    qdrant_api_key: str | None = None
    qdrant_ensure_collection: bool = False
    qdrant_vector_size: int | None = None
    qdrant_distance: str | None = None
    vector_store_client: object | None = None
    query_embedder: object | None = None
    bm25_k1: float | None = None
    bm25_b: float | None = None
    rerank: str = "none"
    cache_store: str = "memory"
    queue_store: str = "memory"
    redis_endpoint: str | None = None
    redis_password: str | None = None
    redis_db: int | None = None
    redis_key_prefix: str = "pivot:"
    redis_client: object | None = None

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
        if (self.bm25_k1 is None) != (self.bm25_b is None):
            raise RuntimeError(
                "PIVOT_BM25_K1 and PIVOT_BM25_B must both be set or both omitted"
            )
        if self.bm25_k1 is not None and self.bm25_k1 <= 0:
            raise RuntimeError("PIVOT_BM25_K1 must be a positive number")
        if self.bm25_b is not None and (self.bm25_b < 0 or self.bm25_b > 1):
            raise RuntimeError("PIVOT_BM25_B must be between 0 and 1")
        if self.rerank not in {"none", "overlap", "bm25"}:
            raise RuntimeError(
                "unsupported PIVOT_RERANK="
                f"{self.rerank!r}; this slice wires none, overlap, or bm25"
            )
        if self.rerank == "bm25" and self.bm25_k1 is None:
            raise RuntimeError(
                "PIVOT_BM25_K1 and PIVOT_BM25_B are required when PIVOT_RERANK=bm25"
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
            database_url=(env.get("PIVOT_DATABASE_URL") or "").strip() or None,
            create_schema=(env.get("PIVOT_DB_CREATE_SCHEMA") or "").strip() == "1",
            object_store=(env.get("PIVOT_OBJECT_STORE") or "memory").strip() or "memory",
            minio_endpoint=(env.get("PIVOT_MINIO_ENDPOINT") or "").strip() or None,
            minio_bucket=(env.get("PIVOT_MINIO_BUCKET") or "").strip() or None,
            minio_access_key=(env.get("PIVOT_MINIO_ACCESS_KEY") or "").strip() or None,
            minio_secret_key=(env.get("PIVOT_MINIO_SECRET_KEY") or "").strip() or None,
            minio_secure=(env.get("PIVOT_MINIO_SECURE") or "").strip() == "1",
            minio_ensure_bucket=(env.get("PIVOT_MINIO_ENSURE_BUCKET") or "").strip() == "1",
            vector_store=(env.get("PIVOT_VECTOR_STORE") or "memory").strip() or "memory",
            qdrant_endpoint=(env.get("PIVOT_QDRANT_ENDPOINT") or "").strip() or None,
            qdrant_collection=(env.get("PIVOT_QDRANT_COLLECTION") or "").strip() or None,
            qdrant_api_key=(env.get("PIVOT_QDRANT_API_KEY") or "").strip() or None,
            qdrant_ensure_collection=(
                env.get("PIVOT_QDRANT_ENSURE_COLLECTION") or ""
            ).strip()
            == "1",
            qdrant_vector_size=_optional_int_or_none(env, "PIVOT_QDRANT_VECTOR_SIZE"),
            qdrant_distance=(env.get("PIVOT_QDRANT_DISTANCE") or "").strip() or None,
            bm25_k1=_optional_positive_float(env, "PIVOT_BM25_K1"),
            bm25_b=_optional_unit_float(env, "PIVOT_BM25_B"),
            rerank=(env.get("PIVOT_RERANK") or "none").strip() or "none",
            cache_store=(env.get("PIVOT_CACHE_STORE") or "memory").strip() or "memory",
            queue_store=(env.get("PIVOT_QUEUE_STORE") or "memory").strip() or "memory",
            redis_endpoint=(env.get("PIVOT_REDIS_ENDPOINT") or "").strip() or None,
            redis_password=(env.get("PIVOT_REDIS_PASSWORD") or "").strip() or None,
            redis_db=_optional_non_negative_int(env, "PIVOT_REDIS_DB"),
            redis_key_prefix=(env.get("PIVOT_REDIS_KEY_PREFIX") or "pivot:").strip()
            or "pivot:",
        )
