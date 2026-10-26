"""S3: retarget a pending approval request (FR-RBAC-004, ADR-019 D2, O1).

Retarget is proposer-only and pending-only, scope checked before state
like every other decision path (S2 fix): a queue-visible non-proposer
hears forbidden, anyone else hears not_found, whatever the request's
state. The new target passes the same validate_upload_target rule as
an upload-time target. Retargeting re-judges the approver against the
new target, creates no new request, leaves the version pending_approval,
dispatches no ingest, and audits doc.approval.retargeted with the old
and the new target in metadata.
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
        # Frank belongs to both departments, so a department-to-
        # department retarget is exercisable from one proposer.
        "usr_frank": (
            Membership(
                user_id="usr_frank", dept_id="dept_eng", dept_role="editor",
                granted_by="usr_admin",
            ),
            Membership(
                user_id="usr_frank", dept_id="dept_art", dept_role="editor",
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
    return service, resources, documents, versions, audits


def _actions(audits) -> list[dict]:
    return [event.to_info() for event in audits.events()]


def _code(excinfo) -> str:
    return excinfo.value.code


def test_FR_RBAC_004_p1_3_retarget_rejudges_approver() -> None:
    service, _, _, versions, audits = _seed()
    retargeted = service.retarget(PROPOSER, "req_eng", "req_rt", "dept_art")
    assert retargeted.id == "req_eng"
    assert retargeted.status == "pending"
    assert retargeted.target_library_id == "dept_art"
    assert versions.get("ver_eng").state == "pending_approval"
    # The old approver no longer decides; the new one does.
    with pytest.raises(AuthError) as excinfo:
        service.approve(ENG_ADMIN, "req_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    decided = service.approve(ART_ADMIN, "req_eng", "req_ok")
    assert decided.status == "approved"
    events = [e for e in _actions(audits) if e["action"] == "doc.approval.retargeted"]
    assert len(events) == 1
    assert events[0]["metadata"]["old_target_library_id"] == "dept_eng"
    assert events[0]["metadata"]["new_target_library_id"] == "dept_art"
    assert events[0]["metadata"]["target_library_id"] == "dept_art"
    assert events[0]["metadata"]["dept_id"] == "dept_art"
    assert events[0]["actor"] == "usr_frank"


def test_FR_RBAC_004_p1_3_retarget_dispatches_no_ingest() -> None:
    dispatched: list = []

    def _ingest(version_id, request_id, actor_id):
        dispatched.append(version_id)

    service, _, _, versions, _ = _seed(ingest=_ingest)
    service.retarget(PROPOSER, "req_eng", "req_rt", "pub")
    assert dispatched == []
    assert versions.get("ver_eng").state == "pending_approval"


def test_FR_RBAC_004_p1_3_retarget_scope_matrix() -> None:
    service, _, _, _, _ = _seed()
    # A queue-visible non-proposer hears forbidden.
    with pytest.raises(AuthError) as excinfo:
        service.retarget(ENG_ADMIN, "req_eng", "req_no", "dept_art")
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    # An outsider sees nothing.
    with pytest.raises(AuthError) as excinfo:
        service.retarget(OUTSIDER, "req_eng", "req_no", "dept_art")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # Unknown request id.
    with pytest.raises(AuthError) as excinfo:
        service.retarget(PROPOSER, "req_missing", "req_no", "dept_art")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_retarget_decided_is_illegal() -> None:
    service, _, _, _, _ = _seed()
    service.approve(ENG_ADMIN, "req_eng", "req_ok")
    # Scope still precedes state: the proposer hears illegal state
    # (she passed the proposer check), not a scope error.
    with pytest.raises(DocumentError) as excinfo:
        service.retarget(PROPOSER, "req_eng", "req_no", "dept_art")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"


def test_FR_RBAC_004_p1_3_retarget_target_validation() -> None:
    service, _, _, _, _ = _seed()
    # Invisible targets read as not_found: cross-project for a
    # non-member, missing, system, and unknown-kind alike.
    for target in ("proj_x", "missing", "unassigned"):
        with pytest.raises(AuthError) as excinfo:
            service.retarget(PROPOSER, "req_eng", "req_no", target)
        assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # A project member retargeting into the public library works,
    # and the old project lead loses the decision.
    retargeted = service.retarget(PX_PROPOSER, "req_px", "req_rt", "pub")
    assert retargeted.target_library_id == "pub"
    with pytest.raises(AuthError) as excinfo:
        service.approve(LEAD, "req_px", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    decided = service.approve(ADMIN, "req_px", "req_ok")
    assert decided.status == "approved"
