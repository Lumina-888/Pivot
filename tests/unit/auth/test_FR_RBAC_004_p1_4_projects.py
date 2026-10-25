"""S3: project libraries for FR-RBAC-004 (ADR-018 D4, D2).

Project libraries reuse the memberships table (dept_id == project id)
with the project_lead/editor/reader roles (Q3). Owning-department
admins create projects and appoint leads; leads manage members with
any active company user, but cannot appoint other leads, cannot grant
permanent membership, and grant at most 60 days (ADR-017 Q1, wired
live here for the first time). Visibility is pub plus own department
libraries plus joined projects, with owning-department admins seeing
their department's projects without joining. Claims into projects go
to leads and owning-department admins, and still only accept
unassigned documents.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeClock
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.errors import AuthError
from pivot.auth.ports import (
    DocumentAuthz,
    DocumentException,
    Library,
    Membership,
    Principal,
    UserAccount,
)
from pivot.documents.ports import DocumentRecord
from pivot.http.memory import (
    InMemoryResources,
    InMemoryUserDirectory,
    MemoryDocuments,
)
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
ENG_ADMIN = Principal(user_id="usr_alice", username="alice", role="user", token_version=1)
ENG_EDITOR = Principal(user_id="usr_bob", username="bob", role="user", token_version=1)
ART_ADMIN = Principal(user_id="usr_carol", username="carol", role="user", token_version=1)
ENG_READER = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
ENG_READER2 = Principal(user_id="usr_erin", username="erin", role="user", token_version=1)
ENG_EDITOR2 = Principal(user_id="usr_frank", username="frank", role="user", token_version=1)
OUTSIDER = Principal(user_id="usr_ghost", username="ghost", role="user", token_version=1)
IDLE = Principal(user_id="usr_idle", username="idle", role="user", token_version=1)

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
        "unassigned": Library(id="unassigned", name="未分配", kind="system"),
    }
    resources.memberships = {
        "usr_alice": (
            Membership(
                user_id="usr_alice", dept_id="dept_eng",
                dept_role="dept_admin", granted_by="usr_admin",
            ),
        ),
        "usr_bob": (
            Membership(
                user_id="usr_bob", dept_id="dept_eng", dept_role="editor",
                granted_by="usr_admin",
            ),
        ),
        "usr_carol": (
            Membership(
                user_id="usr_carol", dept_id="dept_art",
                dept_role="dept_admin", granted_by="usr_admin",
            ),
        ),
        "usr_dave": (
            Membership(
                user_id="usr_dave", dept_id="dept_eng", dept_role="reader",
                granted_by="usr_admin",
            ),
        ),
        "usr_erin": (
            Membership(
                user_id="usr_erin", dept_id="dept_eng", dept_role="reader",
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
    users = InMemoryUserDirectory(
        [
            UserAccount(
                id=user_id, username=username, password_hash="x",
                role=role, status=status, token_version=1,
            )
            for user_id, username, role, status in (
                ("usr_admin", "admin", "admin", "active"),
                ("usr_alice", "alice", "user", "active"),
                ("usr_bob", "bob", "user", "active"),
                ("usr_carol", "carol", "user", "active"),
                ("usr_dave", "dave", "user", "active"),
                ("usr_erin", "erin", "user", "active"),
                ("usr_frank", "frank", "user", "active"),
                ("usr_ghost", "ghost", "user", "active"),
                ("usr_idle", "idle", "user", "inactive"),
            )
        ]
    )
    documents = MemoryDocuments()
    documents.save(
        DocumentRecord(
            id="doc_un", title="未分配文档", space="shared",
            created_by="usr_admin", library_id="unassigned",
        )
    )
    documents.save(
        DocumentRecord(
            id="doc_eng", title="技术文档", space="shared",
            created_by="usr_admin", library_id="dept_eng",
        )
    )
    resources.documents = {
        "doc_un": DocumentAuthz(
            id="doc_un", deleted=False, shared_visible=False,
            export_allowed=False, library_id="unassigned",
        ),
        "doc_eng": DocumentAuthz(
            id="doc_eng", deleted=False, shared_visible=False,
            export_allowed=False, library_id="dept_eng",
        ),
    }
    audits = AuditService(AppendOnlyAuditStore(), clock)
    service = DepartmentAdminService(
        store=resources,
        documents=documents,
        users=users,
        access=AccessControl(resources, clock=clock),
        audits=audits,
        clock=clock,
    )
    return service, resources, documents, users, audits


def _actions(audits) -> list[dict]:
    return [event.to_info() for event in audits.events()]


def _code(excinfo) -> str:
    return excinfo.value.code


def _make_project(service, principal=ENG_ADMIN, project_id="proj_x",
                  owning="dept_eng"):
    project, created = service.create_project(
        principal, project_id, "跨部门项目", owning, "req_project"
    )
    assert created is True
    return project


def _appoint_lead(service, project_id="proj_x", user_id="usr_erin",
                  principal=ENG_ADMIN):
    member, created = service.appoint_project_lead(
        principal, project_id, user_id, "req_lead"
    )
    assert created is True
    return member


def _lead_principal():
    return Principal(
        user_id="usr_erin", username="erin", role="user", token_version=1
    )


# -- creation ---------------------------------------------------------------


def test_FR_RBAC_004_p1_4_project_create_by_owning_dept_admin() -> None:
    service, resources, _, _, audits = _seed()
    project, created = service.create_project(
        ENG_ADMIN, "proj_x", "跨部门项目", "dept_eng", "req_create"
    )
    assert created is True
    assert project.kind == "project"
    assert project.dept_id == "dept_eng"
    assert resources.libraries["proj_x"] is project
    actions = _actions(audits)
    assert actions[-1]["action"] == "authz.project.create"
    assert actions[-1]["metadata"]["dept_id"] == "dept_eng"
    assert actions[-1]["metadata"]["project_id"] == "proj_x"


def test_FR_RBAC_004_p1_4_project_create_by_super_admin() -> None:
    service, _, _, _, _ = _seed()
    project, created = service.create_project(
        ADMIN, "proj_x", "跨部门项目", "dept_eng", "req_create"
    )
    assert created is True
    assert project.dept_id == "dept_eng"


def test_FR_RBAC_004_p1_4_project_create_wrong_dept_admin_not_found() -> None:
    service, _, _, _, _ = _seed()
    with pytest.raises(AuthError) as excinfo:
        service.create_project(
            ART_ADMIN, "proj_x", "跨部门项目", "dept_eng", "req_create"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_4_project_create_plain_user_forbidden() -> None:
    service, _, _, _, _ = _seed()
    with pytest.raises(AuthError) as excinfo:
        service.create_project(
            ENG_EDITOR, "proj_x", "跨部门项目", "dept_eng", "req_create"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_p1_4_project_create_duplicate_and_collision() -> None:
    service, _, _, _, _ = _seed()
    _make_project(service)
    project, created = service.create_project(
        ENG_ADMIN, "proj_x", "跨部门项目", "dept_eng", "req_dup"
    )
    assert created is False
    assert project.kind == "project"
    with pytest.raises(AuthError) as excinfo:
        service.create_project(
            ENG_ADMIN, "dept_eng", "撞库名", "dept_eng", "req_clash"
        )
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"


def test_FR_RBAC_004_p1_4_project_create_missing_owning_dept() -> None:
    service, _, _, _, _ = _seed()
    with pytest.raises(AuthError) as excinfo:
        service.create_project(
            ADMIN, "proj_x", "跨部门项目", "dept_nope", "req_create"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


# -- lead appointment ---------------------------------------------------------


def test_FR_RBAC_004_p1_4_project_appoint_lead_cross_dept() -> None:
    service, resources, _, _, audits = _seed()
    _make_project(service)
    # The candidate need not belong to the owning department: Carol
    # administers art, yet may lead an engineering project.
    member, created = service.appoint_project_lead(
        ENG_ADMIN, "proj_x", "usr_carol", "req_lead"
    )
    assert created is True
    assert member.dept_role == "project_lead"
    assert member.expires_at is None
    actions = _actions(audits)
    assert actions[-1]["action"] == "authz.project.lead_appointed"
    assert actions[-1]["metadata"]["dept_id"] == "dept_eng"
    assert actions[-1]["metadata"]["project_id"] == "proj_x"


def test_FR_RBAC_004_p1_4_project_appoint_lead_by_lead_forbidden() -> None:
    service, _, _, _, _ = _seed()
    _make_project(service)
    _appoint_lead(service)
    with pytest.raises(AuthError) as excinfo:
        service.appoint_project_lead(
            _lead_principal(), "proj_x", "usr_frank", "req_lead"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_p1_4_project_appoint_lead_inactive_not_found() -> None:
    service, _, _, _, _ = _seed()
    _make_project(service)
    with pytest.raises(AuthError) as excinfo:
        service.appoint_project_lead(
            ENG_ADMIN, "proj_x", "usr_idle", "req_lead"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_4_project_appoint_lead_idempotent_and_promote() -> None:
    service, _, _, _, _ = _seed()
    _make_project(service)
    member, created = service.appoint_project_lead(
        ENG_ADMIN, "proj_x", "usr_erin", "req_lead"
    )
    assert created is True
    member2, created2 = service.appoint_project_lead(
        ENG_ADMIN, "proj_x", "usr_erin", "req_lead2"
    )
    assert created2 is False
    assert member2.dept_role == "project_lead"
    # Promoting an existing temp editor keeps the stored expiry.
    service.add_project_member(
        ENG_ADMIN, "proj_x", "usr_frank", "editor", "req_add",
        expires_at=T0 + timedelta(days=30),
    )
    promoted, created3 = service.appoint_project_lead(
        ENG_ADMIN, "proj_x", "usr_frank", "req_lead3"
    )
    assert created3 is True
    assert promoted.dept_role == "project_lead"
    assert promoted.expires_at == T0 + timedelta(days=30)


# -- member management by the lead --------------------------------------------


def test_FR_RBAC_004_p1_4_project_lead_adds_member_temp_ok() -> None:
    service, _, _, _, audits = _seed()
    _make_project(service)
    _appoint_lead(service)
    member, created = service.add_project_member(
        _lead_principal(), "proj_x", "usr_dave", "editor", "req_add",
        expires_at=T0 + timedelta(days=30),
    )
    assert created is True
    assert member.dept_role == "editor"
    assert member.expires_at == T0 + timedelta(days=30)
    actions = _actions(audits)
    assert actions[-1]["action"] == "authz.project.member_added"
    assert actions[-1]["metadata"]["dept_id"] == "dept_eng"
    assert actions[-1]["metadata"]["project_id"] == "proj_x"


def test_FR_RBAC_004_p1_4_project_lead_cap_sixty_days_live() -> None:
    service, _, _, _, _ = _seed()
    _make_project(service)
    _appoint_lead(service)
    # Exactly 60 days passes; 61 days and permanent do not. This is
    # the first live proof of the P1-2 cap: _grantor_kind now reports
    # project_lead for a lead acting on their own project.
    member, _ = service.add_project_member(
        _lead_principal(), "proj_x", "usr_dave", "editor", "req_add",
        expires_at=T0 + timedelta(days=60),
    )
    assert member.expires_at == T0 + timedelta(days=60)
    with pytest.raises(ValueError, match="at most 60 days"):
        service.add_project_member(
            _lead_principal(), "proj_x", "usr_frank", "editor", "req_add",
            expires_at=T0 + timedelta(days=61),
        )
    with pytest.raises(ValueError, match="cannot be permanent"):
        service.add_project_member(
            _lead_principal(), "proj_x", "usr_frank", "editor", "req_add",
            expires_at=None,
        )


def test_FR_RBAC_004_p1_4_project_lead_cannot_appoint_lead() -> None:
    service, _, _, _, _ = _seed()
    _make_project(service)
    _appoint_lead(service)
    with pytest.raises(AuthError) as excinfo:
        service.add_project_member(
            _lead_principal(), "proj_x", "usr_dave", "project_lead",
            "req_add", expires_at=T0 + timedelta(days=30),
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_p1_4_project_lead_adds_cross_dept_user() -> None:
    service, _, _, _, _ = _seed()
    _make_project(service)
    _appoint_lead(service)
    member, created = service.add_project_member(
        _lead_principal(), "proj_x", "usr_carol", "reader", "req_add",
        expires_at=T0 + timedelta(days=10),
    )
    assert created is True
    assert member.dept_role == "reader"


def test_FR_RBAC_004_p1_4_project_lead_add_inactive_not_found() -> None:
    service, _, _, _, _ = _seed()
    _make_project(service)
    _appoint_lead(service)
    with pytest.raises(AuthError) as excinfo:
        service.add_project_member(
            _lead_principal(), "proj_x", "usr_idle", "reader", "req_add",
            expires_at=T0 + timedelta(days=10),
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_4_project_admin_grants_lead_permanent() -> None:
    service, _, _, _, _ = _seed()
    _make_project(service)
    member, created = service.add_project_member(
        ENG_ADMIN, "proj_x", "usr_erin", "project_lead", "req_add",
        expires_at=None,
    )
    assert created is True
    assert member.dept_role == "project_lead"
    assert member.expires_at is None


def test_FR_RBAC_004_p1_4_project_member_role_change_and_renewal() -> None:
    service, _, _, _, audits = _seed()
    _make_project(service)
    _appoint_lead(service)
    service.add_project_member(
        _lead_principal(), "proj_x", "usr_dave", "reader", "req_add",
        expires_at=T0 + timedelta(days=30),
    )
    updated = service.set_project_member_role(
        _lead_principal(), "proj_x", "usr_dave", "editor", "req_set",
        expires_at=T0 + timedelta(days=45),
    )
    assert updated.dept_role == "editor"
    assert updated.expires_at == T0 + timedelta(days=45)
    actions = [a["action"] for a in _actions(audits)]
    assert "authz.project.member_role_changed" in actions
    assert "authz.project.member_renewed" in actions
    # Extending to permanent is refused for a lead grantor.
    with pytest.raises(ValueError, match="cannot be permanent"):
        service.set_project_member_role(
            _lead_principal(), "proj_x", "usr_dave", "editor", "req_set",
            expires_at=None,
        )
    # A lead cannot promote anyone to lead through the role path.
    with pytest.raises(AuthError) as excinfo:
        service.set_project_member_role(
            _lead_principal(), "proj_x", "usr_dave", "project_lead",
            "req_set",
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_p1_4_project_member_remove_rules() -> None:
    service, _, _, _, _ = _seed()
    _make_project(service)
    _appoint_lead(service)
    service.add_project_member(
        _lead_principal(), "proj_x", "usr_dave", "reader", "req_add",
        expires_at=T0 + timedelta(days=30),
    )
    service.remove_project_member(
        _lead_principal(), "proj_x", "usr_dave", "req_rm"
    )
    members = service.list_project_members(
        _lead_principal(), "proj_x", "req_list"
    )
    assert [m.user_id for m in members] == ["usr_erin"]
    # A lead never removes another lead.
    service.add_project_member(
        ENG_ADMIN, "proj_x", "usr_frank", "project_lead", "req_add",
        expires_at=None,
    )
    with pytest.raises(AuthError) as excinfo:
        service.remove_project_member(
            _lead_principal(), "proj_x", "usr_frank", "req_rm"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    # The owning-department admin removes leads.
    service.remove_project_member(
        ENG_ADMIN, "proj_x", "usr_frank", "req_rm"
    )
    # Removing a non-member is not_found, not a silent no-op.
    with pytest.raises(AuthError) as excinfo:
        service.remove_project_member(
            _lead_principal(), "proj_x", "usr_ghost", "req_rm"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_4_project_editor_cannot_manage_members() -> None:
    service, _, _, _, _ = _seed()
    _make_project(service)
    _appoint_lead(service)
    service.add_project_member(
        _lead_principal(), "proj_x", "usr_dave", "editor", "req_add",
        expires_at=T0 + timedelta(days=30),
    )
    with pytest.raises(AuthError) as excinfo:
        service.add_project_member(
            Principal(
                user_id="usr_dave", username="dave", role="user",
                token_version=1,
            ),
            "proj_x", "usr_frank", "reader", "req_add",
            expires_at=T0 + timedelta(days=10),
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"


# -- visibility, claims, removal ----------------------------------------------


def test_FR_RBAC_004_p1_4_project_visibility_union() -> None:
    service, resources, _, _, _ = _seed()
    _make_project(service)
    _appoint_lead(service)
    access = AccessControl(resources, clock=FakeClock(T0))
    # The lead sees the project through membership; the owning-dept
    # admin sees it without joining; outsiders and other-dept admins
    # do not.
    assert "proj_x" in access.visible_libraries(_lead_principal())
    assert "proj_x" in access.visible_libraries(ENG_ADMIN)
    assert "proj_x" not in access.visible_libraries(OUTSIDER)
    assert "proj_x" not in access.visible_libraries(ART_ADMIN)
    assert "proj_x" in access.visible_libraries(ADMIN)
    listed = service.list_projects(_lead_principal(), "req_list")
    assert [p.id for p in listed] == ["proj_x"]
    assert service.list_projects(OUTSIDER, "req_list") == ()
    project = service.get_project(_lead_principal(), "proj_x", "req_get")
    assert project.kind == "project"
    with pytest.raises(AuthError) as excinfo:
        service.get_project(OUTSIDER, "proj_x", "req_get")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_4_project_claim_by_lead_and_admin() -> None:
    service, _, documents, _, audits = _seed()
    _make_project(service)
    _appoint_lead(service)
    claimed = service.claim_document(
        _lead_principal(), "doc_un", "proj_x", "req_claim"
    )
    assert claimed.library_id == "proj_x"
    actions = _actions(audits)
    assert actions[-1]["action"] == "authz.project.claim"
    assert actions[-1]["metadata"]["dept_id"] == "dept_eng"
    assert actions[-1]["metadata"]["project_id"] == "proj_x"
    # The owning-department admin claims too; editors and outsiders
    # get not_found, never a permission lecture.
    documents.save(
        DocumentRecord(
            id="doc_un2", title="未分配二", space="shared",
            created_by="usr_admin", library_id="unassigned",
        )
    )
    claimed2 = service.claim_document(
        ENG_ADMIN, "doc_un2", "proj_x", "req_claim2"
    )
    assert claimed2.library_id == "proj_x"
    documents.save(
        DocumentRecord(
            id="doc_un3", title="未分配三", space="shared",
            created_by="usr_admin", library_id="unassigned",
        )
    )
    with pytest.raises(AuthError) as excinfo:
        service.claim_document(
            ENG_EDITOR, "doc_un3", "proj_x", "req_claim3"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.claim_document(
            OUTSIDER, "doc_un3", "proj_x", "req_claim4"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # A lead cannot claim an already-placed document.
    with pytest.raises(AuthError) as excinfo:
        service.claim_document(
            _lead_principal(), "doc_eng", "proj_x", "req_claim5"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_4_project_remove_rules() -> None:
    service, _, documents, _, audits = _seed()
    _make_project(service)
    _appoint_lead(service)
    with pytest.raises(AuthError) as excinfo:
        service.remove_project(_lead_principal(), "proj_x", "req_rm")
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as excinfo:
        service.remove_project(ENG_ADMIN, "proj_x", "req_rm")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    service.remove_project_member(ENG_ADMIN, "proj_x", "usr_erin", "req_rm")
    service.remove_project(ENG_ADMIN, "proj_x", "req_rm2")
    actions = _actions(audits)
    assert actions[-1]["action"] == "authz.project.remove"
    assert actions[-1]["metadata"]["dept_id"] == "dept_eng"
    # A project holding a live document refuses removal.
    _make_project(service, project_id="proj_y")
    documents.save(
        DocumentRecord(
            id="doc_py", title="项目文档", space="shared",
            created_by="usr_admin", library_id="proj_y",
        )
    )
    with pytest.raises(AuthError) as excinfo:
        service.remove_project(ENG_ADMIN, "proj_y", "req_rm3")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"


def test_FR_RBAC_004_p1_4_project_expired_member_excluded() -> None:
    service, resources, _, _, _ = _seed()
    _make_project(service)
    service.add_project_member(
        ENG_ADMIN, "proj_x", "usr_dave", "reader", "req_add",
        expires_at=T0 - timedelta(seconds=1),
    )
    access = AccessControl(resources, clock=FakeClock(T0))
    dave = Principal(
        user_id="usr_dave", username="dave", role="user", token_version=1
    )
    assert "proj_x" not in access.visible_libraries(dave)
    # The expired row is purged by the admin member read, so renewal
    # is impossible: only a fresh grant brings the member back.
    with pytest.raises(AuthError) as excinfo:
        service.set_project_member_role(
            ENG_ADMIN, "proj_x", "usr_dave", "reader", "req_set",
            expires_at=T0 + timedelta(days=10),
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_4_project_authorize_and_exception_coexist() -> None:
    service, resources, _, _, _ = _seed()
    _make_project(service)
    _appoint_lead(service)
    resources.documents["doc_px"] = DocumentAuthz(
        id="doc_px", deleted=False, shared_visible=False,
        export_allowed=False, library_id="proj_x",
    )
    access = AccessControl(resources, clock=FakeClock(T0))
    access.authorize_document(_lead_principal(), "doc_px", "req_auth")
    access.authorize_document(ENG_ADMIN, "doc_px", "req_auth")
    with pytest.raises(AuthError) as excinfo:
        access.authorize_document(OUTSIDER, "doc_px", "req_auth")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # An exception grant on the project document still opens it for
    # the outsider: exceptions coexist with project visibility.
    resources.exceptions["exc_1"] = DocumentException(
        id="exc_1", document_id="doc_px", target_user_id="usr_ghost",
        target_dept_id=None, granted_by="usr_admin", reason="",
        expires_at=None,
    )
    access.authorize_document(OUTSIDER, "doc_px", "req_auth2")
