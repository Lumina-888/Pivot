"""In-process Wave 1 domain glue for M11. Not HTTP, not Compose, not GATE evidence."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from pivot.audit.ports import Actor
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.ports import UserAccount
from pivot.auth.service import AuthService
from pivot.auth.tokens import TokenService
from pivot.documents.ingest import DocumentIngestSink
from pivot.documents.service import DocumentService
from pivot.exports.models import CitationView, ClaimView, PersistedAnswer
from pivot.exports.repository import InMemoryExportRepository
from pivot.exports.service import ExportService
from pivot.exports.signer import PublicDownloadSigner
from pivot.parsing.models import ParsedBlock, ParsedDocument
from pivot.parsing.registry import ParserRegistry
from pivot.qa.orchestrator import QaOrchestrator
from pivot.qa.ports import EvidenceHit, RetrievalResult
from pivot.retrieval.fakes import KeywordRetriever
from pivot.retrieval.models import ChunkRecord as RetrievalChunk
from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService
from pivot.runs.conversations import ConversationService
from pivot.runs.models import RunBundle
from pivot.runs.service import RunService
from pivot.security.rbac import AccessControl
from pivot_worker.ingest import IngestRequest, IngestWorker

_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str, relative: str) -> ModuleType:
    path = _ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_auth_fakes = _load("m11_auth_fakes", "tests/unit/auth/fakes.py")
_doc_fakes = _load("m11_doc_fakes", "tests/unit/documents/fakes.py")
_export_fakes = _load("m11_export_fakes", "tests/unit/exports/fakes.py")


POLICY_TEXT = "late three times written warning. annual leave cannot carry over."


def policy_pdf() -> bytes:
    payload = f"({POLICY_TEXT}) Tj"
    return b"%PDF-1.4\n" + payload.encode("ascii") + b"\n%%EOF\n"


class FixturePdfParser:
    def parse(self, content: bytes) -> ParsedDocument:
        if not content.startswith(b"%PDF"):
            raise ValueError("not a pdf fixture")
        return ParsedDocument(
            kind="pdf",
            blocks=(ParsedBlock(text=POLICY_TEXT, locator="page=1"),),
        )


class RetrievalBridge:
    def __init__(self, retrieval: RetrievalService) -> None:
        self._retrieval = retrieval
        self.calls: list[dict[str, str | None]] = []

    def retrieve(
        self,
        question: str,
        *,
        scope_type: str,
        scope_document_id: str | None,
        principal_id: str,
    ) -> RetrievalResult:
        self.calls.append(
            {
                "question": question,
                "scope_type": scope_type,
                "scope_document_id": scope_document_id,
                "principal_id": principal_id,
            }
        )
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
                locator="",
            )
            for item in outcome.evidence
        )
        return RetrievalResult(status="ok", evidence=evidence)


def persisted_from_run(bundle: RunBundle) -> PersistedAnswer:
    claims = tuple(
        ClaimView(
            id=str(item["id"]),
            text=str(item["text"]),
            support=str(item.get("support") or "supported"),
            citation_ids=tuple(item.get("citation_ids") or ()),
        )
        for item in bundle.claims
    )
    citations = tuple(
        CitationView(
            id=str(item["id"]),
            document_id=str(item["document_id"]),
            version_id=str(item["version_id"]),
            chunk_id=str(item["chunk_id"]),
            locator=str(item.get("locator") or ""),
            snippet=str(item.get("text") or item.get("snippet") or ""),
        )
        for item in bundle.citations
    )
    return PersistedAnswer(
        conversation_id=bundle.run.conversation_id,
        run_id=bundle.run.id,
        state=bundle.run.state,
        answer_markdown=bundle.run.answer_markdown or "",
        claims=claims,
        citations=citations,
        title="pipeline-export",
        prompt="SYSTEM_PROMPT must not be exported",
        chain_of_thought="hidden thinking",
    )


class Pipeline:
    def __init__(self) -> None:
        hasher = _auth_fakes.TestPasswordHasher()
        self.hasher = hasher
        self.clock = _auth_fakes.FakeClock()
        self.users = _auth_fakes.InMemoryUserDirectory(
            [
                UserAccount(
                    id="usr_alice",
                    username="alice",
                    password_hash=hasher.hash("correct-password"),
                    role="user",
                    status="active",
                    token_version=1,
                ),
                UserAccount(
                    id="usr_bob",
                    username="bob",
                    password_hash=hasher.hash("bob-password"),
                    role="user",
                    status="active",
                    token_version=1,
                ),
                UserAccount(
                    id="usr_admin",
                    username="admin",
                    password_hash=hasher.hash("admin-password"),
                    role="admin",
                    status="active",
                    token_version=1,
                ),
            ]
        )
        self.auth_audits = _auth_fakes.InMemoryAudit()
        self.resources = _auth_fakes.InMemoryResources()
        tokens = TokenService(secret="m11-pipeline-secret", access_ttl=60, clock=self.clock)
        self.auth = AuthService(
            users=self.users,
            hasher=hasher,
            tokens=tokens,
            refresh_tokens=_auth_fakes.InMemoryRefreshStore(),
            audits=self.auth_audits,
            attempts=_auth_fakes.InMemoryAttempts(),
            access=AccessControl(self.resources),
            clock=self.clock,
            access_ttl=60,
            refresh_ttl=3600,
        )
        self.doc_store = _doc_fakes.MemoryDocuments()
        self.versions = _doc_fakes.MemoryVersions()
        self.chunks = _doc_fakes.MemoryChunks()
        self.tasks = _doc_fakes.MemoryTasks()
        self.doc_objects = _doc_fakes.MemoryObjects()
        self.documents = DocumentService(
            documents=self.doc_store,
            versions=self.versions,
            chunks=self.chunks,
            tasks=self.tasks,
            objects=self.doc_objects,
            audits=_doc_fakes.MemoryAudits(),
        )
        self.runs = RunService()
        self.conversations = ConversationService(runs=self.runs)
        self.export_clock = _export_fakes.FakeClock()
        self.export_repo = InMemoryExportRepository()
        self.export_access = _export_fakes.FakeAccess(self.export_repo)
        self.answers = _export_fakes.FakeAnswerStore()
        self.export_objects = _export_fakes.MemoryObjectStore()
        self.export_audits = AuditService(AppendOnlyAuditStore(), self.export_clock)
        self.exports = ExportService(
            access=self.export_access,
            answers=self.answers,
            exports=self.export_repo,
            objects=self.export_objects,
            audits=self.export_audits,
            clock=self.export_clock,
            signer=PublicDownloadSigner("https://files.pivot.test", "m11-signer"),
            ttl_seconds=3600,
            download_ttl_seconds=300,
        )

    def login_alice(self):
        return self.auth.login("alice", "correct-password", request_id="req_login")

    def ingest_policy_pdf(self, actor_id: str, request_id: str = "req_ingest"):
        version = self.documents.upload(
            filename="handbook.pdf",
            declared_mime="application/pdf",
            content=policy_pdf(),
            title="Attendance Policy",
            actor_id=actor_id,
            request_id=request_id,
        )
        task = self.documents.enqueue(version.id, request_id, actor_id=actor_id)
        self.documents.worker_started(version.id, task.id, request_id)
        sink = DocumentIngestSink(self.documents, request_id)
        worker = IngestWorker(
            parsers=ParserRegistry({"pdf": FixturePdfParser()}),
            sink=sink,
            dimension=8,
        )
        result = worker.run(
            IngestRequest(
                version_id=version.id,
                kind="pdf",
                content=policy_pdf(),
                message_id=f"ingest-{task.id}",
            )
        )
        ready = self.versions.get(version.id)
        document = self.doc_store.get(version.document_id)
        return version, ready, document, result

    def retrieval_for_ready_chunks(self) -> RetrievalService:
        corpus = []
        for chunk in self.chunks._items:
            version = self.versions.get(chunk.version_id)
            document = self.doc_store.get(version.document_id) if version else None
            if version is None or document is None:
                continue
            corpus.append(
                RetrievalChunk(
                    chunk_id=chunk.id,
                    version_id=version.id,
                    document_id=document.id,
                    text=chunk.text,
                    title=document.title,
                    space=document.space,
                    ready=version.state == "ready",
                    current=version.current,
                    allowed=True,
                    expired=False,
                    deleted=document.deleted_at is not None,
                    index_generation="gen_pipeline",
                    embedding_model_version="fake-embed-v1",
                    retrieval_config_version="pipeline-injected",
                )
            )
        records = tuple(corpus)
        policy = RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=4, evidence_limit=4)
        return RetrievalService(
            corpus=records,
            dense=KeywordRetriever(records, "dense"),
            bm25=KeywordRetriever(records, "bm25"),
            policy=policy,
        )

    def ask(
        self,
        *,
        owner_id: str,
        question: str,
        conversation_id: str,
        retrieval: RetrievalService,
    ) -> RunBundle:
        bundle = self.runs.create(
            conversation_id=conversation_id,
            owner_id=owner_id,
            question=question,
            idempotency_key=f"idem-{conversation_id}",
            request_id="req_qa",
        )
        QaOrchestrator(RetrievalBridge(retrieval)).execute(
            bundle,
            self.runs.log(bundle.run.id),
            "req_qa",
        )
        self.resources.conversations[conversation_id] = owner_id
        self.export_access.conversation_owners[conversation_id] = owner_id
        if bundle.run.state in {"answered", "uncertain", "refused"}:
            self.answers.add_answer(persisted_from_run(bundle))
        return bundle

    def alice_actor(self) -> Actor:
        return Actor(user_id="usr_alice", username="alice", role="user")

    def bob_actor(self) -> Actor:
        return Actor(user_id="usr_bob", username="bob", role="user")
