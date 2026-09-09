"""Composition root: wire ports and domain services for a bootable FastAPI app."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.ports import UserAccount, UserDirectory
from pivot.auth.service import AuthService
from pivot.auth.tokens import TokenService
from pivot.db.models import Base
from pivot.db.session import create_db_engine, session_factory
from pivot.db.users import SqlAlchemyUserDirectory
from pivot.documents.service import DocumentService
from pivot.exports.repository import InMemoryExportRepository
from pivot.exports.service import ExportService
from pivot.exports.signer import PublicDownloadSigner
from pivot.http.app import create_app
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
from pivot.qa.orchestrator import QaOrchestrator
from pivot.qa.ports import EvidenceHit, RetrievalResult
from pivot.retrieval.fakes import KeywordRetriever
from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService
from pivot.runs.conversations import ConversationService
from pivot.runs.service import RunService
from pivot.security.passwords import Argon2idHasher
from pivot.security.rbac import AccessControl
from pivot.shared.ids import new_id


@dataclass(frozen=True)
class RuntimeAssembly:
    app: FastAPI
    hasher: Argon2idHasher
    users: UserDirectory
    storage: str


class _RuntimeProbes:
    def __init__(self, postgres_engine: Engine | None = None) -> None:
        self._postgres_engine = postgres_engine

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
        return False

    def qdrant(self) -> bool:
        return False

    def redis(self) -> bool:
        return False


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


class _RetrievalBridge:
    def __init__(self, retrieval: RetrievalService) -> None:
        self._retrieval = retrieval

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
    hasher = Argon2idHasher(
        time_cost=resolved.argon2_time_cost,
        memory_cost=resolved.argon2_memory_cost,
        parallelism=resolved.argon2_parallelism,
    )
    clock = UtcClock()
    probes = None
    if resolved.storage == "postgres":
        postgres_engine = _open_postgres_engine(resolved)
        users: UserDirectory = SqlAlchemyUserDirectory(session_factory(postgres_engine))
        probes = _RuntimeProbes(postgres_engine)
    else:
        users = InMemoryUserDirectory()
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
    auth = AuthService(
        users=users,
        hasher=hasher,
        tokens=TokenService(
            secret=resolved.token_secret,
            access_ttl=resolved.access_ttl,
            clock=clock,
        ),
        refresh_tokens=InMemoryRefreshStore(),
        audits=InMemoryAuthAudit(),
        attempts=InMemoryAttempts(),
        access=AccessControl(resources),
        clock=clock,
        access_ttl=resolved.access_ttl,
        refresh_ttl=resolved.refresh_ttl,
    )
    documents = DocumentService(
        documents=MemoryDocuments(),
        versions=MemoryVersions(),
        chunks=MemoryChunks(),
        tasks=MemoryTasks(),
        objects=MemoryDocumentObjects(),
        audits=MemoryDocumentAudits(),
    )
    policy = RetrievalPolicy(
        dense_k=resolved.retrieval_k,
        bm25_k=resolved.retrieval_k,
        rrf_k=resolved.retrieval_k,
        evidence_limit=resolved.retrieval_k,
    )
    empty_corpus: tuple = ()
    retrieval = RetrievalService(
        corpus=empty_corpus,
        dense=KeywordRetriever(empty_corpus, "dense"),
        bm25=KeywordRetriever(empty_corpus, "bm25"),
        policy=policy,
    )
    runs = RunService()
    conversations = ConversationService(runs=runs)
    export_repo = InMemoryExportRepository()
    export_clock = UtcClock()
    audits = AuditService(AppendOnlyAuditStore(), export_clock)
    exports = ExportService(
        access=MemoryExportAccess(export_repo, resources),
        answers=MemoryAnswerStore(),
        exports=export_repo,
        objects=MemoryExportObjects(resolved.export_public_base),
        audits=audits,
        clock=export_clock,
        signer=PublicDownloadSigner(resolved.export_public_base, resolved.token_secret),
        ttl_seconds=resolved.export_ttl,
        download_ttl_seconds=resolved.download_ttl,
    )
    app = create_app(
        probes=probes,
        auth=auth,
        documents=documents,
        retrieval=retrieval,
        runs=runs,
        qa=QaOrchestrator(_RetrievalBridge(retrieval)),
        conversations=conversations,
        exports=exports,
        audits=audits,
    )
    return RuntimeAssembly(app=app, hasher=hasher, users=users, storage=resolved.storage)


def assemble_runtime_app(settings: RuntimeSettings | None = None) -> FastAPI:
    return assemble_runtime(settings).app
