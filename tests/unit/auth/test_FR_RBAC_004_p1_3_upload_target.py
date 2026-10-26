"""S3: upload-with-target validation and request creation (FR-RBAC-004,
ADR-019 D1/D2).

Target validation is fail-closed: invisible, system-kind, and unknown-kind
targets all read as not_found; department targets need a live membership
in that department; project targets need a live membership in that
project (an owning-department admin who never joined is NOT a member,
per D2's letter); public targets take any uploader (Q1). The
self-approval check reuses the queue decision rule via is_approver,
never a second standard.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fakes import FakeClock
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.approvals import ApprovalService
from pivot.auth.errors import AuthError
from pivot.auth.ports import Library, Membership, Principal
from pivot.documents.errors import DocumentError
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
ENG_EDITOR = Principal(user_id="usr_frank", username="frank", role="user", token_version=1)
PX_MEMBER = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
OUTSIDER = Principal(user_id="usr_ghost", username="ghost", role="user", token_version=1)

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


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
        "weird": Library(id="weird", name="未知种", kind="weird"),
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
    audits = AuditService(AppendOnlyAuditStore(), clock)
    service = ApprovalService(
        store=resources,
        documents=MemoryDocuments(),
        versions=MemoryVersions(),
        objects=MemoryObjects(),
        access=AccessControl(resources, clock=clock),
        audits=audits,
        clock=clock,
    )
    return service, resources, audits


def _code(excinfo) -> str:
    return excinfo.value.code


def test_FR_RBAC_004_p1_3_upload_target_super_admin_any_library() -> None:
    service, _, _ = _seed()
    for target in ("pub", "dept_eng", "dept_art", "proj_x"):
        library = service.validate_upload_target(ADMIN, target, "req_ok")
        assert library.id == target
    for target in ("unassigned", "missing", "weird"):
        with pytest.raises(AuthError) as excinfo:
            service.validate_upload_target(ADMIN, target, "req_no")
        assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_upload_target_department_membership() -> None:
    service, _, _ = _seed()
    assert service.validate_upload_target(ENG_EDITOR, "dept_eng", "req_ok").id == "dept_eng"
    # Cross-department targets read as not_found: no existence leak.
    with pytest.raises(AuthError) as excinfo:
        service.validate_upload_target(ENG_EDITOR, "dept_art", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # Not a project member either.
    with pytest.raises(AuthError) as excinfo:
        service.validate_upload_target(ENG_EDITOR, "proj_x", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_upload_target_project_requires_join() -> None:
    service, _, _ = _seed()
    assert service.validate_upload_target(PX_MEMBER, "proj_x", "req_ok").id == "proj_x"
    assert service.validate_upload_target(LEAD, "proj_x", "req_ok").id == "proj_x"
    # Owning-department admin who never joined is not a project
    # member (D2's letter), even though the project is visible to her.
    with pytest.raises(AuthError) as excinfo:
        service.validate_upload_target(ENG_ADMIN, "proj_x", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_upload_target_public_open_and_unassigned_refused() -> None:
    service, _, _ = _seed()
    # Q1: any uploader may target the public library. The route's
    # require_upload gate still blocks pure outsiders from uploading
    # at all; validation itself does not re-impose that gate.
    assert service.validate_upload_target(OUTSIDER, "pub", "req_ok").id == "pub"
    assert service.validate_upload_target(ENG_EDITOR, "pub", "req_ok").id == "pub"
    with pytest.raises(AuthError) as excinfo:
        service.validate_upload_target(ENG_EDITOR, "unassigned", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_upload_target_is_approver_matches_queue_rule() -> None:
    service, _, _ = _seed()
    eng = service.validate_upload_target(ENG_ADMIN, "dept_eng", "req_ok")
    pub = service.validate_upload_target(ADMIN, "pub", "req_ok")
    proj = service.validate_upload_target(LEAD, "proj_x", "req_ok")
    assert service.is_approver(ADMIN, eng) is True
    assert service.is_approver(ENG_ADMIN, eng) is True
    assert service.is_approver(ART_ADMIN, eng) is False
    assert service.is_approver(ENG_EDITOR, eng) is False
    assert service.is_approver(ENG_ADMIN, pub) is False
    assert service.is_approver(LEAD, proj) is True
    assert service.is_approver(PX_MEMBER, proj) is False


def test_FR_RBAC_004_p1_3_upload_request_create_and_second_refused() -> None:
    service, resources, audits = _seed()
    library = service.validate_upload_target(ENG_EDITOR, "dept_eng", "req_ok")
    request = service.create_upload_request(
        principal=ENG_EDITOR,
        document_id="doc_new",
        version_id="ver_new",
        library=library,
        http_request_id="req_create",
    )
    assert request.status == "pending"
    assert request.proposer == "usr_frank"
    assert request.target_library_id == "dept_eng"
    assert service.pending_request_for("doc_new") is not None
    assert service.pending_request_for("doc_other") is None
    requested = [
        event.to_info()
        for event in audits.events()
        if event.action == "doc.approval.requested"
    ]
    assert len(requested) == 1
    assert requested[0]["metadata"]["target_library_id"] == "dept_eng"
    # A second pending request for the same document is refused,
    # never duplicated (the store's unique backstop is not reached).
    with pytest.raises(DocumentError) as excinfo:
        service.create_upload_request(
            principal=ENG_EDITOR,
            document_id="doc_new",
            version_id="ver_new2",
            library=library,
            http_request_id="req_create2",
        )
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    assert len(resources.approval_requests) == 1
