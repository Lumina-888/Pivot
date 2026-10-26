"""S5: claim interlock and exception gate for FR-RBAC-004 (ADR-019 D4).

Single channel: a document with a pending publish or move request is
claimed only through its queue, never through claim — for every
claimant including the super admin. Claim lands the document in the
target library's default folder (S4 O7 parity). Exceptions may not
target a pending-approval document.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fakes import FakeClock
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.approvals import ApprovalService
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.errors import AuthError
from pivot.auth.moves import MoveService
from pivot.auth.ports import (
    ApprovalRequest,
    Library,
    Membership,
    MoveRequest,
    Principal,
    UserAccount,
)
from pivot.documents.ports import DocumentRecord, VersionRecord
from pivot.http.memory import (
    InMemoryResources,
    InMemoryUserDirectory,
    MemoryDocuments,
    MemoryVersions,
)
from pivot.security.rbac import AccessControl
from tests.unit.documents.fakes import MemoryObjects

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
ENG_ADMIN = Principal(user_id="usr_alice", username="alice", role="user", token_version=1)
ART_ADMIN = Principal(user_id="usr_carol", username="carol", role="user", token_version=1)
LEAD = Principal(user_id="usr_bob", username="bob", role="user", token_version=1)
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
        "dept_art": Library(
            id="dept_art", name="美术部", kind="department", dept_id="dept_art"
        ),
        "proj_x": Library(
            id="proj_x", name="跨部门项目", kind="project", dept_id="dept_eng"
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
        "usr_carol": (
            Membership(
                user_id="usr_carol", dept_id="dept_art", dept_role="dept_admin",
                granted_by="usr_admin",
            ),
        ),
        "usr_bob": (
            Membership(
                user_id="usr_bob", dept_id="proj_x", dept_role="project_lead",
                granted_by="usr_alice",
            ),
        ),
        "usr_frank": (
            Membership(
                user_id="usr_frank", dept_id="dept_eng", dept_role="editor",
                granted_by="usr_admin",
            ),
        ),
    }
    users = InMemoryUserDirectory(
        [
            UserAccount(
                id=user_id, username=username, password_hash="x",
                role=role, status="active", token_version=1,
            )
            for user_id, username, role in (
                ("usr_admin", "admin", "admin"),
                ("usr_alice", "alice", "user"),
                ("usr_carol", "carol", "user"),
                ("usr_bob", "bob", "user"),
                ("usr_frank", "frank", "user"),
                ("usr_ghost", "ghost", "user"),
            )
        ]
    )
    documents = MemoryDocuments()
    versions = MemoryVersions()
    for doc_id, library_id, folder_id in (
        ("doc_free", "unassigned", None),
        ("doc_pending", "unassigned", None),
        ("doc_stale_folder", "unassigned", "fld_stale"),
        ("doc_stale_pin", "unassigned", "fld_stale"),
        ("doc_pub", "dept_eng", None),
    ):
        documents.save(
            DocumentRecord(
                id=doc_id, title=doc_id, space="shared",
                created_by="usr_frank", library_id=library_id,
                folder_id=folder_id,
            )
        )
    versions.save(
        VersionRecord(
            id="ver_pending", document_id="doc_pending",
            content_sha256="sha", storage_key="quarantine/doc_pending/ver_pending",
            state="pending_approval",
        )
    )
    resources.approval_requests = {
        "req_pending": ApprovalRequest(
            id="req_pending", document_id="doc_pending",
            version_id="ver_pending", target_library_id="dept_eng",
            proposer="usr_frank", status="pending", created_at=T0,
        ),
    }
    # A move request seeded directly onto an unassigned document:
    # propose() can never produce this shape (it requires a published
    # document), but the claim check must still refuse it — the
    # defense-in-depth layer, not the library check.
    resources.move_requests = {
        "mv_stale": MoveRequest(
            id="mv_stale", document_id="doc_stale_folder",
            source_library_id="dept_eng", target_library_id="dept_art",
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
    departments = DepartmentAdminService(
        store=resources,
        documents=documents,
        users=users,
        access=access,
        audits=audits,
        clock=clock,
    )
    departments.bind_pending_request_checks(
        pending_approval_for=approvals.pending_request_for,
        pending_move_for=moves.pending_request_for,
    )
    return departments, approvals, moves, documents, audits


def _actions(audits) -> list[dict]:
    return [event.to_info() for event in audits.events()]


def _code(excinfo) -> str:
    return excinfo.value.code


def test_FR_RBAC_004_p1_3_claim_refuses_pending_approval_for_all_claimants() -> None:
    departments, _, _, documents, _ = _seed()
    # The target department's own admin is refused: the single channel
    # admits no self-approval shortcut through claim.
    with pytest.raises(AuthError) as excinfo:
        departments.claim_document(ENG_ADMIN, "doc_pending", "dept_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    # The super-admin fast lane covers ordinary unassigned documents
    # only, not pending ones.
    with pytest.raises(AuthError) as excinfo:
        departments.claim_document(ADMIN, "doc_pending", "dept_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    assert documents.get("doc_pending").library_id == "unassigned"


def test_FR_RBAC_004_p1_3_claim_refuses_pending_move_even_when_unassigned() -> None:
    departments, _, _, documents, _ = _seed()
    with pytest.raises(AuthError) as excinfo:
        departments.claim_document(ART_ADMIN, "doc_stale_folder", "dept_art", "req_no")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    assert documents.get("doc_stale_folder").library_id == "unassigned"


def test_FR_RBAC_004_p1_3_claim_fast_lane_and_default_folder() -> None:
    departments, _, _, documents, audits = _seed()
    claimed = departments.claim_document(ENG_ADMIN, "doc_free", "dept_eng", "req_ok")
    assert claimed.library_id == "dept_eng"
    assert claimed.folder_id is None
    events = [
        event for event in _actions(audits)
        if event["action"] == "authz.library.claim"
    ]
    assert len(events) == 1
    assert events[0]["metadata"]["to_library"] == "dept_eng"
    # A stale folder on an unassigned document does not survive the
    # claim: the claim pins the target library's default folder.
    claimed = departments.claim_document(ADMIN, "doc_stale_pin", "dept_art", "req_ok2")
    assert claimed.library_id == "dept_art"
    assert claimed.folder_id is None


def test_FR_RBAC_004_p1_3_claim_allowed_after_request_decided() -> None:
    departments, approvals, _, documents, _ = _seed()
    approvals.withdraw(EDITOR, "req_pending", "req_wd")
    claimed = departments.claim_document(ENG_ADMIN, "doc_pending", "dept_eng", "req_ok")
    assert claimed.library_id == "dept_eng"


def test_FR_RBAC_004_p1_3_exception_gate_pending_approval() -> None:
    departments, approvals, _, _, _ = _seed()
    # Scope first: an admin of another department hears not_found,
    # never the pending state — and so does the target department's
    # own admin, because a pending document still sits in
    # "unassigned", which has no owning department to manage it.
    # The gate itself is what stops the super admin, who passes scope.
    with pytest.raises(AuthError) as excinfo:
        departments.grant_exception(
            ART_ADMIN, "doc_pending", "req_no", target_user_id="usr_ghost"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        departments.grant_exception(
            ENG_ADMIN, "doc_pending", "req_no", target_user_id="usr_ghost"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        departments.grant_exception(
            ADMIN, "doc_pending", "req_no", target_user_id="usr_ghost"
        )
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    # Once the request is decided, the gate lifts: approve moves the
    # document into dept_eng, and the owning admin may grant.
    approvals.approve(ENG_ADMIN, "req_pending", "req_ap")
    exception, created = departments.grant_exception(
        ENG_ADMIN, "doc_pending", "req_ok", target_user_id="usr_ghost"
    )
    assert created is True
    assert exception.document_id == "doc_pending"
