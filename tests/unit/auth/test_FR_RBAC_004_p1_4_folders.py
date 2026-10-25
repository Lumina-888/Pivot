"""S2: department-library folder management for FR-RBAC-004 (ADR-018 D3, D2).

Department admins create and delete folders, manage folder members,
and rename folders; folder members with the full role add and remove
folder documents and move documents between folders. Department admins
bypass folder roles entirely inside their own department: a read-only
folder is still fully open to them. Folder members come only from the
department's live members, and moving a document checks both sides.
Deletion mirrors remove_department: members or live documents refuse
it, and an empty folder's retrieval collection is deleted with it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeClock
from pivot.audit.ports import Actor
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.errors import AuthError
from pivot.auth.ports import (
    DocumentAuthz,
    FolderMembership,
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

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


def _seed(clock: FakeClock, *, drop=None):
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
                user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
                granted_by="usr_admin",
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
                user_id="usr_carol", dept_id="dept_art", dept_role="dept_admin",
                granted_by="usr_admin",
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
    resources.documents = {
        doc_id: DocumentAuthz(
            id=doc_id, deleted=False, shared_visible=False,
            export_allowed=False, library_id=library_id,
        )
        for doc_id, library_id in (
            ("doc_eng", "dept_eng"),
            ("doc_eng2", "dept_eng"),
            ("doc_art", "dept_art"),
        )
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
                ("usr_bob", "bob", "user"),
                ("usr_carol", "carol", "user"),
                ("usr_dave", "dave", "user"),
                ("usr_erin", "erin", "user"),
                ("usr_frank", "frank", "user"),
                ("usr_ghost", "ghost", "user"),
            )
        ]
    )
    documents = MemoryDocuments()
    for doc_id, library_id in (
        ("doc_eng", "dept_eng"),
        ("doc_eng2", "dept_eng"),
        ("doc_art", "dept_art"),
    ):
        documents.save(
            DocumentRecord(
                id=doc_id, title=doc_id, space="shared",
                created_by="usr_admin", library_id=library_id,
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


def _make_folder(service, principal=ENG_ADMIN, folder_id="fld_a"):
    folder, created = service.create_folder(
        principal, "dept_eng", folder_id, "文件夹 A", "req_folder"
    )
    assert created is True
    return folder


def _add_folder_member(service, folder_id, user_id, role, principal=ENG_ADMIN):
    member, created = service.add_folder_member(
        principal, "dept_eng", folder_id, user_id, role, "req_add"
    )
    assert created is True
    return member


# -- create ---------------------------------------------------------------

def test_FR_RBAC_004_folder_dept_admin_creates_and_recreate_is_idempotent() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, audits = _seed(clock)
    folder, created = service.create_folder(
        ENG_ADMIN, "dept_eng", "fld_a", "文件夹 A", "req_create"
    )
    assert created is True
    assert folder.library_id == "dept_eng"
    again, created_again = service.create_folder(
        ENG_ADMIN, "dept_eng", "fld_a", "文件夹 A", "req_create2"
    )
    assert created_again is False
    assert again.id == "fld_a"
    created_events = [
        event for event in _actions(audits)
        if event["action"] == "authz.folder.created"
    ]
    assert len(created_events) == 1
    assert created_events[0]["metadata"]["dept_id"] == "dept_eng"
    assert created_events[0]["metadata"]["folder_id"] == "fld_a"


def test_FR_RBAC_004_folder_super_admin_creates() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    folder, created = service.create_folder(
        ADMIN, "dept_eng", "fld_a", "文件夹 A", "req_create"
    )
    assert created is True
    assert folder.id == "fld_a"


def test_FR_RBAC_004_folder_editor_create_is_not_found() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    with pytest.raises(AuthError) as excinfo:
        service.create_folder(
            ENG_EDITOR, "dept_eng", "fld_a", "文件夹 A", "req_create"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_cross_department_create_is_not_found() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    with pytest.raises(AuthError) as excinfo:
        service.create_folder(
            ART_ADMIN, "dept_eng", "fld_a", "文件夹 A", "req_create"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_create_in_public_library_is_not_found() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    with pytest.raises(AuthError) as excinfo:
        service.create_folder(ADMIN, "pub", "fld_a", "文件夹 A", "req_create")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_id_colliding_with_library_is_rejected() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    with pytest.raises(ValueError):
        service.create_folder(
            ENG_ADMIN, "dept_eng", "dept_art", "冒名文件夹", "req_create"
        )
    with pytest.raises(ValueError):
        service.create_folder(
            ENG_ADMIN, "dept_eng", "pub", "冒名文件夹", "req_create"
        )


def test_FR_RBAC_004_folder_create_bad_id_or_name_is_rejected() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    with pytest.raises(ValueError):
        service.create_folder(
            ENG_ADMIN, "dept_eng", "Bad Id!", "文件夹", "req_create"
        )
    with pytest.raises(ValueError):
        service.create_folder(
            ENG_ADMIN, "dept_eng", "fld_a", "", "req_create"
        )


# -- delete ---------------------------------------------------------------

def test_FR_RBAC_004_folder_delete_empty_drops_collection() -> None:
    clock = FakeClock(T0)
    dropped: list[tuple[str, str]] = []
    service, resources, _, _, audits = _seed(
        clock, drop=lambda library_id, folder_id: dropped.append(
            (library_id, folder_id)
        ),
    )
    _make_folder(service)
    service.delete_folder(ENG_ADMIN, "dept_eng", "fld_a", "req_delete")
    assert resources.get_folder("fld_a") is None
    assert dropped == [("dept_eng", "fld_a")]
    deleted = [
        event for event in _actions(audits)
        if event["action"] == "authz.folder.deleted"
    ]
    assert len(deleted) == 1
    assert deleted[0]["metadata"]["dept_id"] == "dept_eng"


def test_FR_RBAC_004_folder_delete_with_members_is_forbidden() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    _make_folder(service)
    _add_folder_member(service, "fld_a", "usr_dave", "reader")
    with pytest.raises(AuthError) as excinfo:
        service.delete_folder(ENG_ADMIN, "dept_eng", "fld_a", "req_delete")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    assert resources.get_folder("fld_a") is not None


def test_FR_RBAC_004_folder_delete_with_live_document_is_forbidden() -> None:
    clock = FakeClock(T0)
    service, resources, documents, _, _ = _seed(clock)
    _make_folder(service)
    service.move_document_to_folder(
        ENG_ADMIN, "dept_eng", "doc_eng", "fld_a", "req_move"
    )
    with pytest.raises(AuthError) as excinfo:
        service.delete_folder(ENG_ADMIN, "dept_eng", "fld_a", "req_delete")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    assert resources.get_folder("fld_a") is not None


def test_FR_RBAC_004_folder_delete_collection_failure_refuses() -> None:
    clock = FakeClock(T0)

    def _boom(library_id, folder_id):
        raise RuntimeError("qdrant down")

    service, resources, _, _, _ = _seed(clock, drop=_boom)
    _make_folder(service)
    with pytest.raises(RuntimeError):
        service.delete_folder(ENG_ADMIN, "dept_eng", "fld_a", "req_delete")
    # Nothing changed: the folder row survives a failed collection drop.
    assert resources.get_folder("fld_a") is not None


def test_FR_RBAC_004_folder_delete_by_editor_is_not_found() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    _make_folder(service)
    with pytest.raises(AuthError) as excinfo:
        service.delete_folder(ENG_EDITOR, "dept_eng", "fld_a", "req_delete")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


# -- list / get -------------------------------------------------------------

def test_FR_RBAC_004_folder_list_dept_admin_sees_all_member_sees_own() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    _make_folder(service, folder_id="fld_a")
    _make_folder(service, folder_id="fld_b")
    _add_folder_member(service, "fld_a", "usr_dave", "reader")
    admin_items = service.list_folders(ENG_ADMIN, "dept_eng", "req_list")
    assert {item.id for item in admin_items} == {"fld_a", "fld_b"}
    member_items = service.list_folders(ENG_READER, "dept_eng", "req_list")
    assert [item.id for item in member_items] == ["fld_a"]
    # The default folder has no row and never appears in the list.
    assert all(item.id != "dept_eng" for item in member_items)


def test_FR_RBAC_004_folder_list_outsider_is_not_found() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    _make_folder(service)
    with pytest.raises(AuthError) as excinfo:
        service.list_folders(OUTSIDER, "dept_eng", "req_list")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_get_member_nonmember_and_admin() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    _make_folder(service)
    _add_folder_member(service, "fld_a", "usr_dave", "reader")
    assert service.get_folder(
        ENG_READER, "dept_eng", "fld_a", "req_get"
    ).id == "fld_a"
    assert service.get_folder(
        ENG_ADMIN, "dept_eng", "fld_a", "req_get"
    ).id == "fld_a"
    with pytest.raises(AuthError) as excinfo:
        service.get_folder(ENG_READER2, "dept_eng", "fld_a", "req_get")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


# -- rename ---------------------------------------------------------------

def test_FR_RBAC_004_folder_rename_full_member_and_dept_admin_bypass() -> None:
    clock = FakeClock(T0)
    service, _, _, _, audits = _seed(clock)
    _make_folder(service)
    _add_folder_member(service, "fld_a", "usr_frank", "full")
    _add_folder_member(service, "fld_a", "usr_dave", "reader")
    renamed = service.rename_folder(
        ENG_EDITOR2, "dept_eng", "fld_a", "新名字", "req_rename"
    )
    assert renamed.name == "新名字"
    # A department admin renames even a read-only folder: folder roles
    # never restrict a department admin inside their own department.
    renamed_again = service.rename_folder(
        ENG_ADMIN, "dept_eng", "fld_a", "管理员改名", "req_rename2"
    )
    assert renamed_again.name == "管理员改名"
    assert len(service.list_folder_members(
        ENG_ADMIN, "dept_eng", "fld_a", "req_list"
    )) == 2
    renamed_events = [
        event for event in _actions(audits)
        if event["action"] == "authz.folder.renamed"
    ]
    assert len(renamed_events) == 2
    assert renamed_events[0]["metadata"]["dept_id"] == "dept_eng"


def test_FR_RBAC_004_folder_rename_reader_is_forbidden_outsider_not_found() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    _make_folder(service)
    _add_folder_member(service, "fld_a", "usr_dave", "reader")
    with pytest.raises(AuthError) as excinfo:
        service.rename_folder(
            ENG_READER, "dept_eng", "fld_a", "新名字", "req_rename"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as excinfo:
        service.rename_folder(
            OUTSIDER, "dept_eng", "fld_a", "新名字", "req_rename"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


# -- folder members ---------------------------------------------------------

def test_FR_RBAC_004_folder_member_add_and_readd_is_idempotent() -> None:
    clock = FakeClock(T0)
    service, _, _, _, audits = _seed(clock)
    _make_folder(service)
    member, created = service.add_folder_member(
        ENG_ADMIN, "dept_eng", "fld_a", "usr_dave", "reader", "req_add"
    )
    assert created is True
    assert member.folder_role == "reader"
    again, created_again = service.add_folder_member(
        ENG_ADMIN, "dept_eng", "fld_a", "usr_dave", "reader", "req_add2"
    )
    assert created_again is False
    assert again.user_id == "usr_dave"
    added = [
        event for event in _actions(audits)
        if event["action"] == "authz.folder.member_added"
    ]
    assert len(added) == 1
    assert added[0]["metadata"]["dept_id"] == "dept_eng"
    assert added[0]["metadata"]["folder_id"] == "fld_a"


def test_FR_RBAC_004_folder_member_must_be_department_member() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    _make_folder(service)
    # usr_ghost exists but belongs to no department.
    with pytest.raises(AuthError) as excinfo:
        service.add_folder_member(
            ENG_ADMIN, "dept_eng", "fld_a", "usr_ghost", "reader", "req_add"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    # usr_carol belongs to another department.
    with pytest.raises(AuthError) as excinfo:
        service.add_folder_member(
            ENG_ADMIN, "dept_eng", "fld_a", "usr_carol", "reader", "req_add"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_folder_member_add_unknown_user_is_not_found() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    _make_folder(service)
    with pytest.raises(AuthError) as excinfo:
        service.add_folder_member(
            ENG_ADMIN, "dept_eng", "fld_a", "usr_nope", "reader", "req_add"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_member_add_by_editor_forbidden_cross_dept_not_found() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    _make_folder(service)
    with pytest.raises(AuthError) as excinfo:
        service.add_folder_member(
            ENG_EDITOR, "dept_eng", "fld_a", "usr_dave", "reader", "req_add"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as excinfo:
        service.add_folder_member(
            ART_ADMIN, "dept_eng", "fld_a", "usr_dave", "reader", "req_add"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_member_remove_and_role_change_with_renewal() -> None:
    clock = FakeClock(T0)
    service, _, _, _, audits = _seed(clock)
    _make_folder(service)
    _add_folder_member(service, "fld_a", "usr_dave", "reader")
    updated = service.set_folder_member_role(
        ENG_ADMIN, "dept_eng", "fld_a", "usr_dave", "editor", "req_set"
    )
    assert updated.folder_role == "editor"
    # A full member still cannot manage members: role assignment is a
    # department admin act, and full excludes member management.
    _add_folder_member(service, "fld_a", "usr_frank", "full")
    with pytest.raises(AuthError) as excinfo:
        service.add_folder_member(
            ENG_EDITOR2, "dept_eng", "fld_a", "usr_erin", "reader", "req_add"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    service.remove_folder_member(
        ENG_ADMIN, "dept_eng", "fld_a", "usr_dave", "req_remove"
    )
    assert service.list_folder_members(
        ENG_ADMIN, "dept_eng", "fld_a", "req_list"
    )[0].user_id == "usr_frank"
    actions = [event["action"] for event in _actions(audits)]
    assert "authz.folder.member_role_changed" in actions
    assert "authz.folder.member_removed" in actions


def test_FR_RBAC_004_folder_member_expiry_renewal_and_purge() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, audits = _seed(clock)
    _make_folder(service)
    expires = T0 + timedelta(days=30)
    service.add_folder_member(
        ENG_ADMIN, "dept_eng", "fld_a", "usr_dave", "reader", "req_add",
        expires_at=expires,
    )
    # Extension before expiry writes its own renewal event.
    renewed = service.set_folder_member_role(
        ENG_ADMIN, "dept_eng", "fld_a", "usr_dave", "reader", "req_set",
        expires_at=T0 + timedelta(days=60),
    )
    assert renewed.expires_at == T0 + timedelta(days=60)
    renewed_events = [
        event for event in _actions(audits)
        if event["action"] == "authz.folder.member_renewed"
    ]
    assert len(renewed_events) == 1
    assert renewed_events[0]["metadata"]["folder_id"] == "fld_a"
    # Explicit null clears to a long-term grant.
    cleared = service.set_folder_member_role(
        ENG_ADMIN, "dept_eng", "fld_a", "usr_dave", "reader", "req_set2",
        expires_at=None,
    )
    assert cleared.expires_at is None
    # An expired row is purged by the member read: it cannot be
    # renewed, only re-granted.
    resources.folder_memberships["usr_dave"] = (
        FolderMembership(
            folder_id="fld_a", user_id="usr_dave", folder_role="reader",
            granted_by="usr_admin", expires_at=T0 - timedelta(seconds=1),
        ),
    )
    with pytest.raises(AuthError) as excinfo:
        service.set_folder_member_role(
            ENG_ADMIN, "dept_eng", "fld_a", "usr_dave", "reader", "req_set3"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    assert resources.get_folder_memberships("usr_dave") == ()


def test_FR_RBAC_004_folder_member_list_is_manager_only() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    _make_folder(service)
    _add_folder_member(service, "fld_a", "usr_dave", "reader")
    with pytest.raises(AuthError) as excinfo:
        service.list_folder_members(ENG_READER, "dept_eng", "fld_a", "req_list")
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    items = service.list_folder_members(
        ENG_ADMIN, "dept_eng", "fld_a", "req_list"
    )
    assert [item.user_id for item in items] == ["usr_dave"]


# -- moves ------------------------------------------------------------------

def test_FR_RBAC_004_folder_move_default_to_folder_and_back() -> None:
    clock = FakeClock(T0)
    service, _, documents, _, audits = _seed(clock)
    _make_folder(service)
    moved, changed = service.move_document_to_folder(
        ENG_ADMIN, "dept_eng", "doc_eng", "fld_a", "req_move"
    )
    assert changed is True
    assert moved.folder_id == "fld_a"
    assert documents.get("doc_eng").folder_id == "fld_a"
    back, changed_back = service.move_document_to_folder(
        ENG_ADMIN, "dept_eng", "doc_eng", None, "req_move2"
    )
    assert changed_back is True
    assert back.folder_id is None
    actions = [event["action"] for event in _actions(audits)]
    assert actions.count("authz.folder.document_added") == 1
    assert actions.count("authz.folder.document_removed") == 1
    added = [
        event for event in _actions(audits)
        if event["action"] == "authz.folder.document_added"
    ][0]
    assert added["metadata"]["dept_id"] == "dept_eng"
    assert added["metadata"]["folder_id"] == "fld_a"


def test_FR_RBAC_004_folder_move_full_member_adds_from_default() -> None:
    clock = FakeClock(T0)
    service, _, documents, _, _ = _seed(clock)
    _make_folder(service)
    _add_folder_member(service, "fld_a", "usr_frank", "full")
    # A full member adds documents to their own folder from the
    # default folder: the target side alone gates that move.
    moved, changed = service.move_document_to_folder(
        ENG_EDITOR2, "dept_eng", "doc_eng", "fld_a", "req_move"
    )
    assert changed is True
    assert documents.get("doc_eng").folder_id == "fld_a"
    # And removes them back to the default folder: the source side.
    _, changed_back = service.move_document_to_folder(
        ENG_EDITOR2, "dept_eng", "doc_eng", None, "req_move2"
    )
    assert changed_back is True


def test_FR_RBAC_004_folder_move_reader_and_editor_are_refused() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    _make_folder(service)
    _add_folder_member(service, "fld_a", "usr_dave", "reader")
    _add_folder_member(service, "fld_a", "usr_bob", "editor")
    with pytest.raises(AuthError) as excinfo:
        service.move_document_to_folder(
            ENG_READER, "dept_eng", "doc_eng", "fld_a", "req_move"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as excinfo:
        service.move_document_to_folder(
            ENG_EDITOR, "dept_eng", "doc_eng", "fld_a", "req_move"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_folder_move_between_folders_needs_both_sides() -> None:
    clock = FakeClock(T0)
    service, _, documents, _, _ = _seed(clock)
    _make_folder(service, folder_id="fld_a")
    _make_folder(service, folder_id="fld_b")
    _add_folder_member(service, "fld_a", "usr_frank", "full")
    _add_folder_member(service, "fld_b", "usr_frank", "full")
    _add_folder_member(service, "fld_b", "usr_dave", "reader")
    service.move_document_to_folder(
        ENG_ADMIN, "dept_eng", "doc_eng", "fld_a", "req_move"
    )
    # Full in both folders: the move succeeds and writes both events.
    moved, changed = service.move_document_to_folder(
        ENG_EDITOR2, "dept_eng", "doc_eng", "fld_b", "req_move2"
    )
    assert changed is True
    assert moved.folder_id == "fld_b"
    # A reader of the target folder cannot pull a document in, even
    # though the document sits in a folder they cannot manage.
    with pytest.raises(AuthError) as excinfo:
        service.move_document_to_folder(
            ENG_READER, "dept_eng", "doc_eng", "fld_a", "req_move3"
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    assert documents.get("doc_eng").folder_id == "fld_b"


def test_FR_RBAC_004_folder_move_same_folder_is_noop_after_checks() -> None:
    clock = FakeClock(T0)
    service, _, documents, _, audits = _seed(clock)
    _make_folder(service)
    _add_folder_member(service, "fld_a", "usr_frank", "full")
    service.move_document_to_folder(
        ENG_ADMIN, "dept_eng", "doc_eng", "fld_a", "req_move"
    )
    before = len(_actions(audits))
    moved, changed = service.move_document_to_folder(
        ENG_EDITOR2, "dept_eng", "doc_eng", "fld_a", "req_move2"
    )
    assert changed is False
    assert moved.folder_id == "fld_a"
    assert len(_actions(audits)) == before
    # An outsider probing the same-folder move learns nothing: the
    # permission check runs before the no-op answer.
    with pytest.raises(AuthError) as excinfo:
        service.move_document_to_folder(
            OUTSIDER, "dept_eng", "doc_eng", "fld_a", "req_move3"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_move_cross_library_and_unknown_targets() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    _make_folder(service)
    # An art document through the eng path is not found for a dept
    # admin, and forbidden for a super admin who knows the target.
    with pytest.raises(AuthError) as excinfo:
        service.move_document_to_folder(
            ENG_ADMIN, "dept_eng", "doc_art", "fld_a", "req_move"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.move_document_to_folder(
            ADMIN, "dept_eng", "doc_art", "fld_a", "req_move"
        )
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    with pytest.raises(AuthError) as excinfo:
        service.move_document_to_folder(
            ENG_ADMIN, "dept_eng", "doc_eng", "fld_nope", "req_move"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.move_document_to_folder(
            ENG_ADMIN, "dept_eng", "doc_nope", "fld_a", "req_move"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_move_dept_admin_bypasses_read_only_folder() -> None:
    clock = FakeClock(T0)
    service, _, documents, _, _ = _seed(clock)
    _make_folder(service)
    _add_folder_member(service, "fld_a", "usr_dave", "reader")
    moved, changed = service.move_document_to_folder(
        ENG_ADMIN, "dept_eng", "doc_eng", "fld_a", "req_move"
    )
    assert changed is True
    assert documents.get("doc_eng").folder_id == "fld_a"


def test_FR_RBAC_004_folder_move_expired_member_is_outsider() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    _make_folder(service)
    resources.folder_memberships["usr_frank"] = (
        FolderMembership(
            folder_id="fld_a", user_id="usr_frank", folder_role="full",
            granted_by="usr_admin", expires_at=T0 - timedelta(seconds=1),
        ),
    )
    with pytest.raises(AuthError) as excinfo:
        service.move_document_to_folder(
            ENG_EDITOR2, "dept_eng", "doc_eng", "fld_a", "req_move"
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


# -- audit view and compensation ---------------------------------------------

def test_FR_RBAC_004_folder_events_visible_in_department_audit_view() -> None:
    clock = FakeClock(T0)
    service, _, _, _, audits = _seed(clock)
    _make_folder(service)
    _add_folder_member(service, "fld_a", "usr_dave", "reader")
    service.move_document_to_folder(
        ENG_ADMIN, "dept_eng", "doc_eng", "fld_a", "req_move"
    )
    listed = audits.list_department_events(
        Actor(user_id="usr_alice", username="alice", role="user", status="active"),
        frozenset({"dept_eng"}),
        "req_list",
    )
    actions = [item["action"] for item in listed["items"]]
    assert "authz.folder.created" in actions
    assert "authz.folder.member_added" in actions
    assert "authz.folder.document_added" in actions
    assert all(
        item["metadata"]["dept_id"] == "dept_eng" for item in listed["items"]
    )
    other = audits.list_department_events(
        Actor(user_id="usr_carol", username="carol", role="user", status="active"),
        frozenset({"dept_art"}),
        "req_list",
    )
    assert other["items"] == []


class _FailingAuditStore:
    def append(self, event) -> None:
        raise RuntimeError("audit down")

    def events(self):
        return ()


def test_FR_RBAC_004_folder_audit_failure_compensates_on_memory_path() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    failing = DepartmentAdminService(
        store=resources,
        documents=MemoryDocuments(),
        users=InMemoryUserDirectory([]),
        access=AccessControl(resources, clock=clock),
        audits=AuditService(_FailingAuditStore(), clock),
        clock=clock,
    )
    # The memory path has no transaction: a failed audit write rolls
    # the mutation back instead of landing without its trace.
    with pytest.raises(RuntimeError):
        failing.create_folder(
            ADMIN, "dept_eng", "fld_a", "文件夹 A", "req_create"
        )
    assert resources.get_folder("fld_a") is None
