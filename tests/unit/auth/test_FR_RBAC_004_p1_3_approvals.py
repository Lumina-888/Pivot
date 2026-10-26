"""S2: publish-approval service for FR-RBAC-004 (ADR-019 D1, D6).

Approval decisions by target library kind (department -> dept
admins, public -> super admins, project -> project leads), delegated
actions by super admins on department/project queues (O2), proposer
only withdraw/resubmit, dedicated review read, and the approve order
(close request, rewrite library, transition version, then dispatch
ingest) that S3's self-approval fast path reuses unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fakes import FakeClock
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.approvals import ApprovalService
from pivot.auth.errors import AuthError
from pivot.auth.ports import (
    ApprovalRequest,
    Library,
    Membership,
    Principal,
)
from pivot.documents.errors import DocumentError
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
ART_ADMIN = Principal(user_id="usr_carol", username="carol", role="user", token_version=1)
LEAD = Principal(user_id="usr_bob", username="bob", role="user", token_version=1)
PROPOSER = Principal(user_id="usr_frank", username="frank", role="user", token_version=1)
PX_PROPOSER = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
OUTSIDER = Principal(user_id="usr_ghost", username="ghost", role="user", token_version=1)

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


def _seed(*, ingest=None):
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
        "usr_dave": (
            Membership(
                user_id="usr_dave", dept_id="proj_x", dept_role="editor",
                granted_by="usr_bob",
            ),
        ),
    }
    documents = MemoryDocuments()
    versions = MemoryVersions()
    objects = MemoryObjects()
    for doc_id, version_id in (
        ("doc_eng", "ver_eng"),
        ("doc_pub", "ver_pub"),
        ("doc_px", "ver_px"),
    ):
        documents.save(
            DocumentRecord(
                id=doc_id, title=doc_id, space="shared",
                created_by="usr_frank", library_id="unassigned",
            )
        )
        versions.save(
            VersionRecord(
                id=version_id, document_id=doc_id, content_sha256="sha",
                storage_key=f"quarantine/{doc_id}/{version_id}",
                state="pending_approval",
            )
        )
        objects.put(f"quarantine/{doc_id}/{version_id}", b"original-" + doc_id.encode())
    resources.approval_requests = {
        "req_eng": ApprovalRequest(
            id="req_eng", document_id="doc_eng", version_id="ver_eng",
            target_library_id="dept_eng", proposer="usr_frank",
            status="pending", created_at=T0,
        ),
        "req_pub": ApprovalRequest(
            id="req_pub", document_id="doc_pub", version_id="ver_pub",
            target_library_id="pub", proposer="usr_frank",
            status="pending", created_at=T0,
        ),
        "req_px": ApprovalRequest(
            id="req_px", document_id="doc_px", version_id="ver_px",
            target_library_id="proj_x", proposer="usr_dave",
            status="pending", created_at=T0,
        ),
    }
    audits = AuditService(AppendOnlyAuditStore(), clock)
    service = ApprovalService(
        store=resources,
        documents=documents,
        versions=versions,
        objects=objects,
        access=AccessControl(resources, clock=clock),
        audits=audits,
        clock=clock,
        ingest=ingest,
    )
    return service, resources, documents, versions, objects, audits


def _actions(audits) -> list[dict]:
    return [event.to_info() for event in audits.events()]


def _code(excinfo) -> str:
    return excinfo.value.code


def test_FR_RBAC_004_p1_3_approve_by_department_admin() -> None:
    dispatched: list = []
    service, _, documents, versions, _, audits = _seed(
        ingest=lambda vid, rid, actor: dispatched.append((vid, actor))
    )
    decided = service.approve(ENG_ADMIN, "req_eng", "req_approve")
    assert decided.status == "approved"
    assert decided.decided_by == "usr_alice"
    assert documents.get("doc_eng").library_id == "dept_eng"
    assert versions.get("ver_eng").state == "uploaded"
    # Ingest dispatched after the library rewrite, by the approver.
    assert dispatched == [("ver_eng", "usr_alice")]
    actions = _actions(audits)
    approved = [e for e in actions if e["action"] == "authz.approval.approved"]
    assert len(approved) == 1
    assert approved[0]["metadata"]["dept_id"] == "dept_eng"
    assert approved[0]["metadata"]["project_id"] is None
    assert approved[0]["actor"] == "usr_alice"
    assert not [e for e in actions if e["action"] == "authz.approval.delegated"]


def test_FR_RBAC_004_p1_3_approve_public_by_super_admin_is_ordinary() -> None:
    service, _, documents, versions, _, audits = _seed()
    service.approve(ADMIN, "req_pub", "req_approve")
    assert documents.get("doc_pub").library_id == "pub"
    assert versions.get("ver_pub").state == "uploaded"
    actions = _actions(audits)
    assert len([e for e in actions if e["action"] == "authz.approval.approved"]) == 1
    # O2: the public queue already belongs to super admins, so this
    # is an ordinary approval, not a delegation.
    assert not [e for e in actions if e["action"] == "authz.approval.delegated"]


def test_FR_RBAC_004_p1_3_approve_department_by_super_admin_is_delegated() -> None:
    service, _, documents, _, _, audits = _seed()
    service.approve(ADMIN, "req_eng", "req_approve")
    assert documents.get("doc_eng").library_id == "dept_eng"
    actions = _actions(audits)
    assert len([e for e in actions if e["action"] == "authz.approval.approved"]) == 1
    delegated = [e for e in actions if e["action"] == "authz.approval.delegated"]
    assert len(delegated) == 1
    assert delegated[0]["actor"] == "usr_admin"
    assert delegated[0]["metadata"]["dept_id"] == "dept_eng"


def test_FR_RBAC_004_p1_3_approve_project_by_lead() -> None:
    service, _, documents, versions, _, audits = _seed()
    service.approve(LEAD, "req_px", "req_approve")
    assert documents.get("doc_px").library_id == "proj_x"
    assert versions.get("ver_px").state == "uploaded"
    approved = [
        e for e in _actions(audits) if e["action"] == "authz.approval.approved"
    ]
    assert approved[0]["metadata"]["dept_id"] == "dept_eng"
    assert approved[0]["metadata"]["project_id"] == "proj_x"


def test_FR_RBAC_004_p1_3_approve_scope_matrix() -> None:
    service, _, _, _, _, _ = _seed()
    # Other department's admin: the request does not exist for them.
    with pytest.raises(AuthError) as excinfo:
        service.approve(ART_ADMIN, "req_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # The proposer knows the request exists but cannot decide it.
    with pytest.raises(AuthError) as excinfo:
        service.approve(PROPOSER, "req_eng", "req_no")
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    # A project lead holds no power over a department queue.
    with pytest.raises(AuthError) as excinfo:
        service.approve(LEAD, "req_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # An outsider sees nothing.
    with pytest.raises(AuthError) as excinfo:
        service.approve(OUTSIDER, "req_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # Unknown request id.
    with pytest.raises(AuthError) as excinfo:
        service.approve(ENG_ADMIN, "req_missing", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_approve_non_pending_is_illegal() -> None:
    service, _, _, _, _, _ = _seed()
    service.reject(ENG_ADMIN, "req_eng", "req_reject")
    with pytest.raises(DocumentError) as excinfo:
        service.approve(ENG_ADMIN, "req_eng", "req_again")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"


def test_FR_RBAC_004_p1_3_approve_non_unassigned_document_is_illegal() -> None:
    service, _, documents, _, _, _ = _seed()
    # Inconsistent seed: a pending request whose document already
    # left unassigned must not publish into the wrong scope.
    doc = documents.get("doc_eng")
    doc.library_id = "dept_art"
    documents.save(doc)
    with pytest.raises(DocumentError) as excinfo:
        service.approve(ENG_ADMIN, "req_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"


def test_FR_RBAC_004_p1_3_ingest_failure_does_not_roll_back_decision() -> None:
    def _boom(version_id, request_id, actor_id):
        raise RuntimeError("dispatch down")

    service, _, documents, versions, _, _ = _seed(ingest=_boom)
    with pytest.raises(RuntimeError):
        service.approve(ENG_ADMIN, "req_eng", "req_approve")
    # The decision stands (mirrors the upload route); the version
    # sits in uploaded for the existing retry path.
    assert documents.get("doc_eng").library_id == "dept_eng"
    assert versions.get("ver_eng").state == "uploaded"


def test_FR_RBAC_004_p1_3_reject_keeps_document_unassigned() -> None:
    dispatched: list = []
    service, _, documents, versions, _, audits = _seed(
        ingest=lambda vid, rid, actor: dispatched.append(vid)
    )
    decided = service.reject(ENG_ADMIN, "req_eng", "req_reject", reason="太敏感")
    assert decided.status == "rejected"
    assert decided.reason == "太敏感"
    assert documents.get("doc_eng").library_id == "unassigned"
    assert versions.get("ver_eng").state == "rejected"
    assert dispatched == []
    rejected = [
        e for e in _actions(audits) if e["action"] == "authz.approval.rejected"
    ]
    assert len(rejected) == 1
    assert rejected[0]["metadata"]["dept_id"] == "dept_eng"


def test_FR_RBAC_004_p1_3_reject_reason_optional_and_delegated() -> None:
    service, _, _, versions, _, audits = _seed()
    decided = service.reject(ADMIN, "req_eng", "req_reject")
    assert decided.reason == ""
    assert versions.get("ver_eng").state == "rejected"
    actions = _actions(audits)
    assert len([e for e in actions if e["action"] == "authz.approval.rejected"]) == 1
    assert len([e for e in actions if e["action"] == "authz.approval.delegated"]) == 1


def test_FR_RBAC_004_p1_3_withdraw_by_proposer_dispatches_ingest() -> None:
    dispatched: list = []
    service, _, _, versions, _, audits = _seed(
        ingest=lambda vid, rid, actor: dispatched.append((vid, actor))
    )
    withdrawn = service.withdraw(PROPOSER, "req_eng", "req_withdraw")
    assert withdrawn.status == "withdrawn"
    assert versions.get("ver_eng").state == "uploaded"
    # O3: withdraw triggers ingest, so the version proceeds through
    # the normal pipeline instead of stalling in uploaded.
    assert dispatched == [("ver_eng", "usr_frank")]
    withdrawn_events = [
        e for e in _actions(audits) if e["action"] == "doc.approval.withdrawn"
    ]
    assert len(withdrawn_events) == 1


def test_FR_RBAC_004_p1_3_withdraw_scope_matrix() -> None:
    service, _, _, _, _, _ = _seed()
    # A queue-visible approver still cannot withdraw someone else's
    # request: withdraw belongs to the proposer alone.
    with pytest.raises(AuthError) as excinfo:
        service.withdraw(ENG_ADMIN, "req_eng", "req_no")
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    # An outsider sees nothing.
    with pytest.raises(AuthError) as excinfo:
        service.withdraw(OUTSIDER, "req_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_resubmit_rejected_with_new_target() -> None:
    service, resources, _, versions, _, audits = _seed()
    service.reject(ENG_ADMIN, "req_eng", "req_reject", reason="换个库")
    reopened = service.resubmit(
        PROPOSER, "req_eng", "req_resubmit", target_library_id="dept_art"
    )
    assert reopened.status == "pending"
    assert reopened.target_library_id == "dept_art"
    assert reopened.reason == ""
    assert reopened.decided_by is None
    assert versions.get("ver_eng").state == "pending_approval"
    # The new target re-scopes the approver: the art admin can now
    # decide, the eng admin can no longer.
    service.approve(ART_ADMIN, "req_eng", "req_approve2")
    requested = [
        e for e in _actions(audits) if e["action"] == "doc.approval.requested"
    ]
    assert len(requested) == 1


def test_FR_RBAC_004_p1_3_resubmit_scope_and_state() -> None:
    service, _, _, _, _, _ = _seed()
    # Pending requests cannot be resubmitted.
    with pytest.raises(DocumentError) as excinfo:
        service.resubmit(PROPOSER, "req_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    service.reject(ENG_ADMIN, "req_eng", "req_reject")
    # Only the proposer resubmits, even a queue-visible approver.
    with pytest.raises(AuthError) as excinfo:
        service.resubmit(ENG_ADMIN, "req_eng", "req_no")
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    # Retargeting to a missing library is not_found, not a new queue.
    with pytest.raises(AuthError) as excinfo:
        service.resubmit(PROPOSER, "req_eng", "req_no", target_library_id="dept_nope")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_queue_scope_matrix() -> None:
    service, _, _, _, _, _ = _seed()
    assert {r.id for r in service.list_pending(ADMIN)} == {
        "req_eng", "req_pub", "req_px"
    }
    # Eng admin: own department target plus the project target their
    # department owns (visibility, not decision power).
    assert {r.id for r in service.list_pending(ENG_ADMIN)} == {
        "req_eng", "req_px"
    }
    assert {r.id for r in service.list_pending(LEAD)} == {"req_px"}
    # Proposers see their own submissions.
    assert {r.id for r in service.list_pending(PROPOSER)} == {
        "req_eng", "req_pub"
    }
    assert {r.id for r in service.list_pending(ART_ADMIN)} == set()
    assert {r.id for r in service.list_pending(OUTSIDER)} == set()
    # Decided requests leave the queue but stay visible to proposer
    # and approver via get_request.
    service.approve(ENG_ADMIN, "req_eng", "req_approve")
    assert {r.id for r in service.list_pending(ENG_ADMIN)} == {"req_px"}
    assert service.get_request(PROPOSER, "req_eng", "req_get").status == "approved"
    with pytest.raises(AuthError) as excinfo:
        service.get_request(OUTSIDER, "req_eng", "req_get")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_review_read_matrix() -> None:
    service, _, _, _, _, audits = _seed()
    payload = service.review_read(PROPOSER, "req_eng", "req_review")
    assert payload.body == b"original-doc_eng"
    payload = service.review_read(ENG_ADMIN, "req_eng", "req_review2")
    assert payload.body == b"original-doc_eng"
    payload = service.review_read(ADMIN, "req_eng", "req_review3")
    assert payload.body == b"original-doc_eng"
    # A non-approver member sees nothing, even a project member
    # reaching for a department queue.
    with pytest.raises(AuthError) as excinfo:
        service.review_read(PX_PROPOSER, "req_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.review_read(OUTSIDER, "req_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    reviews = [
        e for e in _actions(audits) if e["action"] == "doc.approval.review"
    ]
    assert len(reviews) == 3
    assert all(e["metadata"]["dept_id"] == "dept_eng" for e in reviews)


def test_FR_RBAC_004_p1_3_review_read_decided_is_illegal() -> None:
    service, _, _, _, _, _ = _seed()
    service.approve(ENG_ADMIN, "req_eng", "req_approve")
    # Once decided, the normal preview/download paths own the
    # document again; the dedicated review path closes.
    with pytest.raises(DocumentError) as excinfo:
        service.review_read(PROPOSER, "req_eng", "req_review")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
