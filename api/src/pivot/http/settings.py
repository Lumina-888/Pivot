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
    embedding: str = "hash"
    embedding_endpoint: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    embedding_timeout: float | None = None
    json_http_client: object | None = None
    bm25_k1: float | None = None
    bm25_b: float | None = None
    rerank: str = "none"
    rerank_endpoint: str | None = None
    rerank_model: str | None = None
    rerank_api_key: str | None = None
    rerank_timeout: float | None = None
    cache_store: str = "memory"
    queue_store: str = "memory"
    redis_endpoint: str | None = None
    redis_password: str | None = None
    redis_db: int | None = None
    redis_key_prefix: str = "pivot:"
    redis_client: object | None = None
    login_max_failures: int | None = None
    login_window_seconds: int | None = None
    ingest_backend: str = "sync"
    parse_queue: str | None = None
    online_queue: str | None = None
    worker_concurrency: int | None = None
    celery_broker: str | None = None
    celery_always_eager: bool = False
    llm: str = "local"
    llm_endpoint: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_timeout: float | None = None
    llm_auth_header: str | None = None
    llm_auth_scheme: str | None = None
    llm_fallback_endpoint: str | None = None
    llm_fallback_model: str | None = None
    llm_fallback_api_key: str | None = None
    llm_fallback_timeout: float | None = None
    llm_fallback_auth_header: str | None = None
    llm_fallback_auth_scheme: str | None = None
    parser: str = "local"
    parser_endpoint: str | None = None
    parser_token: str | None = None
    parser_timeout: float | None = None
    parser_poll_timeout: float | None = None
    parser_poll_interval: float | None = None
    parser_model: str | None = None
    parser_http_client: object | None = None

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
        if self.embedding not in {"hash", "http"}:
            raise RuntimeError(
                "unsupported PIVOT_EMBEDDING="
                f"{self.embedding!r}; this slice wires hash or http"
            )
        if self.embedding == "http" and not (
            self.embedding_endpoint and self.embedding_model and self.embedding_api_key
        ):
            raise RuntimeError(
                "PIVOT_EMBEDDING_ENDPOINT, PIVOT_EMBEDDING_MODEL, and "
                "PIVOT_EMBEDDING_API_KEY are required when PIVOT_EMBEDDING=http"
            )
        if self.rerank not in {"none", "overlap", "bm25", "bge"}:
            raise RuntimeError(
                "unsupported PIVOT_RERANK="
                f"{self.rerank!r}; this slice wires none, overlap, bm25, or bge"
            )
        if self.rerank == "bm25" and self.bm25_k1 is None:
            raise RuntimeError(
                "PIVOT_BM25_K1 and PIVOT_BM25_B are required when PIVOT_RERANK=bm25"
            )
        if self.rerank == "bge" and not (
            self.rerank_endpoint and self.rerank_model and self.rerank_api_key
        ):
            raise RuntimeError(
                "PIVOT_RERANK_ENDPOINT, PIVOT_RERANK_MODEL, and "
                "PIVOT_RERANK_API_KEY are required when PIVOT_RERANK=bge"
            )
        if (self.login_max_failures is None) != (self.login_window_seconds is None):
            raise RuntimeError(
                "PIVOT_LOGIN_MAX_FAILURES and PIVOT_LOGIN_WINDOW_SECONDS "
                "must both be set or both omitted"
            )
        if self.login_max_failures is not None and self.cache_store != "redis":
            raise RuntimeError(
                "PIVOT_LOGIN_MAX_FAILURES requires PIVOT_CACHE_STORE=redis"
            )
        if self.ingest_backend not in {"sync", "celery"}:
            raise RuntimeError(
                "unsupported PIVOT_INGEST="
                f"{self.ingest_backend!r}; this slice wires sync or celery"
            )
        if self.ingest_backend == "celery":
            parse_queue = (self.parse_queue or "").strip()
            online_queue = (self.online_queue or "").strip()
            if not parse_queue or not online_queue:
                raise RuntimeError(
                    "PIVOT_PARSE_QUEUE and PIVOT_ONLINE_QUEUE are required "
                    "when PIVOT_INGEST=celery"
                )
            if parse_queue == online_queue:
                raise RuntimeError("parse and online queues must be isolated")
            if self.worker_concurrency is None or self.worker_concurrency < 1:
                raise RuntimeError(
                    "PIVOT_WORKER_CONCURRENCY is required when PIVOT_INGEST=celery"
                )
            if not (self.celery_broker or "").strip():
                raise RuntimeError(
                    "PIVOT_CELERY_BROKER is required when PIVOT_INGEST=celery"
                )
        if self.llm not in {"local", "http"}:
            raise RuntimeError(
                "unsupported PIVOT_LLM="
                f"{self.llm!r}; this slice wires local or http"
            )
        if self.llm == "http" and not (
            self.llm_endpoint and self.llm_model and self.llm_api_key
        ):
            raise RuntimeError(
                "PIVOT_LLM_ENDPOINT, PIVOT_LLM_MODEL, and "
                "PIVOT_LLM_API_KEY are required when PIVOT_LLM=http"
            )
        fallback_fields = (
            self.llm_fallback_endpoint,
            self.llm_fallback_model,
            self.llm_fallback_api_key,
        )
        if any(fallback_fields) and not all(fallback_fields):
            raise RuntimeError(
                "PIVOT_LLM_FALLBACK_ENDPOINT, PIVOT_LLM_FALLBACK_MODEL, and "
                "PIVOT_LLM_FALLBACK_API_KEY must all be set or all omitted"
            )
        if all(fallback_fields) and self.llm != "http":
            raise RuntimeError(
                "PIVOT_LLM_FALLBACK_* requires PIVOT_LLM=http"
            )
        if self.parser not in {"local", "mineru"}:
            raise RuntimeError(
                "unsupported PIVOT_PARSER="
                f"{self.parser!r}; this slice wires local or mineru"
            )
        if self.parser == "mineru" and not (
            self.parser_endpoint and self.parser_token
        ):
            raise RuntimeError(
                "PIVOT_PARSER_ENDPOINT and PIVOT_PARSER_TOKEN are required "
                "when PIVOT_PARSER=mineru"
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
            embedding=(env.get("PIVOT_EMBEDDING") or "hash").strip() or "hash",
            embedding_endpoint=(env.get("PIVOT_EMBEDDING_ENDPOINT") or "").strip() or None,
            embedding_model=(env.get("PIVOT_EMBEDDING_MODEL") or "").strip() or None,
            embedding_api_key=(env.get("PIVOT_EMBEDDING_API_KEY") or "").strip() or None,
            embedding_timeout=_optional_positive_float(env, "PIVOT_EMBEDDING_TIMEOUT"),
            bm25_k1=_optional_positive_float(env, "PIVOT_BM25_K1"),
            bm25_b=_optional_unit_float(env, "PIVOT_BM25_B"),
            rerank=(env.get("PIVOT_RERANK") or "none").strip() or "none",
            rerank_endpoint=(env.get("PIVOT_RERANK_ENDPOINT") or "").strip() or None,
            rerank_model=(env.get("PIVOT_RERANK_MODEL") or "").strip() or None,
            rerank_api_key=(env.get("PIVOT_RERANK_API_KEY") or "").strip() or None,
            rerank_timeout=_optional_positive_float(env, "PIVOT_RERANK_TIMEOUT"),
            cache_store=(env.get("PIVOT_CACHE_STORE") or "memory").strip() or "memory",
            queue_store=(env.get("PIVOT_QUEUE_STORE") or "memory").strip() or "memory",
            redis_endpoint=(env.get("PIVOT_REDIS_ENDPOINT") or "").strip() or None,
            redis_password=(env.get("PIVOT_REDIS_PASSWORD") or "").strip() or None,
            redis_db=_optional_non_negative_int(env, "PIVOT_REDIS_DB"),
            redis_key_prefix=(env.get("PIVOT_REDIS_KEY_PREFIX") or "pivot:").strip()
            or "pivot:",
            login_max_failures=_optional_int_or_none(env, "PIVOT_LOGIN_MAX_FAILURES"),
            login_window_seconds=_optional_int_or_none(
                env, "PIVOT_LOGIN_WINDOW_SECONDS"
            ),
            ingest_backend=(env.get("PIVOT_INGEST") or "sync").strip() or "sync",
            parse_queue=(env.get("PIVOT_PARSE_QUEUE") or "").strip() or None,
            online_queue=(env.get("PIVOT_ONLINE_QUEUE") or "").strip() or None,
            worker_concurrency=_optional_int_or_none(env, "PIVOT_WORKER_CONCURRENCY"),
            celery_broker=(env.get("PIVOT_CELERY_BROKER") or "").strip() or None,
            celery_always_eager=(env.get("PIVOT_CELERY_EAGER") or "").strip() == "1",
            llm=(env.get("PIVOT_LLM") or "local").strip() or "local",
            llm_endpoint=(env.get("PIVOT_LLM_ENDPOINT") or "").strip() or None,
            llm_model=(env.get("PIVOT_LLM_MODEL") or "").strip() or None,
            llm_api_key=(env.get("PIVOT_LLM_API_KEY") or "").strip() or None,
            llm_timeout=_optional_positive_float(env, "PIVOT_LLM_TIMEOUT"),
            llm_auth_header=(env.get("PIVOT_LLM_AUTH_HEADER") or "").strip() or None,
            llm_auth_scheme=(env.get("PIVOT_LLM_AUTH_SCHEME") or "").strip() or None,
            llm_fallback_endpoint=(
                env.get("PIVOT_LLM_FALLBACK_ENDPOINT") or ""
            ).strip()
            or None,
            llm_fallback_model=(
                env.get("PIVOT_LLM_FALLBACK_MODEL") or ""
            ).strip()
            or None,
            llm_fallback_api_key=(
                env.get("PIVOT_LLM_FALLBACK_API_KEY") or ""
            ).strip()
            or None,
            llm_fallback_timeout=_optional_positive_float(
                env, "PIVOT_LLM_FALLBACK_TIMEOUT"
            ),
            llm_fallback_auth_header=(
                env.get("PIVOT_LLM_FALLBACK_AUTH_HEADER") or ""
            ).strip()
            or None,
            llm_fallback_auth_scheme=(
                env.get("PIVOT_LLM_FALLBACK_AUTH_SCHEME") or ""
            ).strip()
            or None,
            parser=(env.get("PIVOT_PARSER") or "local").strip() or "local",
            parser_endpoint=(env.get("PIVOT_PARSER_ENDPOINT") or "").strip() or None,
            parser_token=(env.get("PIVOT_PARSER_TOKEN") or "").strip() or None,
            parser_timeout=_optional_positive_float(env, "PIVOT_PARSER_TIMEOUT"),
            parser_poll_timeout=_optional_positive_float(
                env, "PIVOT_PARSER_POLL_TIMEOUT"
            ),
            parser_poll_interval=_optional_positive_float(
                env, "PIVOT_PARSER_POLL_INTERVAL"
            ),
            parser_model=(env.get("PIVOT_PARSER_MODEL") or "").strip() or None,
        )
