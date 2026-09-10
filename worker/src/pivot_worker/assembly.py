"""Assemble a worker ingest runner against shared PG facts and MinIO bytes."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from pivot.db.documents import (
    SqlAlchemyChunkStore,
    SqlAlchemyDocumentStore,
    SqlAlchemyTaskStore,
    SqlAlchemyVersionStore,
)
from pivot.db.models import Base
from pivot.db.session import create_db_engine, session_factory
from pivot.documents.service import DocumentService
from pivot.storage.adapters.minio import MinioObjectStore, connect_minio_client
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pivot_worker.runtime import DocumentIngestRunner


def _require(environ: Mapping[str, str], key: str) -> str:
    value = (environ.get(key) or "").strip()
    if not value:
        raise RuntimeError(f"{key} is required for the worker ingest runner")
    return value


class _NullAudits:
    def emit(self, event: object) -> None:
        return None


@dataclass(frozen=True)
class IngestAssemblySettings:
    storage: str
    object_store: str
    database_url: str | None = None
    create_schema: bool = False
    minio_endpoint: str | None = None
    minio_bucket: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_secure: bool = False
    minio_ensure_bucket: bool = False
    object_store_client: object | None = None

    def __post_init__(self) -> None:
        if self.storage != "postgres":
            raise RuntimeError(
                "PIVOT_STORAGE=postgres is required for the worker ingest runner; "
                "memory facts cannot be shared across processes"
            )
        if self.object_store != "minio":
            raise RuntimeError(
                "PIVOT_OBJECT_STORE=minio is required for the worker ingest runner; "
                "memory objects cannot be shared across processes"
            )
        url = (self.database_url or "").strip()
        if not url:
            raise RuntimeError("PIVOT_DATABASE_URL is required when PIVOT_STORAGE=postgres")
        if not (self.minio_endpoint or "").strip() or not (self.minio_bucket or "").strip():
            raise RuntimeError(
                "PIVOT_MINIO_ENDPOINT and PIVOT_MINIO_BUCKET are required "
                "when PIVOT_OBJECT_STORE=minio"
            )
        if self.create_schema and not url.startswith("sqlite"):
            raise RuntimeError("PIVOT_DB_CREATE_SCHEMA is only allowed for sqlite test URLs")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> IngestAssemblySettings:
        env = os.environ if environ is None else environ
        return cls(
            storage=_require(env, "PIVOT_STORAGE"),
            database_url=(env.get("PIVOT_DATABASE_URL") or "").strip() or None,
            create_schema=(env.get("PIVOT_DB_CREATE_SCHEMA") or "").strip() == "1",
            object_store=_require(env, "PIVOT_OBJECT_STORE"),
            minio_endpoint=(env.get("PIVOT_MINIO_ENDPOINT") or "").strip() or None,
            minio_bucket=(env.get("PIVOT_MINIO_BUCKET") or "").strip() or None,
            minio_access_key=(env.get("PIVOT_MINIO_ACCESS_KEY") or "").strip() or None,
            minio_secret_key=(env.get("PIVOT_MINIO_SECRET_KEY") or "").strip() or None,
            minio_secure=(env.get("PIVOT_MINIO_SECURE") or "").strip() == "1",
            minio_ensure_bucket=(env.get("PIVOT_MINIO_ENSURE_BUCKET") or "").strip() == "1",
        )


@dataclass(frozen=True)
class IngestAssembly:
    runner: DocumentIngestRunner
    documents: DocumentService
    objects: MinioObjectStore
    storage: str
    object_store: str


def _engine_kwargs(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


def _open_postgres_engine(settings: IngestAssemblySettings) -> Engine:
    url = settings.database_url or ""
    engine = create_db_engine(url, **_engine_kwargs(url))
    if settings.create_schema:
        Base.metadata.create_all(engine)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise RuntimeError("postgres is not reachable") from exc
    return engine


def _open_minio_store(settings: IngestAssemblySettings) -> MinioObjectStore:
    client = settings.object_store_client
    if client is None:
        if not settings.minio_access_key or not settings.minio_secret_key:
            raise RuntimeError(
                "PIVOT_MINIO_ACCESS_KEY and PIVOT_MINIO_SECRET_KEY are required "
                "when PIVOT_OBJECT_STORE=minio"
            )
        client = connect_minio_client(
            endpoint=settings.minio_endpoint or "",
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    store = MinioObjectStore(
        client,
        bucket=settings.minio_bucket or "",
        ensure_bucket=settings.minio_ensure_bucket,
    )
    if not store.healthy():
        raise RuntimeError("minio is not reachable")
    return store


def assemble_ingest_runtime(
    settings: IngestAssemblySettings | None = None,
) -> IngestAssembly:
    resolved = settings or IngestAssemblySettings.from_env()
    engine = _open_postgres_engine(resolved)
    sessions = session_factory(engine)
    objects = _open_minio_store(resolved)
    documents = DocumentService(
        documents=SqlAlchemyDocumentStore(sessions),
        versions=SqlAlchemyVersionStore(sessions),
        chunks=SqlAlchemyChunkStore(sessions),
        tasks=SqlAlchemyTaskStore(sessions),
        objects=objects,
        audits=_NullAudits(),
    )
    return IngestAssembly(
        runner=DocumentIngestRunner(documents),
        documents=documents,
        objects=objects,
        storage=resolved.storage,
        object_store=resolved.object_store,
    )
