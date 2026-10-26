"""S5: delete-cancel for FR-RBAC-004 (ADR-019 D4, decided O4).

Deleting (tombstone) closes the document's pending publish and move
requests as cancelled with audit events, leaves version states
untouched, and never touches decided requests. The S1 status CHECK
already admits 'cancelled' for both tables, so no migration is needed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fakes import FakeClock
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.approvals import ApprovalService
from pivot.auth.moves import MoveService
from pivot.auth.ports import (
    ApprovalRequest,
    Library,
    Membership,
    MoveRequest,
    Principal,
)
from pivot.documents.ports import DocumentRecord, VersionRecord
from pivot.http.memory import (
    InMemoryResources,
    MemoryDocuments,
    MemoryVersions,
)
from pivot.security.rbac import AccessControl
from tests.unit.documents.fakes import MemoryObjects

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
ENG_ADMIN = Principal(user_id="usr_alice", username="alice", role="user", token_version=1)
EDITOR = Principal(user_id="usr_frank", username="frank", role="user", token_version=1)

T0 = datetime(2026, 10, 26, 8, 0, tzinfo=UTC)


def _seed():
    clock = FakeClock(T0)
    resources = InMemoryResources()
    resources.libraries = {
        "pub": Library(id="pub", name="公共库", kind="public"),
        "dept_eng": Library(
            id="dept_eng", name="技术部", kind="department", dept_id="dept_eng"
        ),
        "unassigned": Library(id="unassigned", name="未分配", kind="system"),
    }
    resources.memberships = {
        "usr_alice": (
            Membership(
                user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
                granted_by="usr_admin",
            ),
        ),
        "usr_frank": (
            Membership(
                user_id="usr_frank", dept_id="dept_eng", dept_role="editor",
                granted_by="usr_admin",
            ),
        ),
    }
    documents = MemoryDocuments()
    versions = MemoryVersions()
    for doc_id, version_id, state, library_id in (
        ("doc_pending", "ver_pending", "pending_approval", "unassigned"),
        ("doc_moving", "ver_moving", "ready", "dept_eng"),
        ("doc_decided", "ver_decided", "uploaded", "dept_eng"),
        ("doc_free", "ver_free", "uploaded", "unassigned"),
    ):
        documents.save(
            DocumentRecord(
                id=doc_id, title=doc_id, space="shared",
                created_by="usr_frank", library_id=library_id,
            )
        )
        versions.save(
            VersionRecord(
                id=version_id, document_id=doc_id, content_sha256="sha",
                storage_key=f"quarantine/{doc_id}/{version_id}",
                state=state,
            )
        )
    resources.approval_requests = {
        "req_pending": ApprovalRequest(
            id="req_pending", document_id="doc_pending",
            version_id="ver_pending", target_library_id="dept_eng",
            proposer="usr_frank", status="pending", created_at=T0,
        ),
        "req_decided": ApprovalRequest(
            id="req_decided", document_id="doc_decided",
            version_id="ver_decided", target_library_id="dept_eng",
            proposer="usr_frank", status="approved", created_at=T0,
            decided_at=T0, decided_by="usr_alice",
        ),
    }
    resources.move_requests = {
        "mv_pending": MoveRequest(
            id="mv_pending", document_id="doc_moving",
            source_library_id="dept_eng", target_library_id="pub",
            proposer="usr_alice", status="pending", created_at=T0,
        ),
    }
    audits = AuditService(AppendOnlyAuditStore(), clock)
    access = AccessControl(resources, clock=clock)
    approvals = ApprovalService(
        store=resources,
        documents=documents,
        versions=versions,
        objects=MemoryObjects(),
        access=access,
        audits=audits,
        clock=clock,
    )
    moves = MoveService(
        store=resources,
        documents=documents,
        access=access,
        audits=audits,
        clock=clock,
        approvals=approvals,
    )
    return approvals, moves, resources, audits


def _actions(audits) -> list[dict]:
    return [event.to_info() for event in audits.events()]


def _of(actions, action: str) -> list[dict]:
    return [event for event in actions if event["action"] == action]


def test_FR_RBAC_004_p1_3_delete_cancels_pending_approval() -> None:
    approvals, _, resources, audits = _seed()
    cancelled = approvals.cancel_pending_for_document(
        "doc_pending", "usr_admin", "req_del"
    )
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert cancelled.decided_by == "usr_admin"
    assert resources.approval_requests["req_pending"].status == "cancelled"
    events = _of(_actions(audits), "doc.approval.cancelled")
    assert len(events) == 1
    assert events[0]["actor"] == "usr_admin"
    assert events[0]["metadata"]["document_id"] == "doc_pending"
    assert events[0]["metadata"]["target_library_id"] == "dept_eng"
    assert events[0]["metadata"]["dept_id"] == "dept_eng"
    # Second call is a no-op: nothing pending anymore.
    assert approvals.cancel_pending_for_document(
        "doc_pending", "usr_admin", "req_del2"
    ) is None


def test_FR_RBAC_004_p1_3_delete_cancels_pending_move() -> None:
    _, moves, resources, audits = _seed()
    cancelled = moves.cancel_pending_for_document(
        "doc_moving", "usr_admin", "req_del"
    )
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert resources.move_requests["mv_pending"].status == "cancelled"
    events = _of(_actions(audits), "doc.move.cancelled")
    assert len(events) == 1
    assert events[0]["metadata"]["document_id"] == "doc_moving"
    assert events[0]["metadata"]["source_library_id"] == "dept_eng"
    assert events[0]["metadata"]["target_library_id"] == "pub"
    assert events[0]["metadata"]["dept_id"] == "pub"


def test_FR_RBAC_004_p1_3_delete_cancel_leaves_decided_requests_alone() -> None:
    approvals, moves, resources, audits = _seed()
    assert approvals.cancel_pending_for_document(
        "doc_decided", "usr_admin", "req_del"
    ) is None
    assert moves.cancel_pending_for_document(
        "doc_decided", "usr_admin", "req_del"
    ) is None
    assert resources.approval_requests["req_decided"].status == "approved"
    assert _of(_actions(audits), "doc.approval.cancelled") == []
    assert _of(_actions(audits), "doc.move.cancelled") == []


def test_FR_RBAC_004_p1_3_delete_cancel_tolerates_missing_target_library() -> None:
    approvals, _, resources, audits = _seed()
    # The target library was removed while the request pended: the
    # cancellation must still close the dead request, not fail.
    del resources.libraries["dept_eng"]
    cancelled = approvals.cancel_pending_for_document(
        "doc_pending", "usr_admin", "req_del"
    )
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert len(_of(_actions(audits), "doc.approval.cancelled")) == 1
