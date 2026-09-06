"""In-memory fakes for M06 unit tests. Not a production fact store."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from pivot.audit.ports import Actor
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.exports.errors import not_found, resource_forbidden
from pivot.exports.models import (
    CitationView,
    ClaimView,
    DocumentExportView,
    PersistedAnswer,
)
from pivot.exports.repository import InMemoryExportRepository
from pivot.exports.service import ExportService
from pivot.exports.signer import PublicDownloadSigner


class FakeClock:
    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 9, 6, 8, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: int) -> None:
        self._now = self._now + timedelta(seconds=seconds)


class FakeAccess:
    def __init__(self, export_store: InMemoryExportRepository) -> None:
        self._exports = export_store
        self.conversation_owners: dict[str, str] = {}
        self.documents: dict[str, dict] = {}
        self.calls: list[tuple[str, str, str]] = []

    def authorize_conversation(self, actor: Actor, conversation_id: str, request_id: str) -> None:
        self.calls.append(("conversation", conversation_id, actor.user_id))
        owner = self.conversation_owners.get(conversation_id)
        if owner is None:
            raise not_found(request_id)
        if owner == actor.user_id:
            return
        if actor.role == "admin":
            raise resource_forbidden(request_id)
        raise not_found(request_id)

    def authorize_document(self, actor: Actor, document_id: str, request_id: str) -> None:
        self.calls.append(("document", document_id, actor.user_id))
        document = self.documents.get(document_id)
        if document is None or document.get("deleted"):
            raise not_found(request_id)
        if document.get("shared_visible") or document.get("owner_id") == actor.user_id:
            return
        raise not_found(request_id)

    def authorize_export(self, actor: Actor, export_id: str, request_id: str) -> None:
        self.calls.append(("export", export_id, actor.user_id))
        record = self._exports.get(export_id)
        if record is None:
            raise not_found(request_id)
        if record.owner_id == actor.user_id:
            return
        if actor.role == "admin":
            raise resource_forbidden(request_id)
        raise not_found(request_id)


class FakeAnswerStore:
    def __init__(self) -> None:
        self.answers: dict[str, PersistedAnswer] = {}
        self.documents: dict[str, DocumentExportView] = {}
        self.qa_invocations = 0
        self.reads = 0

    def add_answer(self, answer: PersistedAnswer) -> None:
        self.answers[answer.conversation_id] = answer

    def add_document(self, document: DocumentExportView) -> None:
        self.documents[document.document_id] = document

    def get_exportable_answer(self, conversation_id: str) -> PersistedAnswer | None:
        self.reads += 1
        return self.answers.get(conversation_id)

    def get_document_export(self, document_id: str) -> DocumentExportView | None:
        self.reads += 1
        return self.documents.get(document_id)

    def rerun_qa(self, conversation_id: str) -> None:
        self.qa_invocations += 1


class MemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.presign_calls: list[tuple[str, int]] = []

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        self.objects[key] = data

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def presign(self, key: str, *, expires_seconds: int) -> str:
        self.presign_calls.append((key, expires_seconds))
        return f"http://minio:9000/exports/{key}?X-Amz-Expires={expires_seconds}"


def sample_answer(
    conversation_id: str = "conv_alice",
    title: str = "迟到处理规则",
) -> PersistedAnswer:
    return PersistedAnswer(
        conversation_id=conversation_id,
        run_id="run_alice_1",
        state="answered",
        answer_markdown="迟到三次书面警告。",
        title=title,
        claims=(
            ClaimView(
                id="clm_1",
                text="迟到三次书面警告",
                support="supported",
                citation_ids=("cit_1",),
            ),
        ),
        citations=(
            CitationView(
                id="cit_1",
                document_id="doc_shared",
                version_id="ver_1",
                chunk_id="chk_1",
                locator="员工手册 p.12",
                snippet="迟到累计三次给予书面警告。",
            ),
        ),
        prompt="SYSTEM_PROMPT: you are an internal debugger",
        chain_of_thought="chain-of-thought: retrieve hidden tool args",
        tool_parameters={"tool": "search", "api_key": "sk-secret-export"},
    )


ALICE = Actor(user_id="usr_alice", username="alice", role="user")
BOB = Actor(user_id="usr_bob", username="bob", role="user")
ADMIN = Actor(user_id="usr_admin", username="admin", role="admin")


@dataclass
class ExportHarness:
    clock: FakeClock
    access: FakeAccess
    answers: FakeAnswerStore
    exports: InMemoryExportRepository
    objects: MemoryObjectStore
    audits: AuditService
    service: ExportService
    alice: Actor = field(default_factory=lambda: ALICE)
    bob: Actor = field(default_factory=lambda: BOB)
    admin: Actor = field(default_factory=lambda: ADMIN)


def build_harness(ttl_seconds: int = 3600) -> ExportHarness:
    clock = FakeClock()
    exports = InMemoryExportRepository()
    access = FakeAccess(exports)
    access.conversation_owners["conv_alice"] = ALICE.user_id
    access.conversation_owners["conv_bob"] = BOB.user_id
    access.documents["doc_shared"] = {
        "deleted": False,
        "shared_visible": True,
        "owner_id": "usr_system",
        "export_allowed": True,
    }
    access.documents["doc_secret"] = {
        "deleted": False,
        "shared_visible": False,
        "owner_id": "usr_other",
        "export_allowed": False,
    }
    answers = FakeAnswerStore()
    answers.add_answer(sample_answer())
    answers.add_document(
        DocumentExportView(
            document_id="doc_shared",
            title="员工手册",
            version_id="ver_1",
            locators=("p.12",),
            display_text="迟到累计三次给予书面警告。",
        )
    )
    objects = MemoryObjectStore()
    audits = AuditService(AppendOnlyAuditStore(), clock)
    service = ExportService(
        access=access,
        answers=answers,
        exports=exports,
        objects=objects,
        audits=audits,
        clock=clock,
        signer=PublicDownloadSigner("https://files.pivot.test", "test-signer"),
        ttl_seconds=ttl_seconds,
        download_ttl_seconds=300,
    )
    return ExportHarness(
        clock=clock,
        access=access,
        answers=answers,
        exports=exports,
        objects=objects,
        audits=audits,
        service=service,
    )
