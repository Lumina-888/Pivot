"""S5: claim audit surface for FR-RBAC-004 (ADR-017 D3).

The claim itself writes the claim event; a sync failure writes
authz.library.sync_failed with metadata dept_id set to the claimed-to
library, so the target department's admins see it in their scoped
audit view and unrelated departments do not. A successful sync writes
no extra event: the claim event is the trace.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pivot.audit.ports import Actor
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.ports import Library as _Library
from pivot.auth.ports import Principal, UserAccount
from pivot.documents.ports import DocumentRecord
from pivot.http.memory import (
    InMemoryResources,
    InMemoryUserDirectory,
    MemoryDocuments,
)
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
ENG_ADMIN = Actor(user_id="usr_alice", username="alice", role="user")
ART_ADMIN = Actor(user_id="usr_carol", username="carol", role="user")


class _Clock:
    def __init__(self) -> None:
        self._now = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now


def _service():
    clock = _Clock()
    resources = InMemoryResources()
    resources.libraries = {
        "pub": _Library(id="pub", name="公共库", kind="public"),
        "unassigned": _Library(id="unassigned", name="未分配", kind="system"),
    }
    documents = MemoryDocuments()
    store = AppendOnlyAuditStore()
    audits = AuditService(store, clock)
    users = InMemoryUserDirectory(
        [
            UserAccount(
                id="usr_admin", username="admin", password_hash="hash",
                role="admin", status="active", token_version=1,
            ),
            UserAccount(
                id="usr_alice", username="alice", password_hash="hash",
                role="user", status="active", token_version=1,
            ),
            UserAccount(
                id="usr_carol", username="carol", password_hash="hash",
                role="user", status="active", token_version=1,
            ),
        ]
    )
    service = DepartmentAdminService(
        store=resources,
        documents=documents,
        users=users,
        access=AccessControl(resources, clock=clock),
        audits=audits,
        clock=clock,
    )
    service.create_department(ADMIN, "dept_eng", "技术部", "req_seed_eng")
    service.create_department(ADMIN, "dept_art", "美术部", "req_seed_art")
    service.add_member(ADMIN, "dept_eng", "usr_alice", "dept_admin", "req_seed_a")
    service.add_member(ADMIN, "dept_art", "usr_carol", "dept_admin", "req_seed_c")
    documents.save(
        DocumentRecord(
            id="doc_new", title="新文档", space="shared",
            created_by="usr_admin", library_id="unassigned",
        )
    )
    return service, audits, store


def test_FR_RBAC_004_claim_sync_failed_event_scoped_to_target_dept() -> None:
    service, audits, store = _service()
    claimed = service.claim_document(ADMIN, "doc_new", "dept_eng", "req_claim")
    assert claimed.library_id == "dept_eng"
    # The claim path itself writes no sync_failed event.
    assert store.query(action="authz.library.sync_failed") == ()
    # The task's final-failure record, as the worker would write it.
    audits.record(
        actor="usr_admin",
        action="authz.library.sync_failed",
        target="doc_new",
        result="failed",
        request_id="req_sync",
        metadata={
            "dept_id": "dept_eng",
            "from_library": "unassigned",
            "to_library": "dept_eng",
            "attempts": 4,
        },
    )
    eng_view = audits.list_department_events(
        ENG_ADMIN, frozenset({"dept_eng"}), "req_view_eng"
    )
    eng_actions = [
        (item["action"], item["target"]) for item in eng_view["items"]
    ]
    assert ("authz.library.claim", "doc_new") in eng_actions
    assert ("authz.library.sync_failed", "doc_new") in eng_actions
    art_view = audits.list_department_events(
        ART_ADMIN, frozenset({"dept_art"}), "req_view_art"
    )
    art_actions = [
        (item["action"], item["target"]) for item in art_view["items"]
    ]
    assert ("authz.library.sync_failed", "doc_new") not in art_actions
    assert ("authz.library.claim", "doc_new") not in art_actions
