"""Assemble a worker ingest runner against shared PG/MinIO and optional Qdrant."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pivot.audit.policy import AuditWriteFailures, TieredAuditSink
from pivot.db.audit import SqlAlchemyAuditStore, SqlAlchemyDocumentAuditSink
from pivot.db.documents import (
    SqlAlchemyChunkStore,
    SqlAlchemyDocumentStore,
    SqlAlchemyTaskStore,
    SqlAlchemyVersionStore,
)
from pivot.db.models import Base
from pivot.db.session import create_db_engine, session_factory
from pivot.documents.service import DocumentService
from pivot.parsing import (
    ParserRegistry,
    StdlibMinerUHttpClient,
    mineru_parser_registry,
    native_parser_registry,
)
from pivot.retrieval.fakes import HashingQueryEmbedder
from pivot.retrieval.providers import HttpQueryEmbedder, StdlibJsonHttpClient
from pivot.storage.adapters.minio import MinioObjectStore, connect_minio_client
from pivot.storage.adapters.qdrant import QdrantVectorStore, connect_qdrant_client
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pivot_worker.index import IndexPublisher
from pivot_worker.runtime import DocumentIngestRunner


def _require(environ: Mapping[str, str], key: str) -> str:
    value = (environ.get(key) or "").strip()
    if not value:
        raise RuntimeError(f"{key} is required for the worker ingest runner")
    return value


def _optional_positive_int(environ: Mapping[str, str], key: str) -> int | None:
    raw = (environ.get(key) or "").strip()
    if not raw:
        return None
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
    vector_store: str = "memory"
    qdrant_endpoint: str | None = None
    qdrant_collection: str | None = None
    qdrant_api_key: str | None = None
    qdrant_ensure_collection: bool = False
    qdrant_vector_size: int | None = None
    qdrant_distance: str | None = None
    vector_store_client: object | None = None
    retrieval_backend: str = "llama"
    llama_qdrant_client: object | None = None
    embedding: str = "hash"
    embedding_endpoint: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    embedding_timeout: float | None = None
    json_http_client: object | None = None
    parser: str = "local"
    parser_endpoint: str | None = None
    parser_token: str | None = None
    parser_timeout: float | None = None
    parser_poll_timeout: float | None = None
    parser_poll_interval: float | None = None
    parser_model: str | None = None
    parser_http_client: object | None = None

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
        if self.vector_store not in {"memory", "qdrant"}:
            raise RuntimeError(
                "unsupported PIVOT_VECTOR_STORE="
                f"{self.vector_store!r}; this slice wires memory or qdrant"
            )
        if self.retrieval_backend not in {"llama"}:
            raise RuntimeError(
                "unsupported PIVOT_RETRIEVAL_BACKEND="
                f"{self.retrieval_backend!r}; native was removed,"
                " llama is the only backend (ADR-020)"
            )
        if self.vector_store == "qdrant":
            if not (self.qdrant_endpoint or "").strip() or not (
                self.qdrant_collection or ""
            ).strip():
                raise RuntimeError(
                    "PIVOT_QDRANT_ENDPOINT and PIVOT_QDRANT_COLLECTION are required "
                    "when PIVOT_VECTOR_STORE=qdrant"
                )
            if self.qdrant_vector_size is None:
                raise RuntimeError(
                    "PIVOT_QDRANT_VECTOR_SIZE is required when PIVOT_VECTOR_STORE=qdrant "
                    "so ingest embedding dimension can be injected"
                )
            if self.qdrant_ensure_collection and not (self.qdrant_distance or "").strip():
                raise RuntimeError(
                    "PIVOT_QDRANT_DISTANCE is required when PIVOT_QDRANT_ENSURE_COLLECTION=1"
                )
        if self.embedding not in {"hash", "http"}:
            raise RuntimeError(
                "unsupported PIVOT_EMBEDDING="
                f"{self.embedding!r}; this slice wires hash or http"
            )
        if self.embedding == "http":
            if self.vector_store != "qdrant":
                raise RuntimeError(
                    "PIVOT_EMBEDDING=http requires PIVOT_VECTOR_STORE=qdrant"
                )
            if not (
                self.embedding_endpoint and self.embedding_model and self.embedding_api_key
            ):
                raise RuntimeError(
                    "PIVOT_EMBEDDING_ENDPOINT, PIVOT_EMBEDDING_MODEL, and "
                    "PIVOT_EMBEDDING_API_KEY are required when PIVOT_EMBEDDING=http"
                )
        if self.parser not in {"local", "mineru", "native"}:
            raise RuntimeError(
                "unsupported PIVOT_PARSER="
                f"{self.parser!r}; this slice wires local, mineru, or native"
            )
        if self.parser == "mineru" and not (
            self.parser_endpoint and self.parser_token
        ):
            raise RuntimeError(
                "PIVOT_PARSER_ENDPOINT and PIVOT_PARSER_TOKEN are required "
                "when PIVOT_PARSER=mineru"
            )

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
            vector_store=(env.get("PIVOT_VECTOR_STORE") or "memory").strip() or "memory",
            qdrant_endpoint=(env.get("PIVOT_QDRANT_ENDPOINT") or "").strip() or None,
            qdrant_collection=(env.get("PIVOT_QDRANT_COLLECTION") or "").strip() or None,
            qdrant_api_key=(env.get("PIVOT_QDRANT_API_KEY") or "").strip() or None,
            qdrant_ensure_collection=(
                env.get("PIVOT_QDRANT_ENSURE_COLLECTION") or ""
            ).strip()
            == "1",
            qdrant_vector_size=_optional_positive_int(env, "PIVOT_QDRANT_VECTOR_SIZE"),
            qdrant_distance=(env.get("PIVOT_QDRANT_DISTANCE") or "").strip() or None,
            retrieval_backend=(env.get("PIVOT_RETRIEVAL_BACKEND") or "llama").strip()
            or "llama",
            embedding=(env.get("PIVOT_EMBEDDING") or "hash").strip() or "hash",
            embedding_endpoint=(env.get("PIVOT_EMBEDDING_ENDPOINT") or "").strip()
            or None,
            embedding_model=(env.get("PIVOT_EMBEDDING_MODEL") or "").strip() or None,
            embedding_api_key=(env.get("PIVOT_EMBEDDING_API_KEY") or "").strip() or None,
            embedding_timeout=_optional_positive_float(env, "PIVOT_EMBEDDING_TIMEOUT"),
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


class _LlamaSyncingRunner:
    """Ingest runner wrapper that reconciles the llama collection.

    The worker process owns ingest under celery, so the collection-level
    reconcile the API performs for in-process ingest happens here. The
    sync never raises; the API rechecks authorization against live facts
    on every query regardless.
    """

    def __init__(self, runner, *, sync, version_rows) -> None:
        self._runner = runner
        self._sync = sync
        self._version_rows = version_rows

    def __call__(self, version_id, request_id, actor_id):
        result = self._runner(version_id, request_id, actor_id)
        version = self._version_rows.get(version_id)
        if version is not None:
            self._sync(version.document_id)
        return result


def _llama_document_sync(
    settings, *, store, document_rows, version_rows, embedding, strict: bool = False
):
    """Build the per-document reconcile callback for the worker process.

    The default logging wrapper never raises: ingest only needs a
    best-effort sync, and the API rechecks authorization against live
    facts on every query regardless. The claim-sync task instead needs
    ``strict``: failures must propagate so its bounded retries and its
    final-failure audit event can trigger (ADR-017 D3).
    """
    from pivot.retrieval.llama_embeddings import PivotEmbedding
    from pivot.retrieval.llama_index_builder import _payload_of, scroll_payloads
    from pivot.retrieval.llama_qdrant_index import LlamaLibraryIndexSet

    def external_llm_allowed(version_id: str) -> bool:
        version = version_rows.get(version_id)
        return bool(version is not None and version.external_llm_allowed)

    def library_id_for(version_id: str) -> str | None:
        try:
            version = version_rows.get(version_id)
            if version is None:
                return None
            document = document_rows.get(version.document_id)
            if document is None:
                return None
            library_id = document.library_id
            return library_id if isinstance(library_id, str) and library_id.strip() else None
        except Exception:
            return None

    def folder_id_for(version_id: str) -> str | None:
        # Live folder facts for startup partition (ADR-018 D3); None
        # means the default folder, which is the library collection.
        try:
            version = version_rows.get(version_id)
            if version is None:
                return None
            document = document_rows.get(version.document_id)
            if document is None:
                return None
            folder_id = document.folder_id
            return folder_id if isinstance(folder_id, str) and folder_id.strip() else None
        except Exception:
            return None

    client = settings.llama_qdrant_client
    if client is None:
        from pivot.storage.adapters.qdrant import _normalize_endpoint
        from qdrant_client import QdrantClient as SdkQdrantClient

        client_kwargs: dict[str, object] = {
            "url": _normalize_endpoint(settings.qdrant_endpoint or "")
        }
        if settings.qdrant_api_key:
            client_kwargs["api_key"] = settings.qdrant_api_key
        client = SdkQdrantClient(**client_kwargs)
    if not settings.qdrant_distance:
        raise RuntimeError(
            "PIVOT_QDRANT_DISTANCE is required when "
            "PIVOT_RETRIEVAL_BACKEND=llama so the worker can sync the "
            "LlamaIndex collections"
        )
    holders = LlamaLibraryIndexSet.open(
        client=client,
        native_collection=settings.qdrant_collection or "",
        embed_model=PivotEmbedding(
            embedding,
            model_name=settings.embedding_model or "hash-embedding",
            dimension=settings.qdrant_vector_size,
        ),
        vector_size=settings.qdrant_vector_size,
        distance=settings.qdrant_distance,
        native_payloads=scroll_payloads(store),
        external_llm_allowed=external_llm_allowed,
        library_id_for=library_id_for,
        folder_id_for=folder_id_for,
        hydrate=False,
    )
    logger = logging.getLogger(__name__)

    def reconcile(document_id: str) -> None:
        """Reconcile one document, raising on failure (claim-sync path)."""
        current_payloads: list = []
        document = document_rows.get(document_id)
        library_id = None
        folder_id = None
        if document is not None:
            library_id = document.library_id
            folder_id = document.folder_id
            if document.deleted_at is None:
                current = None
                for version in version_rows.list_for_document(document_id):
                    if version.current:
                        current = version
                        break
                if current is not None:
                    current_payloads = [
                        payload
                        for payload in scroll_payloads(store)
                        if _payload_of(payload).get("version_id") == current.id
                    ]
        holders.reconcile_document(
            document_id,
            library_id=library_id,
            folder_id=folder_id,
            current_payloads=current_payloads,
            external_llm_allowed=external_llm_allowed,
        )

    def sync(document_id: str) -> None:
        try:
            reconcile(document_id)
        except Exception:
            logger.exception("llama index reconcile failed for document %s", document_id)

    if strict:
        return reconcile
    return sync


@dataclass(frozen=True)
class IngestAssembly:
    runner: DocumentIngestRunner | _LlamaSyncingRunner
    documents: DocumentService
    objects: MinioObjectStore
    storage: str
    object_store: str
    vector_store: str = "memory"
    vectors: QdrantVectorStore | None = None
    index: IndexPublisher | None = None
    embedding: object | None = None
    parsers: ParserRegistry | None = None
    claim_sync: Callable[[str], None] | None = None
    claim_sync_audit: Callable[..., Any] | None = None


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


def _open_qdrant_store(settings: IngestAssemblySettings) -> QdrantVectorStore:
    if not settings.qdrant_endpoint or not settings.qdrant_collection:
        raise RuntimeError(
            "PIVOT_QDRANT_ENDPOINT and PIVOT_QDRANT_COLLECTION are required "
            "when PIVOT_VECTOR_STORE=qdrant"
        )
    if settings.qdrant_ensure_collection and (
        settings.qdrant_vector_size is None or not settings.qdrant_distance
    ):
        raise RuntimeError(
            "PIVOT_QDRANT_VECTOR_SIZE and PIVOT_QDRANT_DISTANCE are required "
            "when PIVOT_QDRANT_ENSURE_COLLECTION=1"
        )
    client = settings.vector_store_client
    if client is None:
        client = connect_qdrant_client(
            endpoint=settings.qdrant_endpoint,
            api_key=settings.qdrant_api_key,
        )
    store = QdrantVectorStore(
        client,
        collection=settings.qdrant_collection,
        ensure_collection=settings.qdrant_ensure_collection,
        vector_size=settings.qdrant_vector_size,
        distance=settings.qdrant_distance,
    )
    if not store.healthy():
        raise RuntimeError("qdrant is not reachable")
    return store


def _json_http_client(settings: IngestAssemblySettings):
    if settings.json_http_client is not None:
        return settings.json_http_client
    return StdlibJsonHttpClient()


def _parser_http_client(settings: IngestAssemblySettings):
    if settings.parser_http_client is not None:
        return settings.parser_http_client
    return StdlibMinerUHttpClient()


def _ingest_parsers(settings: IngestAssemblySettings) -> ParserRegistry | None:
    if settings.parser == "native":
        return native_parser_registry()
    if settings.parser != "mineru":
        return None
    return mineru_parser_registry(
        _parser_http_client(settings),
        endpoint=settings.parser_endpoint or "",
        token=settings.parser_token or "",
        timeout_seconds=settings.parser_timeout,
        poll_timeout_seconds=settings.parser_poll_timeout,
        poll_interval_seconds=settings.parser_poll_interval,
        model=settings.parser_model,
    )


def _ingest_embedder(settings: IngestAssemblySettings):
    if settings.embedding == "http":
        return HttpQueryEmbedder(
            _json_http_client(settings),
            endpoint=settings.embedding_endpoint or "",
            model=settings.embedding_model or "",
            api_key=settings.embedding_api_key or "",
            timeout_seconds=settings.embedding_timeout,
            expected_dimension=settings.qdrant_vector_size,
        )
    return HashingQueryEmbedder(settings.qdrant_vector_size or 0)


def assemble_ingest_runtime(
    settings: IngestAssemblySettings | None = None,
) -> IngestAssembly:
    resolved = settings or IngestAssemblySettings.from_env()
    engine = _open_postgres_engine(resolved)
    sessions = session_factory(engine)
    objects = _open_minio_store(resolved)
    document_rows = SqlAlchemyDocumentStore(sessions)
    version_rows = SqlAlchemyVersionStore(sessions)
    documents = DocumentService(
        documents=document_rows,
        versions=version_rows,
        chunks=SqlAlchemyChunkStore(sessions),
        tasks=SqlAlchemyTaskStore(sessions),
        objects=objects,
        audits=TieredAuditSink(
            SqlAlchemyDocumentAuditSink(SqlAlchemyAuditStore(sessions)),
            AuditWriteFailures(),
        ),
    )
    vectors = None
    index = None
    embedding = None
    parsers = _ingest_parsers(resolved)
    runner_kwargs: dict[str, object] = {}
    if resolved.vector_store == "qdrant":
        vectors = _open_qdrant_store(resolved)
        index = IndexPublisher(store=vectors)
        embedding = _ingest_embedder(resolved)
        runner_kwargs = {
            "embedding": embedding,
            "index": index,
            "dimension": resolved.qdrant_vector_size,
        }
        if resolved.embedding == "http" and resolved.embedding_model:
            runner_kwargs["embedding_model_version"] = resolved.embedding_model
    if parsers is not None:
        runner_kwargs["parsers"] = parsers
    runner: DocumentIngestRunner | _LlamaSyncingRunner = DocumentIngestRunner(
        documents, **runner_kwargs
    )
    if resolved.retrieval_backend == "llama" and vectors is not None and embedding is not None:
        sync = _llama_document_sync(
            resolved,
            store=vectors,
            document_rows=document_rows,
            version_rows=version_rows,
            embedding=embedding,
        )
        runner = _LlamaSyncingRunner(runner, sync=sync, version_rows=version_rows)
        # Claim-sync task (ADR-017 D3): the strict variant raises so the
        # task's bounded retries and final-failure audit can trigger.
        # AuditService shares the worker's session factory, like the
        # document stores above.
        from pivot.audit.service import AuditService
        from pivot.http.memory import UtcClock

        claim_sync = _llama_document_sync(
            resolved,
            store=vectors,
            document_rows=document_rows,
            version_rows=version_rows,
            embedding=embedding,
            strict=True,
        )
        claim_sync_audit = AuditService(
            SqlAlchemyAuditStore(sessions), UtcClock()
        ).record
    else:
        claim_sync = None
        claim_sync_audit = None
    return IngestAssembly(
        runner=runner,
        documents=documents,
        objects=objects,
        storage=resolved.storage,
        object_store=resolved.object_store,
        vector_store=resolved.vector_store,
        vectors=vectors,
        index=index,
        embedding=embedding,
        parsers=parsers,
        claim_sync=claim_sync,
        claim_sync_audit=claim_sync_audit,
    )
