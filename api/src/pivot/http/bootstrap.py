"""Composition root: wire ports and domain services for a bootable FastAPI app."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.attempts import CacheLoginAttempts
from pivot.auth.ports import UserAccount, UserDirectory
from pivot.auth.service import AuthService
from pivot.auth.tokens import TokenService
from pivot.db.conversations import SqlAlchemyConversationStore
from pivot.db.documents import (
    SqlAlchemyChunkStore,
    SqlAlchemyDocumentStore,
    SqlAlchemyTaskStore,
    SqlAlchemyVersionStore,
)
from pivot.db.exports import SqlAlchemyExportRepository
from pivot.db.models import Base
from pivot.db.refresh import SqlAlchemyRefreshTokenStore
from pivot.db.runs import SqlAlchemyRunStore
from pivot.db.session import create_db_engine, session_factory
from pivot.db.users import SqlAlchemyUserDirectory
from pivot.documents.service import DocumentService
from pivot.exports.repository import InMemoryExportRepository
from pivot.exports.service import ExportService
from pivot.exports.signer import PublicDownloadSigner
from pivot.http.app import create_app
from pivot.http.export_objects import ExportObjectAdapter
from pivot.http.memory import (
    InMemoryAttempts,
    InMemoryAuthAudit,
    InMemoryRefreshStore,
    InMemoryResources,
    InMemoryUserDirectory,
    MemoryAnswerStore,
    MemoryChunks,
    MemoryDocumentAudits,
    MemoryDocumentObjects,
    MemoryDocuments,
    MemoryExportAccess,
    MemoryExportObjects,
    MemoryTasks,
    MemoryVersions,
    UtcClock,
)
from pivot.http.settings import RuntimeSettings
from pivot.parsing import ParserRegistry, StdlibMinerUHttpClient, mineru_parser_registry
from pivot.qa.orchestrator import QaOrchestrator
from pivot.qa.ports import EvidenceHit, RetrievalResult
from pivot.qa.writer import EvidenceJoinWriter, FailoverDraftWriter, HttpDraftWriter
from pivot.retrieval.bm25 import Bm25Reranker, Bm25Retriever
from pivot.retrieval.fakes import HashingQueryEmbedder, KeywordRetriever, OverlapReranker
from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.providers import HttpBgeReranker, HttpQueryEmbedder, StdlibJsonHttpClient
from pivot.retrieval.service import RetrievalService
from pivot.retrieval.tokenize import SimpleLexTokenizer
from pivot.retrieval.vector import VectorStoreRetriever
from pivot.runs.conversations import ConversationService, InMemoryConversationStore
from pivot.runs.service import InMemoryRunStore, RunService
from pivot.security.passwords import Argon2idHasher
from pivot.security.rbac import AccessControl
from pivot.shared.ids import new_id
from pivot.storage.adapters.minio import MinioObjectStore, connect_minio_client
from pivot.storage.adapters.qdrant import QdrantVectorStore, connect_qdrant_client
from pivot.storage.adapters.redis import RedisCacheStore, RedisQueueStore, connect_redis_client


@dataclass(frozen=True)
class RuntimeAssembly:
    app: FastAPI
    hasher: Argon2idHasher
    users: UserDirectory
    storage: str
    object_store: str = "memory"
    objects: object | None = None
    vector_store: str = "memory"
    vectors: object | None = None
    cache_store: str = "memory"
    queue_store: str = "memory"
    cache: object | None = None
    queue: object | None = None
    export_objects: object | None = None
    answers: object | None = None
    resources: object | None = None
    retrieval: object | None = None
    query_embedder: object | None = None
    bm25: object | None = None
    index: object | None = None
    ingest_embedding: object | None = None
    ingest: object | None = None
    ingest_backend: str = "sync"
    attempts: object | None = None
    document_rows: object | None = None
    export_rows: object | None = None
    refresh_tokens: object | None = None
    conversation_rows: object | None = None
    conversations: object | None = None
    run_rows: object | None = None
    runs: object | None = None
    draft_writer: object | None = None
    parsers: ParserRegistry | None = None


class _ConversationBoundCatalog:
    """Resource catalog that reads conversation owners from the session store."""

    def __init__(self, inner: InMemoryResources, conversations: ConversationService) -> None:
        self._inner = inner
        self._conversations = conversations

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def get_conversation_owner(self, conversation_id: str) -> str | None:
        record = self._conversations.lookup(conversation_id)
        if record is not None:
            return record.owner_id
        return self._inner.get_conversation_owner(conversation_id)

    def claim_conversation(self, conversation_id: str, owner_id: str) -> str:
        record = self._conversations.lookup(conversation_id)
        if record is not None:
            return record.owner_id
        return self._inner.claim_conversation(conversation_id, owner_id)


class _RuntimeProbes:
    def __init__(
        self,
        postgres_engine: Engine | None = None,
        minio_store: MinioObjectStore | None = None,
        qdrant_store: QdrantVectorStore | None = None,
        redis_store: RedisCacheStore | RedisQueueStore | None = None,
    ) -> None:
        self._postgres_engine = postgres_engine
        self._minio_store = minio_store
        self._qdrant_store = qdrant_store
        self._redis_store = redis_store

    def postgres(self) -> bool:
        if self._postgres_engine is None:
            return False
        try:
            with self._postgres_engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def minio(self) -> bool:
        if self._minio_store is None:
            return False
        return bool(self._minio_store.healthy())

    def qdrant(self) -> bool:
        if self._qdrant_store is None:
            return False
        return bool(self._qdrant_store.healthy())

    def redis(self) -> bool:
        if self._redis_store is None:
            return False
        return bool(self._redis_store.healthy())


def _engine_kwargs(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


def _open_postgres_engine(settings: RuntimeSettings) -> Engine:
    if not settings.database_url:
        raise RuntimeError("PIVOT_DATABASE_URL is required when PIVOT_STORAGE=postgres")
    engine = create_db_engine(settings.database_url, **_engine_kwargs(settings.database_url))
    if settings.create_schema:
        if not settings.database_url.startswith("sqlite"):
            raise RuntimeError("PIVOT_DB_CREATE_SCHEMA is only allowed for sqlite test URLs")
        Base.metadata.create_all(engine)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise RuntimeError("postgres is not reachable") from exc
    return engine


def _open_minio_store(settings: RuntimeSettings) -> MinioObjectStore:
    if not settings.minio_endpoint or not settings.minio_bucket:
        raise RuntimeError(
            "PIVOT_MINIO_ENDPOINT and PIVOT_MINIO_BUCKET are required "
            "when PIVOT_OBJECT_STORE=minio"
        )
    client = settings.object_store_client
    if client is None:
        if not settings.minio_access_key or not settings.minio_secret_key:
            raise RuntimeError(
                "PIVOT_MINIO_ACCESS_KEY and PIVOT_MINIO_SECRET_KEY are required "
                "when PIVOT_OBJECT_STORE=minio"
            )
        client = connect_minio_client(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    store = MinioObjectStore(
        client,
        bucket=settings.minio_bucket,
        ensure_bucket=settings.minio_ensure_bucket,
    )
    if not store.healthy():
        raise RuntimeError("minio is not reachable")
    return store


def _open_qdrant_store(settings: RuntimeSettings) -> QdrantVectorStore:
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


def _index_publisher(store: QdrantVectorStore) -> object:
    try:
        from pivot_worker.index import IndexPublisher
    except ImportError as exc:
        raise RuntimeError(
            "pivot_worker is required when PIVOT_VECTOR_STORE=qdrant so ingest can publish"
        ) from exc
    return IndexPublisher(store=store)


def _parser_http_client(settings: RuntimeSettings):
    if settings.parser_http_client is not None:
        return settings.parser_http_client
    return StdlibMinerUHttpClient()


def _ingest_parsers(settings: RuntimeSettings) -> ParserRegistry | None:
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


def _ingest_runner(
    documents,
    *,
    embedding,
    index,
    dimension: int | None,
    embedding_model_version: str | None = None,
    parsers: ParserRegistry | None = None,
) -> object | None:
    try:
        from pivot_worker.runtime import DocumentIngestRunner
    except ImportError:
        return None
    kwargs: dict[str, object] = {}
    if embedding is not None:
        kwargs["embedding"] = embedding
    if index is not None:
        kwargs["index"] = index
    if dimension is not None:
        kwargs["dimension"] = dimension
    if embedding_model_version is not None:
        kwargs["embedding_model_version"] = embedding_model_version
    if parsers is not None:
        kwargs["parsers"] = parsers
    return DocumentIngestRunner(documents, **kwargs)


def _celery_submitter(runner, settings: RuntimeSettings):
    if runner is None:
        raise RuntimeError("pivot_worker is required when PIVOT_INGEST=celery")
    try:
        from pivot_worker.celery_app import CeleryIngestSubmitter
    except ImportError as exc:
        raise RuntimeError(
            "pivot_worker[celery] is required when PIVOT_INGEST=celery"
        ) from exc
    return CeleryIngestSubmitter(
        runner,
        parse_queue=settings.parse_queue or "",
        online_queue=settings.online_queue or "",
        concurrency=settings.worker_concurrency or 0,
        broker_url=settings.celery_broker,
        always_eager=settings.celery_always_eager,
    )


def _json_http_client(settings: RuntimeSettings):
    if settings.json_http_client is not None:
        return settings.json_http_client
    return StdlibJsonHttpClient()


def _http_draft_writer(
    settings: RuntimeSettings,
    *,
    endpoint: str,
    model: str,
    api_key: str,
    timeout_seconds: float | None,
    auth_header: str | None,
    auth_scheme: str | None,
):
    return HttpDraftWriter(
        _json_http_client(settings),
        endpoint=endpoint,
        model=model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        auth_header=auth_header,
        auth_scheme=auth_scheme,
    )


def _draft_writer(settings: RuntimeSettings):
    if settings.llm != "http":
        return EvidenceJoinWriter()
    primary = _http_draft_writer(
        settings,
        endpoint=settings.llm_endpoint or "",
        model=settings.llm_model or "",
        api_key=settings.llm_api_key or "",
        timeout_seconds=settings.llm_timeout,
        auth_header=settings.llm_auth_header,
        auth_scheme=settings.llm_auth_scheme,
    )
    if not (
        settings.llm_fallback_endpoint
        and settings.llm_fallback_model
        and settings.llm_fallback_api_key
    ):
        return primary
    fallback = _http_draft_writer(
        settings,
        endpoint=settings.llm_fallback_endpoint,
        model=settings.llm_fallback_model,
        api_key=settings.llm_fallback_api_key,
        timeout_seconds=settings.llm_fallback_timeout,
        auth_header=settings.llm_fallback_auth_header,
        auth_scheme=settings.llm_fallback_auth_scheme,
    )
    return FailoverDraftWriter(primary, fallback)


def _external_llm_allowed(versions, version_id: str) -> bool:
    if versions is None:
        return False
    getter = getattr(versions, "get", None)
    if getter is None:
        return False
    version = getter(version_id)
    return bool(version is not None and getattr(version, "external_llm_allowed", False))


def _query_embedder(settings: RuntimeSettings):
    if settings.query_embedder is not None:
        return settings.query_embedder
    if settings.embedding == "http":
        return HttpQueryEmbedder(
            _json_http_client(settings),
            endpoint=settings.embedding_endpoint or "",
            model=settings.embedding_model or "",
            api_key=settings.embedding_api_key or "",
            timeout_seconds=settings.embedding_timeout,
            expected_dimension=settings.qdrant_vector_size,
        )
    if settings.qdrant_vector_size is None:
        raise RuntimeError(
            "PIVOT_QDRANT_VECTOR_SIZE is required when PIVOT_VECTOR_STORE=qdrant "
            "so query embedding dimension can be injected"
        )
    return HashingQueryEmbedder(settings.qdrant_vector_size)


def _open_redis_stores(
    settings: RuntimeSettings,
) -> tuple[RedisCacheStore | None, RedisQueueStore | None, RedisCacheStore | RedisQueueStore]:
    if not settings.redis_endpoint:
        raise RuntimeError(
            "PIVOT_REDIS_ENDPOINT is required when PIVOT_CACHE_STORE=redis "
            "or PIVOT_QUEUE_STORE=redis"
        )
    client = settings.redis_client
    if client is None:
        client = connect_redis_client(
            endpoint=settings.redis_endpoint,
            password=settings.redis_password,
            db=settings.redis_db,
        )
    cache = None
    queue = None
    if settings.cache_store == "redis":
        cache = RedisCacheStore(client, prefix=settings.redis_key_prefix)
    if settings.queue_store == "redis":
        queue = RedisQueueStore(client, prefix=settings.redis_key_prefix)
    probe = cache or queue
    if probe is None or not probe.healthy():
        raise RuntimeError("redis is not reachable")
    return cache, queue, probe


class _RetrievalBridge:
    def __init__(self, retrieval: RetrievalService, versions=None) -> None:
        self._retrieval = retrieval
        self._versions = versions

    def retrieve(
        self,
        question: str,
        *,
        scope_type: str,
        scope_document_id: str | None,
        principal_id: str,
    ) -> RetrievalResult:
        outcome = self._retrieval.retrieve(
            RetrievalQuery(
                text=question,
                principal_id=principal_id,
                scope_type=scope_type,
                scope_document_id=scope_document_id,
            )
        )
        if outcome.status != "ok":
            return RetrievalResult(
                status=outcome.status,
                evidence=(),
                error_code=outcome.error_code,
            )
        evidence = tuple(
            EvidenceHit(
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                version_id=item.version_id,
                text=item.text,
                external_llm_allowed=_external_llm_allowed(
                    self._versions, item.version_id
                ),
            )
            for item in outcome.evidence
        )
        return RetrievalResult(status="ok", evidence=evidence)


def assemble_runtime(settings: RuntimeSettings | None = None) -> RuntimeAssembly:
    resolved = settings or RuntimeSettings.from_env()
    if resolved.storage not in {"memory", "postgres"}:
        raise RuntimeError(
            "unsupported PIVOT_STORAGE="
            f"{resolved.storage!r}; this slice wires memory or postgres. "
            "See progress/changes/20260909-M03-postgres-user-directory.md"
        )
    if resolved.object_store not in {"memory", "minio"}:
        raise RuntimeError(
            "unsupported PIVOT_OBJECT_STORE="
            f"{resolved.object_store!r}; this slice wires memory or minio. "
            "See progress/changes/20260909-M03-minio-object-store.md"
        )
    if resolved.vector_store not in {"memory", "qdrant"}:
        raise RuntimeError(
            "unsupported PIVOT_VECTOR_STORE="
            f"{resolved.vector_store!r}; this slice wires memory or qdrant. "
            "See progress/changes/20260909-M03-qdrant-vector-store.md"
        )
    if resolved.cache_store not in {"memory", "redis"}:
        raise RuntimeError(
            "unsupported PIVOT_CACHE_STORE="
            f"{resolved.cache_store!r}; this slice wires memory or redis. "
            "See progress/changes/20260909-M03-redis-cache-queue.md"
        )
    if resolved.queue_store not in {"memory", "redis"}:
        raise RuntimeError(
            "unsupported PIVOT_QUEUE_STORE="
            f"{resolved.queue_store!r}; this slice wires memory or redis. "
            "See progress/changes/20260909-M03-redis-cache-queue.md"
        )
    if resolved.embedding == "http" and resolved.vector_store != "qdrant":
        raise RuntimeError("PIVOT_EMBEDDING=http requires PIVOT_VECTOR_STORE=qdrant")
    hasher = Argon2idHasher(
        time_cost=resolved.argon2_time_cost,
        memory_cost=resolved.argon2_memory_cost,
        parallelism=resolved.argon2_parallelism,
    )
    clock = UtcClock()
    postgres_engine = None
    minio_store = None
    qdrant_store = None
    redis_probe = None
    cache_port = None
    queue_port = None
    document_rows: object
    version_rows: object
    chunk_rows: object
    task_rows: object
    export_rows: object
    refresh_tokens: object
    conversation_rows: object
    run_rows: object
    if resolved.storage == "postgres":
        postgres_engine = _open_postgres_engine(resolved)
        sessions = session_factory(postgres_engine)
        users: UserDirectory = SqlAlchemyUserDirectory(sessions)
        document_rows = SqlAlchemyDocumentStore(sessions)
        version_rows = SqlAlchemyVersionStore(sessions)
        chunk_rows = SqlAlchemyChunkStore(sessions)
        task_rows = SqlAlchemyTaskStore(sessions)
        export_rows = SqlAlchemyExportRepository(sessions)
        refresh_tokens = SqlAlchemyRefreshTokenStore(sessions)
        conversation_rows = SqlAlchemyConversationStore(sessions)
        run_rows = SqlAlchemyRunStore(sessions)
    else:
        users = InMemoryUserDirectory()
        document_rows = MemoryDocuments()
        version_rows = MemoryVersions()
        chunk_rows = MemoryChunks()
        task_rows = MemoryTasks()
        export_rows = InMemoryExportRepository()
        refresh_tokens = InMemoryRefreshStore()
        conversation_rows = InMemoryConversationStore()
        run_rows = InMemoryRunStore()
    if resolved.object_store == "minio":
        minio_store = _open_minio_store(resolved)
        document_objects = minio_store
    else:
        document_objects = MemoryDocumentObjects()
    query_embedder = None
    index_publisher = None
    ingest_embedding = None
    if resolved.vector_store == "qdrant":
        qdrant_store = _open_qdrant_store(resolved)
        vector_store = qdrant_store
        query_embedder = _query_embedder(resolved)
        index_publisher = _index_publisher(qdrant_store)
        ingest_embedding = query_embedder
    else:
        vector_store = None
    if resolved.cache_store == "redis" or resolved.queue_store == "redis":
        cache_port, queue_port, redis_probe = _open_redis_stores(resolved)
    probes = None
    if (
        postgres_engine is not None
        or minio_store is not None
        or qdrant_store is not None
        or redis_probe is not None
    ):
        probes = _RuntimeProbes(postgres_engine, minio_store, qdrant_store, redis_probe)
    if resolved.bootstrap_username and resolved.bootstrap_password:
        existing = users.get_by_username(resolved.bootstrap_username)
        if existing is None:
            now = clock.now()
            users.save(
                UserAccount(
                    id=new_id("user"),
                    username=resolved.bootstrap_username,
                    password_hash=hasher.hash(resolved.bootstrap_password),
                    role="admin",
                    status="active",
                    token_version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
    resources = InMemoryResources()
    runs = RunService(store=run_rows)
    conversations = ConversationService(runs=runs, store=conversation_rows)
    catalog = _ConversationBoundCatalog(resources, conversations)
    if (
        resolved.login_max_failures is not None
        and resolved.login_window_seconds is not None
        and cache_port is not None
    ):
        attempts: object = CacheLoginAttempts(
            cache_port,
            max_failures=resolved.login_max_failures,
            window_seconds=resolved.login_window_seconds,
        )
    else:
        attempts = InMemoryAttempts()
    auth = AuthService(
        users=users,
        hasher=hasher,
        tokens=TokenService(
            secret=resolved.token_secret,
            access_ttl=resolved.access_ttl,
            clock=clock,
        ),
        refresh_tokens=refresh_tokens,
        audits=InMemoryAuthAudit(),
        attempts=attempts,
        access=AccessControl(catalog),
        clock=clock,
        access_ttl=resolved.access_ttl,
        refresh_ttl=resolved.refresh_ttl,
    )
    documents = DocumentService(
        documents=document_rows,
        versions=version_rows,
        chunks=chunk_rows,
        tasks=task_rows,
        objects=document_objects,
        audits=MemoryDocumentAudits(),
    )
    parsers = _ingest_parsers(resolved)
    ingest_runner = _ingest_runner(
        documents,
        embedding=ingest_embedding,
        index=index_publisher,
        dimension=resolved.qdrant_vector_size,
        embedding_model_version=(
            resolved.embedding_model if resolved.embedding == "http" else None
        ),
        parsers=parsers,
    )
    ingest_submitter = ingest_runner
    if resolved.ingest_backend == "celery":
        ingest_submitter = _celery_submitter(ingest_runner, resolved)
    if minio_store is not None:
        export_object_store: object = ExportObjectAdapter(minio_store)
    else:
        export_object_store = MemoryExportObjects(resolved.export_public_base)
    policy = RetrievalPolicy(
        dense_k=resolved.retrieval_k,
        bm25_k=resolved.retrieval_k,
        rrf_k=resolved.retrieval_k,
        evidence_limit=resolved.retrieval_k,
    )
    empty_corpus: tuple = ()
    if qdrant_store is not None and query_embedder is not None:
        dense_retriever: object = VectorStoreRetriever(
            qdrant_store, query_embedder, source="dense"
        )
    else:
        dense_retriever = KeywordRetriever(empty_corpus, "dense")
    tokenizer = SimpleLexTokenizer()
    if resolved.bm25_k1 is not None and resolved.bm25_b is not None:
        bm25_retriever: object = Bm25Retriever(
            tokenizer, k1=resolved.bm25_k1, b=resolved.bm25_b, source="bm25"
        )
    else:
        bm25_retriever = KeywordRetriever(empty_corpus, "bm25")
    reranker = None
    if resolved.rerank == "overlap":
        reranker = OverlapReranker()
    elif resolved.rerank == "bm25":
        reranker = Bm25Reranker(tokenizer, k1=resolved.bm25_k1, b=resolved.bm25_b)
    elif resolved.rerank == "bge":
        reranker = HttpBgeReranker(
            _json_http_client(resolved),
            endpoint=resolved.rerank_endpoint or "",
            model=resolved.rerank_model or "",
            api_key=resolved.rerank_api_key or "",
            timeout_seconds=resolved.rerank_timeout,
        )
    retrieval = RetrievalService(
        corpus=empty_corpus,
        dense=dense_retriever,
        bm25=bm25_retriever,
        policy=policy,
        reranker=reranker,
    )
    export_clock = UtcClock()
    audits = AuditService(AppendOnlyAuditStore(), export_clock)
    answers = MemoryAnswerStore()
    exports = ExportService(
        access=MemoryExportAccess(export_rows, catalog),
        answers=answers,
        exports=export_rows,
        objects=export_object_store,
        audits=audits,
        clock=export_clock,
        signer=PublicDownloadSigner(resolved.export_public_base, resolved.token_secret),
        ttl_seconds=resolved.export_ttl,
        download_ttl_seconds=resolved.download_ttl,
    )
    draft_writer = _draft_writer(resolved)
    app = create_app(
        probes=probes,
        auth=auth,
        documents=documents,
        retrieval=retrieval,
        runs=runs,
        qa=QaOrchestrator(
            _RetrievalBridge(retrieval, version_rows),
            writer=draft_writer,
        ),
        conversations=conversations,
        exports=exports,
        audits=audits,
        ingest=ingest_submitter,
    )
    return RuntimeAssembly(
        app=app,
        hasher=hasher,
        users=users,
        storage=resolved.storage,
        object_store=resolved.object_store,
        objects=document_objects,
        vector_store=resolved.vector_store,
        vectors=vector_store,
        cache_store=resolved.cache_store,
        queue_store=resolved.queue_store,
        cache=cache_port,
        queue=queue_port,
        export_objects=export_object_store,
        answers=answers,
        resources=resources,
        retrieval=retrieval,
        query_embedder=query_embedder,
        bm25=bm25_retriever,
        index=index_publisher,
        ingest_embedding=ingest_embedding,
        ingest=ingest_submitter,
        ingest_backend=resolved.ingest_backend,
        attempts=attempts,
        document_rows=document_rows,
        export_rows=export_rows,
        refresh_tokens=refresh_tokens,
        conversation_rows=conversation_rows,
        conversations=conversations,
        run_rows=run_rows,
        runs=runs,
        draft_writer=draft_writer,
        parsers=parsers,
    )


def assemble_runtime_app(settings: RuntimeSettings | None = None) -> FastAPI:
    return assemble_runtime(settings).app
