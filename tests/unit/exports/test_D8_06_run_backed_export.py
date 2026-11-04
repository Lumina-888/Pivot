"""D8-06: export must work on real (PG) assemblies, not only seeded ones.

Phenomenon 1: conversation export always failed, because
ExportService._load_payload requires a PersistedAnswer that production
code never constructs (only tests seed MemoryAnswerStore). Phenomenon
2: document export always 404'd for a super admin on an ingested
document, because MemoryExportAccess used the legacy owner/shared-
visible rule and _LibraryBackedCatalog never proxied get_document.
"""

from __future__ import annotations

import pytest
from pivot.audit.ports import Actor
from pivot.auth.ports import DocumentAuthz, Library, Membership
from pivot.documents.ports import ChunkRecord, DocumentRecord, VersionRecord
from pivot.exports.errors import ExportError
from pivot.exports.repository import InMemoryExportRepository
from pivot.http.memory import (
    InMemoryResources,
    MemoryAnswerStore,
    MemoryChunks,
    MemoryDocuments,
    MemoryExportAccess,
    MemoryVersions,
    RunBackedAnswerStore,
)
from pivot.runs.models import RunBundle, RunRecord
from pivot.security.rbac import AccessControl


class _FakeRuns:
    def __init__(self, bundles: dict[str, tuple[RunBundle, ...]]) -> None:
        self._bundles = bundles

    def list_for_conversation(self, conversation_id: str):
        return self._bundles.get(conversation_id, ())


def _bundle(state: str, answer: str | None) -> RunBundle:
    return RunBundle(
        run=RunRecord(
            id="run_1",
            conversation_id="conv_1",
            message_id="msg_1",
            owner_id="usr_alice",
            question="q",
            idempotency_key="k",
            fingerprint="f",
            state=state,
            answer_markdown=answer,
        ),
        claims=[{"id": "c1", "text": "claim", "citation_ids": ["cit1"], "support": "supported"}],
        citations=[
            {
                "id": "cit1",
                "document_id": "doc_1",
                "version_id": "ver_1",
                "chunk_id": "chk_1",
                "locator": "loc",
                "snippet": "snip",
            }
        ],
    )


def test_D8_06_conversation_export_falls_back_to_persisted_run():
    store = RunBackedAnswerStore(
        MemoryAnswerStore(), runs=_FakeRuns({"conv_1": (_bundle("answered", "final answer"),)})
    )
    answer = store.get_exportable_answer("conv_1")
    assert answer is not None
    assert answer.run_id == "run_1"
    assert answer.state == "answered"
    assert answer.answer_markdown == "final answer"
    assert answer.claims[0].text == "claim"
    assert answer.citations[0].chunk_id == "chk_1"


def test_D8_06_non_exportable_run_stays_failed():
    store = RunBackedAnswerStore(
        MemoryAnswerStore(), runs=_FakeRuns({"conv_1": (_bundle("failed", "boom"),)})
    )
    assert store.get_exportable_answer("conv_1") is None
    assert store.get_exportable_answer("conv_missing") is None


def test_D8_06_document_export_built_from_document_stores():
    documents = MemoryDocuments()
    versions = MemoryVersions()
    chunks = MemoryChunks()
    documents.save(
        DocumentRecord(
            id="doc_1", title="Doc", space="pub", created_by="usr_alice", library_id="pub"
        )
    )
    versions.save(
        VersionRecord(
            id="ver_1", document_id="doc_1", content_sha256="x", storage_key="k",
            state="ready", current=True,
        )
    )
    chunks.add(
        ChunkRecord(id="chk_1", version_id="ver_1", text="hello", text_hash="h")
    )
    chunks.add(
        ChunkRecord(id="chk_2", version_id="ver_1", text="world", text_hash="w")
    )
    store = RunBackedAnswerStore(
        MemoryAnswerStore(), documents=documents, versions=versions, chunks=chunks
    )
    view = store.get_document_export("doc_1")
    assert view is not None
    assert view.title == "Doc"
    assert view.version_id == "ver_1"
    assert view.locators == ("chk_1", "chk_2")
    assert view.display_text == "hello\n\nworld"


def _catalog_with_member() -> InMemoryResources:
    catalog = InMemoryResources()
    catalog.libraries = {
        "dept_eng": Library(id="dept_eng", name="技术部", kind="department", dept_id="dept_eng")
    }
    catalog.documents["doc_1"] = DocumentAuthz(
        id="doc_1", deleted=False, shared_visible=False, export_allowed=False,
        owner_id="usr_alice", library_id="dept_eng",
    )
    catalog.memberships = {
        "usr_bob": (
            Membership(
                user_id="usr_bob", dept_id="dept_eng", dept_role="reader",
                granted_by="usr_admin",
            ),
        ),
    }
    return catalog


def test_D8_06_document_export_uses_rbac_visibility_not_owner_rule():
    catalog = _catalog_with_member()
    access = MemoryExportAccess(
        InMemoryExportRepository(), catalog, access_control=AccessControl(catalog)
    )
    # A super admin who did NOT upload the document: the legacy
    # owner/shared-visible rule 404'd this (D8-06 phenomenon 2).
    admin = Actor(user_id="usr_admin", username="admin", role="admin")
    access.authorize_document(admin, "doc_1", "req_admin")
    # A library member passes through the library channel.
    member = Actor(user_id="usr_bob", username="bob", role="user")
    access.authorize_document(member, "doc_1", "req_member")
    # A non-member still fails closed, without leaking which check failed.
    outsider = Actor(user_id="usr_dave", username="dave", role="user")
    with pytest.raises(ExportError) as error:
        access.authorize_document(outsider, "doc_1", "req_outsider")
    assert error.value.code == "RESOURCE_NOT_FOUND"
