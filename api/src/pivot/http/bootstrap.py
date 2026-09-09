"""Composition root: wire ports and domain services for a bootable FastAPI app."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.ports import UserAccount, UserDirectory
from pivot.auth.service import AuthService
from pivot.auth.tokens import TokenService
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
    if resolved.storage != "memory":
        raise RuntimeError(
            "unsupported PIVOT_STORAGE="
            f"{resolved.storage!r}; this slice only wires memory adapters. "
            "See progress/changes/20260909-M11-composition-root.md"
        )
    hasher = Argon2idHasher(
        time_cost=resolved.argon2_time_cost,
        memory_cost=resolved.argon2_memory_cost,
        parallelism=resolved.argon2_parallelism,
    )
    clock = UtcClock()
    users = InMemoryUserDirectory()
    if resolved.bootstrap_username and resolved.bootstrap_password:
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
