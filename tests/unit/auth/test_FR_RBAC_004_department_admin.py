"""Department admin service for FR-RBAC-004 (ADR-016 D3, D10).

Power matrix: super admins manage everything; department admins only
their own department, and never grant dept_admin (that is a super admin
appointment); everyone else is refused. Unauthorized departments are
handled as nonexistent; a department admin overreaching inside their
own department gets a plain forbidden instead.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.errors import AuthError
from pivot.auth.ports import Library, Membership, Principal, UserAccount
from pivot.documents.ports import DocumentRecord
from pivot.http.memory import (
    InMemoryUserDirectory,
    MemoryDocuments,
    InMemoryResources,
    UtcClock,
)
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
ENG_ADMIN = Principal(user_id="usr_alice", username="alice", role="user", token_version=1)
ENG_EDITOR = Principal(user_id="usr_bob", username="bob", role="user", token_version=1)
ART_ADMIN = Principal(user_id="usr_carol", username="carol", role="user", token_version=1)
PLAIN = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)


def _seed():
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
    }
    users = InMemoryUserDirectory(
        [
            UserAccount(
                id="usr_admin", username="admin", password_hash="x",
                role="admin", status="active", token_version=1,
            ),
            UserAccount(
                id="usr_alice", username="alice", password_hash="x",
                role="user", status="active", token_version=1,
            ),
            UserAccount(
                id="usr_bob", username="bob", password_hash="x",
                role="user", status="active", token_version=1,
            ),
            UserAccount(
                id="usr_carol", username="carol", password_hash="x",
                role="user", status="active", token_version=1,
            ),
            UserAccount(
                id="usr_dave", username="dave", password_hash="x",
                role="user", status="active", token_version=1,
            ),
        ]
    )
    documents = MemoryDocuments()
    documents.save(
        DocumentRecord(
            id="doc_free", title="未分配文档", space="shared",
            created_by="usr_admin", library_id="unassigned",
        )
    )
    documents.save(
        DocumentRecord(
            id="doc_eng", title="技术文档", space="shared",
            created_by="usr_admin", library_id="dept_eng",
        )
    )
    documents.save(
        DocumentRecord(
            id="doc_gone", title="已删文档", space="shared",
            created_by="usr_admin", library_id="unassigned",
            deleted_at=datetime(2026, 10, 24, tzinfo=UTC),
        )
    )
    audits = AuditService(AppendOnlyAuditStore(), UtcClock())
    service = DepartmentAdminService(
        store=resources,
        documents=documents,
        users=users,
        access=AccessControl(resources),
        audits=audits,
        clock=UtcClock(),
    )
    return service, resources, documents, users, audits


def _code(excinfo) -> str:
    assert isinstance(excinfo.value, AuthError)
    return excinfo.value.code


def _audit_actions(audits) -> list[dict]:
    return [event.to_info() for event in audits.events()]


def test_FR_RBAC_004_super_admin_creates_department_and_audits():
    service, resources, _, _, audits = _seed()
    library, created = service.create_department(ADMIN, "dept_ops", "运维部", "req_1")
    assert created is True
    assert library.id == "dept_ops"
    assert library.kind == "department"
    assert library.dept_id == "dept_ops"
    assert resources.get_library("dept_ops") is not None
    events = _audit_actions(audits)
    assert len(events) == 1
    assert events[0]["action"] == "authz.department.create"
    assert events[0]["result"] == "ok"
    assert events[0]["metadata"]["dept_id"] == "dept_ops"


def test_FR_RBAC_004_department_create_forbidden_for_non_super_admin():
    service, _, _, _, _ = _seed()
    with pytest.raises(AuthError) as eng:
        service.create_department(ENG_ADMIN, "dept_ops", "运维部", "req_1")
    assert _code(eng) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as plain:
        service.create_department(PLAIN, "dept_ops", "运维部", "req_1")
    assert _code(plain) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_department_create_is_idempotent_for_same_library():
    service, resources, _, _, audits = _seed()
    first, first_created = service.create_department(ADMIN, "dept_ops", "运维部", "req_1")
    second, second_created = service.create_department(ADMIN, "dept_ops", "运维部", "req_2")
    assert first == second
    assert first_created is True
    assert second_created is False
    assert len(_audit_actions(audits)) == 1
    assert resources.get_library("dept_ops") is not None


def test_FR_RBAC_004_department_create_rejects_reserved_and_bad_ids():
    service, _, _, _, _ = _seed()
    with pytest.raises(AuthError) as pub:
        service.create_department(ADMIN, "pub", "冒充公共库", "req_1")
    assert _code(pub) == "RESOURCE_FORBIDDEN"
    with pytest.raises(ValueError):
        service.create_department(ADMIN, "Bad Id!", "坏名字", "req_1")


def test_FR_RBAC_004_super_admin_removes_empty_department():
    service, resources, _, _, audits = _seed()
    service.create_department(ADMIN, "dept_ops", "运维部", "req_1")
    service.remove_department(ADMIN, "dept_ops", "req_2")
    assert resources.get_library("dept_ops") is None
    actions = [event["action"] for event in _audit_actions(audits)]
    assert actions == ["authz.department.create", "authz.department.remove"]


def test_FR_RBAC_004_department_remove_refuses_nonempty_department():
    service, resources, _, _, _ = _seed()
    with pytest.raises(AuthError) as members:
        service.remove_department(ADMIN, "dept_eng", "req_1")
    assert _code(members) == "RESOURCE_FORBIDDEN"
    assert resources.get_library("dept_eng") is not None
    with pytest.raises(AuthError) as forbidden:
        service.remove_department(ENG_ADMIN, "dept_art", "req_1")
    assert _code(forbidden) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as missing:
        service.remove_department(ADMIN, "dept_nope", "req_1")
    assert _code(missing) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_department_remove_refuses_department_with_live_documents():
    service, resources, documents, _, _ = _seed()
    service.remove_member(ADMIN, "dept_art", "usr_carol", "req_0")
    documents.save(
        DocumentRecord(
            id="doc_art", title="美术文档", space="shared",
            created_by="usr_admin", library_id="dept_art",
        )
    )
    with pytest.raises(AuthError) as blocked:
        service.remove_department(ADMIN, "dept_art", "req_1")
    assert _code(blocked) == "RESOURCE_FORBIDDEN"
    assert resources.get_library("dept_art") is not None


def test_FR_RBAC_004_department_remove_ignores_deleted_documents():
    service, resources, documents, _, _ = _seed()
    service.create_department(ADMIN, "dept_tmp", "临时部", "req_1")
    documents.save(
        DocumentRecord(
            id="doc_tmp_gone", title="已删临时文档", space="shared",
            created_by="usr_admin", library_id="dept_tmp",
            deleted_at=datetime(2026, 10, 24, tzinfo=UTC),
        )
    )
    service.remove_department(ADMIN, "dept_tmp", "req_2")
    assert resources.get_library("dept_tmp") is None


def test_FR_RBAC_004_super_admin_adds_member_with_any_role():
    service, resources, _, _, audits = _seed()
    member, created = service.add_member(
        ADMIN, "dept_art", "usr_dave", "dept_admin", "req_1"
    )
    assert created is True
    assert member.dept_role == "dept_admin"
    assert member.granted_by == "usr_admin"
    assert resources.get_memberships("usr_dave") == (member,)
    events = _audit_actions(audits)
    assert events[-1]["action"] == "authz.permission_change"
    assert events[-1]["metadata"]["dept_id"] == "dept_art"
    assert events[-1]["metadata"]["dept_role"] == "dept_admin"


def test_FR_RBAC_004_department_admin_adds_only_editor_or_reader_in_own_department():
    service, resources, _, _, _ = _seed()
    member, created = service.add_member(
        ENG_ADMIN, "dept_eng", "usr_dave", "reader", "req_1"
    )
    assert created is True
    assert member.dept_role == "reader"
    with pytest.raises(AuthError) as escalation:
        service.add_member(ENG_ADMIN, "dept_eng", "usr_dave", "dept_admin", "req_2")
    assert _code(escalation) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as cross:
        service.add_member(ENG_ADMIN, "dept_art", "usr_dave", "reader", "req_3")
    assert _code(cross) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as plain:
        service.add_member(PLAIN, "dept_eng", "usr_dave", "reader", "req_4")
    assert _code(plain) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as unknown:
        service.add_member(ADMIN, "dept_eng", "usr_ghost", "reader", "req_5")
    assert _code(unknown) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_add_member_is_idempotent_and_never_overwrites_role():
    service, resources, _, _, audits = _seed()
    member, created = service.add_member(
        ADMIN, "dept_eng", "usr_bob", "editor", "req_1"
    )
    assert created is False
    assert member.dept_role == "editor"
    assert len(_audit_actions(audits)) == 0


def test_FR_RBAC_004_set_member_role_matrix():
    service, resources, _, _, audits = _seed()
    changed = service.set_member_role(
        ENG_ADMIN, "dept_eng", "usr_bob", "reader", "req_1"
    )
    assert changed.dept_role == "reader"
    assert changed.granted_by == "usr_alice"
    events = _audit_actions(audits)
    assert events[-1]["metadata"]["old_role"] == "editor"
    assert events[-1]["metadata"]["new_role"] == "reader"
    with pytest.raises(AuthError) as escalation:
        service.set_member_role(ENG_ADMIN, "dept_eng", "usr_bob", "dept_admin", "req_2")
    assert _code(escalation) == "AUTH_FORBIDDEN"
    promoted = service.set_member_role(
        ADMIN, "dept_eng", "usr_bob", "dept_admin", "req_3"
    )
    assert promoted.dept_role == "dept_admin"
    with pytest.raises(AuthError) as cross:
        service.set_member_role(ENG_ADMIN, "dept_art", "usr_carol", "reader", "req_4")
    assert _code(cross) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as missing:
        service.set_member_role(ADMIN, "dept_eng", "usr_dave", "reader", "req_5")
    assert _code(missing) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_remove_member_matrix():
    service, resources, _, _, audits = _seed()
    service.remove_member(ENG_ADMIN, "dept_eng", "usr_bob", "req_1")
    assert resources.get_memberships("usr_bob") == ()
    assert _audit_actions(audits)[-1]["action"] == "authz.permission_change"
    with pytest.raises(AuthError) as escalation:
        service.remove_member(ENG_ADMIN, "dept_eng", "usr_alice", "req_2")
    assert _code(escalation) == "AUTH_FORBIDDEN"
    service.remove_member(ADMIN, "dept_eng", "usr_alice", "req_3")
    assert resources.get_memberships("usr_alice") == ()
    with pytest.raises(AuthError) as cross:
        service.remove_member(ART_ADMIN, "dept_eng", "usr_bob", "req_4")
    assert _code(cross) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as missing:
        service.remove_member(ADMIN, "dept_eng", "usr_dave", "req_5")
    assert _code(missing) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_list_and_get_department_scoping():
    service, _, _, _, _ = _seed()
    seen = {library.id for library in service.list_departments(ENG_ADMIN, "req_1")}
    assert seen == {"pub", "dept_eng"}
    seen_admin = {library.id for library in service.list_departments(ADMIN, "req_1")}
    assert seen_admin == {"pub", "dept_eng", "dept_art", "unassigned"}
    with pytest.raises(AuthError) as plain:
        service.list_departments(PLAIN, "req_1")
    assert _code(plain) == "AUTH_FORBIDDEN"
    assert service.get_department(ENG_ADMIN, "pub", "req_1").id == "pub"
    with pytest.raises(AuthError) as cross:
        service.get_department(ENG_ADMIN, "dept_art", "req_1")
    assert _code(cross) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_list_members_scoping():
    service, _, _, _, _ = _seed()
    members = service.list_members(ENG_ADMIN, "dept_eng", "req_1")
    assert {member.user_id for member in members} == {"usr_alice", "usr_bob"}
    with pytest.raises(AuthError) as cross:
        service.list_members(ENG_ADMIN, "dept_art", "req_1")
    assert _code(cross) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as plain:
        service.list_members(PLAIN, "dept_eng", "req_1")
    assert _code(plain) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_claim_document_matrix():
    service, _, documents, _, audits = _seed()
    claimed = service.claim_document(ENG_ADMIN, "doc_free", "dept_eng", "req_1")
    assert claimed.library_id == "dept_eng"
    assert documents.get("doc_free").library_id == "dept_eng"
    events = _audit_actions(audits)
    assert events[-1]["action"] == "authz.library.claim"
    assert events[-1]["metadata"]["from_library"] == "unassigned"
    assert events[-1]["metadata"]["to_library"] == "dept_eng"
    with pytest.raises(AuthError) as assigned:
        service.claim_document(ADMIN, "doc_eng", "dept_art", "req_2")
    assert _code(assigned) == "RESOURCE_FORBIDDEN"
    assert documents.get("doc_eng").library_id == "dept_eng"
    with pytest.raises(AuthError) as missing:
        service.claim_document(ADMIN, "doc_nope", "dept_eng", "req_3")
    assert _code(missing) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as deleted:
        service.claim_document(ADMIN, "doc_gone", "dept_eng", "req_4")
    assert _code(deleted) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_claim_document_department_admin_boundaries():
    service, _, documents, _, _ = _seed()
    with pytest.raises(AuthError) as cross:
        service.claim_document(ENG_ADMIN, "doc_free", "dept_art", "req_1")
    assert _code(cross) == "RESOURCE_NOT_FOUND"
    assert documents.get("doc_free").library_id == "unassigned"
    with pytest.raises(AuthError) as pub:
        service.claim_document(ENG_ADMIN, "doc_free", "pub", "req_2")
    assert _code(pub) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as plain:
        service.claim_document(PLAIN, "doc_free", "dept_eng", "req_3")
    assert _code(plain) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as missing_target:
        service.claim_document(ADMIN, "doc_free", "dept_nope", "req_4")
    assert _code(missing_target) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as unassigned_target:
        service.claim_document(ADMIN, "doc_free", "unassigned", "req_5")
    assert _code(unassigned_target) == "RESOURCE_FORBIDDEN"


def test_FR_RBAC_004_membership_change_takes_effect_immediately():
    service, resources, _, users, _ = _seed()
    access = AccessControl(resources)
    before = access.visible_libraries(
        Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
    )
    assert before == frozenset({"pub"})
    token_version_before = users.get_by_id("usr_dave").token_version
    service.add_member(ADMIN, "dept_eng", "usr_dave", "reader", "req_1")
    after = access.visible_libraries(
        Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
    )
    assert after == frozenset({"pub", "dept_eng"})
    assert users.get_by_id("usr_dave").token_version == token_version_before
    service.remove_member(ADMIN, "dept_eng", "usr_dave", "req_2")
    shrunk = access.visible_libraries(
        Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
    )
    assert shrunk == frozenset({"pub"})


def test_FR_RBAC_004_denied_admin_attempt_is_audited():
    service, _, _, _, audits = _seed()
    with pytest.raises(AuthError):
        service.add_member(ENG_ADMIN, "dept_art", "usr_dave", "reader", "req_1")
    events = _audit_actions(audits)
    assert len(events) == 1
    assert events[0]["action"] == "authz.admin_denied"
    assert events[0]["result"] == "denied"
    assert events[0]["metadata"]["dept_id"] == "dept_art"


def test_FR_RBAC_004_audit_store_has_no_update_or_delete_path():
    store = AppendOnlyAuditStore()
    assert not hasattr(store, "update")
    assert not hasattr(store, "delete")
    assert not hasattr(store, "remove")
