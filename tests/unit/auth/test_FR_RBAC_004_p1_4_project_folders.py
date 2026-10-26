"""S4: project-library folders and audit closeout for FR-RBAC-004
(ADR-018 D4, D3, D6).

Project folders reuse the S2 folder mechanism with management moved
from the department admin to the project lead: leads create and
delete folders and manage folder members, folder members come only
from project members, and folder roles carry the same semantics
(full excludes member management; editors cannot delete folders or
touch members; readers read including download/export). Leads and
owning-department admins bypass folder roles entirely; the lead's
folder-member grants are capped like project-member grants (60 days,
no permanent). Folder audit events carry both the owning department
(dept_id, so the department audit view picks them up) and the
project id (so the lead audit view can filter on it).
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
ART_ADMIN = Principal(user_id="usr_carol", username="carol", role="user", token_version=1)
LEAD = Principal(user_id="usr_bob", username="bob", role="user", token_version=1)
PX_EDITOR = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
PX_READER = Principal(user_id="usr_erin", username="erin", role="user", token_version=1)
DEPT_EDITOR = Principal(user_id="usr_frank", username="frank", role="user", token_version=1)
OUTSIDER = Principal(user_id="usr_ghost", username="ghost", role="user", token_version=1)

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


def _seed(*, drop=None):
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
        "proj_y": Library(
            id="proj_y", name="另一项目", kind="project", dept_id="dept_art"
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
        "usr_dave": (
            Membership(
                user_id="usr_dave", dept_id="proj_x", dept_role="editor",
                granted_by="usr_bob",
            ),
        ),
        "usr_erin": (
            Membership(
                user_id="usr_erin", dept_id="proj_x", dept_role="reader",
                granted_by="usr_bob",
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
                ("usr_dave", "dave", "user"),
                ("usr_erin", "erin", "user"),
                ("usr_frank", "frank", "user"),
                ("usr_ghost", "ghost", "user"),
            )
        ]
    )
    documents = MemoryDocuments()
    for doc_id in ("doc_px", "doc_px2"):
        documents.save(
            DocumentRecord(
                id=doc_id, title=doc_id, space="shared",
                created_by="usr_admin", library_id="proj_x",
            )
        )
    documents.save(
        DocumentRecord(
            id="doc_py", title="doc_py", space="shared",
            created_by="usr_admin", library_id="proj_y",
        )
    )
    audits = AuditService(AppendOnlyAuditStore(), clock)
    service = DepartmentAdminService(
        store=resources,
        documents=documents,
        users=users,
        access=AccessControl(resources, clock=clock),
        audits=audits,
        clock=clock,
        folder_collection_drop=drop,
    )
    return service, resources, documents, users, audits


def _actions(audits) -> list[dict]:
    return [event.to_info() for event in audits.events()]


def _code(excinfo) -> str:
    return excinfo.value.code


def _make_folder(service, principal=LEAD, folder_id="fld_px"):
    folder, created = service.create_project_folder(
        principal, "proj_x", folder_id, "项目文件夹", "req_folder"
    )
    assert created is True
    return folder


def _add_member(service, folder_id, user_id, role, principal=LEAD):
    member, created = service.add_project_folder_member(
        principal, "proj_x", folder_id, user_id, role, "req_add",
        expires_at=T0 + timedelta(days=30),
    )
    assert created is True
    return member


def test_FR_RBAC_004_p1_4_project_folder_create_matrix() -> None:
    service, _, _, _, _ = _seed()
    _make_folder(service, principal=LEAD)
    _make_folder(service, principal=ENG_ADMIN, folder_id="fld_b")
    _make_folder(service, principal=ADMIN, folder_id="fld_c")
    with pytest.raises(AuthError) as excinfo:
        service.create_project_folder(
            PX_EDITOR, "proj_x", "fld_d", "X", "req_no"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as excinfo:
        service.create_project_folder(
            ART_ADMIN, "proj_x", "fld_e", "X", "req_no"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.create_project_folder(
            OUTSIDER, "proj_x", "fld_f", "X", "req_no"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_4_project_folder_members_only_from_project() -> None:
    service, _, _, _, _ = _seed()
    _make_folder(service)
    _add_member(service, "fld_px", "usr_dave", "reader")
    # A department editor who is not a project member cannot join.
    with pytest.raises(AuthError) as excinfo:
        service.add_project_folder_member(
            LEAD, "proj_x", "fld_px", "usr_frank", "reader", "req_no"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    # A plain project member cannot manage members, not even full ones.
    _add_member(service, "fld_px", "usr_erin", "full")
    with pytest.raises(AuthError) as excinfo:
        service.add_project_folder_member(
            PX_READER, "proj_x", "fld_px", "usr_dave", "reader", "req_no"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    # An outsider gets not_found, never a leak about the folder.
    with pytest.raises(AuthError) as excinfo:
        service.add_project_folder_member(
            OUTSIDER, "proj_x", "fld_px", "usr_dave", "reader", "req_no"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_4_project_folder_role_matrix() -> None:
    service, _, documents, _, _ = _seed()
    _make_folder(service)
    _add_member(service, "fld_px", "usr_dave", "reader")
    _add_member(service, "fld_px", "usr_erin", "full")
    # A folder reader cannot rename (dave holds the reader row;
    # erin holds full). A full member can, tested via the lead below.
    with pytest.raises(AuthError) as excinfo:
        service.rename_project_folder(
            PX_EDITOR, "proj_x", "fld_px", "新名", "req_no"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    renamed = service.rename_project_folder(
        LEAD, "proj_x", "fld_px", "新名", "req_ok"
    )
    assert renamed.name == "新名"
    # The lead bypasses folder roles: a read-only folder is still
    # fully open to the lead, same as a department admin in S2.
    _make_folder(service, folder_id="fld_ro")
    _add_member(service, "fld_ro", "usr_dave", "reader")
    renamed = service.rename_project_folder(
        LEAD, "proj_x", "fld_ro", "负责人改名", "req_lead"
    )
    assert renamed.name == "负责人改名"
    renamed = service.rename_project_folder(
        ENG_ADMIN, "proj_x", "fld_ro", "部门改名", "req_dept"
    )
    assert renamed.name == "部门改名"
    assert documents.get("doc_px") is not None


def test_FR_RBAC_004_p1_4_project_folder_move_both_sides() -> None:
    service, _, documents, _, _ = _seed()
    _make_folder(service)
    _add_member(service, "fld_px", "usr_erin", "full")
    _add_member(service, "fld_px", "usr_dave", "reader")
    with pytest.raises(AuthError) as excinfo:
        service.move_document_to_project_folder(
            PX_EDITOR, "proj_x", "doc_px", "fld_px", "req_no"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    moved, changed = service.move_document_to_project_folder(
        LEAD, "proj_x", "doc_px", "fld_px", "req_ok"
    )
    assert changed is True
    assert moved.folder_id == "fld_px"
    # No-op only after the gates: a reader probing the current folder
    # still gets forbidden, not a quiet False.
    with pytest.raises(AuthError) as excinfo:
        service.move_document_to_project_folder(
            PX_EDITOR, "proj_x", "doc_px", "fld_px", "req_probe"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    moved, changed = service.move_document_to_project_folder(
        LEAD, "proj_x", "doc_px", "fld_px", "req_noop"
    )
    assert changed is False
    # Back to the default folder through the source-side gate alone.
    moved, changed = service.move_document_to_project_folder(
        LEAD, "proj_x", "doc_px", None, "req_back"
    )
    assert changed is True
    assert moved.folder_id is None
    assert documents.get("doc_px").folder_id is None


def test_FR_RBAC_004_p1_4_project_folder_delete_rules() -> None:
    dropped: list[tuple] = []

    def drop(library_id, folder_id):
        dropped.append((library_id, folder_id))

    service, resources, _, _, _ = _seed(drop=drop)
    _make_folder(service)
    _add_member(service, "fld_px", "usr_dave", "reader")
    with pytest.raises(AuthError) as excinfo:
        service.delete_project_folder(LEAD, "proj_x", "fld_px", "req_no")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    service.remove_project_folder_member(
        LEAD, "proj_x", "fld_px", "usr_dave", "req_rm"
    )
    service.move_document_to_project_folder(
        LEAD, "proj_x", "doc_px", "fld_px", "req_in"
    )
    with pytest.raises(AuthError) as excinfo:
        service.delete_project_folder(LEAD, "proj_x", "fld_px", "req_no2")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    service.move_document_to_project_folder(
        LEAD, "proj_x", "doc_px", None, "req_out"
    )
    service.delete_project_folder(LEAD, "proj_x", "fld_px", "req_ok")
    assert dropped == [("proj_x", "fld_px")]
    assert resources.get_folder("fld_px") is None


def test_FR_RBAC_004_p1_4_project_folder_delete_drop_failure_refuses() -> None:
    def failing_drop(library_id, folder_id):
        raise RuntimeError("collection drop failed")

    service, resources, _, _, _ = _seed(drop=failing_drop)
    _make_folder(service)
    with pytest.raises(RuntimeError):
        service.delete_project_folder(LEAD, "proj_x", "fld_px", "req_no")
    assert resources.get_folder("fld_px") is not None


def test_FR_RBAC_004_p1_4_project_folder_member_cap() -> None:
    service, _, _, _, _ = _seed()
    _make_folder(service)
    over = T0 + timedelta(days=61)
    with pytest.raises(ValueError):
        service.add_project_folder_member(
            LEAD, "proj_x", "fld_px", "usr_dave", "reader", "req_over",
            expires_at=over,
        )
    with pytest.raises(ValueError):
        service.add_project_folder_member(
            LEAD, "proj_x", "fld_px", "usr_dave", "reader", "req_perm",
            expires_at=None,
        )
    # The owning-department admin is uncapped, same as project members.
    member, created = service.add_project_folder_member(
        ENG_ADMIN, "proj_x", "fld_px", "usr_dave", "reader", "req_admin",
        expires_at=None,
    )
    assert created is True
    # A lead extending that member to permanent is capped the same way.
    with pytest.raises(ValueError):
        service.set_project_folder_member_role(
            LEAD, "proj_x", "fld_px", "usr_dave", "reader", "req_unperm",
            expires_at=None,
        )
    within = T0 + timedelta(days=60)
    updated = service.set_project_folder_member_role(
        LEAD, "proj_x", "fld_px", "usr_dave", "reader", "req_ok",
        expires_at=within,
    )
    assert updated.expires_at == within


def test_FR_RBAC_004_p1_4_project_folder_list_get_visibility() -> None:
    service, _, _, _, _ = _seed()
    _make_folder(service, folder_id="fld_a")
    _make_folder(service, folder_id="fld_b")
    _add_member(service, "fld_a", "usr_dave", "reader")
    listed = service.list_project_folders(LEAD, "proj_x", "req_lead")
    assert {f.id for f in listed} == {"fld_a", "fld_b"}
    listed = service.list_project_folders(ENG_ADMIN, "proj_x", "req_dept")
    assert {f.id for f in listed} == {"fld_a", "fld_b"}
    listed = service.list_project_folders(PX_EDITOR, "proj_x", "req_mem")
    assert {f.id for f in listed} == {"fld_a"}
    with pytest.raises(AuthError) as excinfo:
        service.list_project_folders(OUTSIDER, "proj_x", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.get_project_folder(PX_EDITOR, "proj_x", "fld_b", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_4_project_folder_audit_carries_both_ids() -> None:
    service, _, _, _, audits = _seed()
    _make_folder(service)
    _add_member(service, "fld_px", "usr_dave", "reader")
    events = [
        event for event in _actions(audits)
        if event["action"].startswith("authz.folder.")
    ]
    assert events
    for event in events:
        assert event["metadata"]["dept_id"] == "dept_eng"
        assert event["metadata"]["project_id"] == "proj_x"


def test_FR_RBAC_004_p1_4_project_audit_view_scope() -> None:
    service, _, _, _, _ = _seed()
    service.require_project_audit_view(ADMIN, "proj_x", "req_admin")
    service.require_project_audit_view(LEAD, "proj_x", "req_lead")
    service.require_project_audit_view(ENG_ADMIN, "proj_x", "req_dept")
    with pytest.raises(AuthError) as excinfo:
        service.require_project_audit_view(PX_EDITOR, "proj_x", "req_no")
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as excinfo:
        service.require_project_audit_view(OUTSIDER, "proj_x", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.require_project_audit_view(ART_ADMIN, "proj_x", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_4_project_exception_list_scope() -> None:
    service, resources, documents, _, _ = _seed()
    documents.save(
        DocumentRecord(
            id="doc_px_perm", title="p", space="shared",
            created_by="usr_admin", library_id="proj_x",
        )
    )
    resources.documents["doc_px_perm"] = DocumentAuthz(
        id="doc_px_perm", deleted=False, shared_visible=False,
        export_allowed=False, library_id="proj_x",
    )
    service.grant_exception(
        ENG_ADMIN, "doc_px_perm", "req_grant",
        target_user_id="usr_dave", reason="r", expires_at=None,
    )
    rows = service.list_exceptions(
        ENG_ADMIN, "doc_px_perm", "req_list", permanent_only=True
    )
    assert len(rows) == 1
    assert rows[0].expires_at is None
    # Another department's admin cannot see this project's list.
    with pytest.raises(AuthError) as excinfo:
        service.list_exceptions(
            ART_ADMIN, "doc_px_perm", "req_no", permanent_only=True
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # The lead administers no department, so the list is forbidden.
    with pytest.raises(AuthError) as excinfo:
        service.list_exceptions(
            LEAD, "doc_px_perm", "req_no", permanent_only=True
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
