"""Real PostgreSQL library visibility and department administration (FR-RBAC-004).

S2's SqlAlchemyLibraryCatalog reader and S4's management write path were
previously proven only on SQLite. These tests close that gap: they run
the same production stores against a real PostgreSQL (this directory's
harness builds the schema with the Alembic migrations, exactly as
production does) and assert the wiring itself — visibility computation
from PG rows and the management service's key paths. The full privilege
matrix stays covered by the unit tests; this file does not re-prove it.

Seeding note: the harness truncates every table between tests, so the
migration's pub/unassigned seed rows survive only for the session's
first test. Seed helpers below are therefore idempotent: each test
seeds exactly the libraries, users, and memberships it needs, and
re-seeding an existing row is a no-op.
"""

from __future__ import annotations

import pytest
from pivot.audit.ports import Actor
from pivot.audit.service import AuditService
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.errors import AuthError
from pivot.auth.ports import Principal
from pivot.db.audit import SqlAlchemyAuditStore
from pivot.db.documents import SqlAlchemyDocumentStore
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import Membership as MembershipRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from pivot.db.users import SqlAlchemyUserDirectory
from pivot.documents.ports import DocumentRecord
from pivot.http.memory import UtcClock
from pivot.security.rbac import AccessControl


def seed_user(pg_session, user_id, username, role="user"):
    pg_session.add(
        UserRow(
            id=user_id, username=username, password_hash="hash",
            role=role, status="active",
        )
    )
    pg_session.commit()


def seed_library(pg_session, library_id, name, kind, dept_id=None):
    # Idempotent: the migration seeds pub/unassigned at upgrade time, so
    # the session's first test already sees them; later tests see a
    # truncated table and need the insert. Never double-insert.
    if pg_session.get(LibraryRow, library_id) is None:
        pg_session.add(
            LibraryRow(id=library_id, name=name, kind=kind, dept_id=dept_id)
        )
        pg_session.commit()


def seed_system_libraries(pg_session):
    seed_library(pg_session, "pub", "公共库", "public")
    seed_library(pg_session, "unassigned", "未分配", "system")


def seed_department(pg_session, dept_id, name):
    seed_library(pg_session, dept_id, name, "department", dept_id=dept_id)


def seed_membership(pg_session, user_id, dept_id, dept_role):
    pg_session.add(
        MembershipRow(
            user_id=user_id, dept_id=dept_id, dept_role=dept_role,
            granted_by="usr_admin",
        )
    )
    pg_session.commit()


def make_catalog(pg_engine):
    return SqlAlchemyLibraryCatalog(session_factory(pg_engine))


def make_service(pg_engine):
    sessions = session_factory(pg_engine)
    catalog = SqlAlchemyLibraryCatalog(sessions)
    audits = AuditService(SqlAlchemyAuditStore(sessions), UtcClock())
    return DepartmentAdminService(
        store=catalog,
        documents=SqlAlchemyDocumentStore(sessions),
        users=SqlAlchemyUserDirectory(sessions),
        access=AccessControl(catalog),
        audits=audits,
        clock=UtcClock(),
    )


def admin_principal():
    return Principal(
        user_id="usr_admin", username="admin", role="admin", token_version=0
    )


def user_principal(user_id, username):
    return Principal(
        user_id=user_id, username=username, role="user", token_version=0
    )


def audit_events(pg_engine, action=None, target=None):
    store = SqlAlchemyAuditStore(session_factory(pg_engine))
    return tuple(
        event
        for event in store.list()
        if (action is None or event.action == action)
        and (target is None or event.target == target)
    )


# --- S2 reader: visibility computation from real PG rows -------------------


def test_FR_RBAC_004_pg_visible_libraries_multi_department_union(
    pg_session, pg_engine
):
    seed_system_libraries(pg_session)
    seed_department(pg_session, "dept_eng", "技术部")
    seed_department(pg_session, "dept_art", "美术部")
    seed_user(pg_session, "usr_multi", "multi")
    seed_membership(pg_session, "usr_multi", "dept_eng", "editor")
    seed_membership(pg_session, "usr_multi", "dept_art", "reader")
    access = AccessControl(make_catalog(pg_engine))
    visible = access.visible_libraries(user_principal("usr_multi", "multi"))
    assert visible == {"pub", "dept_eng", "dept_art"}
    assert "unassigned" not in visible


def test_FR_RBAC_004_pg_visible_libraries_no_membership_public_only(
    pg_session, pg_engine
):
    seed_system_libraries(pg_session)
    seed_department(pg_session, "dept_eng", "技术部")
    seed_user(pg_session, "usr_solo", "solo")
    access = AccessControl(make_catalog(pg_engine))
    assert access.visible_libraries(user_principal("usr_solo", "solo")) == {"pub"}


def test_FR_RBAC_004_pg_visible_libraries_super_admin_all(
    pg_session, pg_engine
):
    seed_system_libraries(pg_session)
    seed_department(pg_session, "dept_eng", "技术部")
    seed_department(pg_session, "dept_art", "美术部")
    seed_user(pg_session, "usr_admin", "admin", role="admin")
    access = AccessControl(make_catalog(pg_engine))
    assert access.visible_libraries(admin_principal()) == {
        "pub", "unassigned", "dept_eng", "dept_art",
    }


def test_FR_RBAC_004_pg_admin_departments_live_from_pg(pg_session, pg_engine):
    seed_system_libraries(pg_session)
    seed_department(pg_session, "dept_eng", "技术部")
    seed_department(pg_session, "dept_art", "美术部")
    seed_user(pg_session, "usr_da", "da")
    seed_membership(pg_session, "usr_da", "dept_eng", "dept_admin")
    seed_membership(pg_session, "usr_da", "dept_art", "reader")
    access = AccessControl(make_catalog(pg_engine))
    principal = user_principal("usr_da", "da")
    assert access.admin_departments(principal) == {"dept_eng"}
    assert access.is_department_admin(principal, "dept_eng") is True
    assert access.is_department_admin(principal, "dept_art") is False


# --- S4 service: management key paths against real PG ------------------------


def test_FR_RBAC_004_pg_admin_create_department_and_members(
    pg_session, pg_engine
):
    seed_system_libraries(pg_session)
    seed_user(pg_session, "usr_admin", "admin", role="admin")
    seed_user(pg_session, "usr_mem", "mem")
    seed_user(pg_session, "usr_da", "da")
    service = make_service(pg_engine)
    library, created = service.create_department(
        admin_principal(), "dept_eng", "技术部", "req_1"
    )
    assert created is True
    assert library.kind == "department"
    member, created = service.add_member(
        admin_principal(), "dept_eng", "usr_mem", "editor", "req_2"
    )
    assert created is True
    assert member.dept_role == "editor"
    service.add_member(admin_principal(), "dept_eng", "usr_da", "dept_admin", "req_3")
    # Read back through a fresh catalog instance: the rows must be in PG,
    # not just held in some object the service kept.
    fresh = make_catalog(pg_engine)
    assert {row.id for row in fresh.list_libraries()} >= {
        "pub", "unassigned", "dept_eng",
    }
    members = {
        row.user_id: row.dept_role
        for row in fresh.get_department_members("dept_eng")
    }
    assert members == {"usr_mem": "editor", "usr_da": "dept_admin"}


def test_FR_RBAC_004_pg_admin_claim_unassigned_document(pg_session, pg_engine):
    seed_system_libraries(pg_session)
    seed_department(pg_session, "dept_eng", "技术部")
    seed_user(pg_session, "usr_admin", "admin", role="admin")
    seed_user(pg_session, "usr_da", "da")
    seed_membership(pg_session, "usr_da", "dept_eng", "dept_admin")
    documents = SqlAlchemyDocumentStore(session_factory(pg_engine))
    documents.save(
        DocumentRecord(
            id="doc-1", title="待认领", space="shared", created_by="usr_admin"
        )
    )
    documents.save(
        DocumentRecord(
            id="doc-2", title="待认领二", space="shared", created_by="usr_admin"
        )
    )
    service = make_service(pg_engine)
    claimed = service.claim_document(
        admin_principal(), "doc-1", "dept_eng", "req_1"
    )
    assert claimed.library_id == "dept_eng"
    assert documents.get("doc-1").library_id == "dept_eng"
    claimed_by_da = service.claim_document(
        user_principal("usr_da", "da"), "doc-2", "dept_eng", "req_2"
    )
    assert claimed_by_da.library_id == "dept_eng"
    claims = audit_events(pg_engine, action="authz.library.claim")
    assert {event.target for event in claims} == {"doc-1", "doc-2"}


def test_FR_RBAC_004_pg_admin_department_audit_scoped_view(
    pg_session, pg_engine
):
    seed_system_libraries(pg_session)
    seed_department(pg_session, "dept_eng", "技术部")
    seed_department(pg_session, "dept_art", "美术部")
    seed_user(pg_session, "usr_admin", "admin", role="admin")
    seed_user(pg_session, "usr_da", "da")
    seed_user(pg_session, "usr_mem", "mem")
    seed_membership(pg_session, "usr_da", "dept_eng", "dept_admin")
    service = make_service(pg_engine)
    service.add_member(admin_principal(), "dept_eng", "usr_mem", "editor", "req_1")
    service.add_member(admin_principal(), "dept_art", "usr_mem", "reader", "req_2")
    audits = AuditService(
        SqlAlchemyAuditStore(session_factory(pg_engine)), UtcClock()
    )
    actor = Actor(user_id="usr_da", username="da", role="user")
    scoped = audits.list_department_events(
        actor, frozenset({"dept_eng"}), "req_3"
    )
    items = scoped["items"]
    assert items
    assert all(item["metadata"]["dept_id"] == "dept_eng" for item in items)
    assert any(
        item["metadata"].get("dept_role") == "editor" for item in items
    )
    assert not any(
        item["metadata"].get("dept_id") == "dept_art" for item in items
    )


def test_FR_RBAC_004_pg_admin_nonempty_department_removal_refused_members(
    pg_session, pg_engine
):
    seed_system_libraries(pg_session)
    seed_department(pg_session, "dept_eng", "技术部")
    seed_user(pg_session, "usr_admin", "admin", role="admin")
    seed_user(pg_session, "usr_mem", "mem")
    seed_membership(pg_session, "usr_mem", "dept_eng", "editor")
    service = make_service(pg_engine)
    with pytest.raises(AuthError) as refused:
        service.remove_department(admin_principal(), "dept_eng", "req_1")
    assert refused.value.code == "RESOURCE_FORBIDDEN"
    assert make_catalog(pg_engine).get_library("dept_eng") is not None


def test_FR_RBAC_004_pg_admin_nonempty_department_removal_refused_live_doc(
    pg_session, pg_engine
):
    seed_system_libraries(pg_session)
    seed_department(pg_session, "dept_eng", "技术部")
    seed_user(pg_session, "usr_admin", "admin", role="admin")
    documents = SqlAlchemyDocumentStore(session_factory(pg_engine))
    documents.save(
        DocumentRecord(
            id="doc-1", title="在库文档", space="shared",
            created_by="usr_admin", library_id="dept_eng",
        )
    )
    service = make_service(pg_engine)
    with pytest.raises(AuthError) as refused:
        service.remove_department(admin_principal(), "dept_eng", "req_1")
    assert refused.value.code == "RESOURCE_FORBIDDEN"
    assert make_catalog(pg_engine).get_library("dept_eng") is not None


def test_FR_RBAC_004_pg_admin_remove_empty_department(pg_session, pg_engine):
    seed_system_libraries(pg_session)
    seed_user(pg_session, "usr_admin", "admin", role="admin")
    service = make_service(pg_engine)
    service.create_department(admin_principal(), "dept_tmp", "临时部", "req_1")
    service.remove_department(admin_principal(), "dept_tmp", "req_2")
    assert make_catalog(pg_engine).get_library("dept_tmp") is None
    removals = audit_events(
        pg_engine, action="authz.department.remove", target="dept_tmp"
    )
    assert len(removals) == 1


def test_FR_RBAC_004_pg_admin_role_change_effective_immediately(
    pg_session, pg_engine
):
    seed_system_libraries(pg_session)
    seed_department(pg_session, "dept_eng", "技术部")
    seed_user(pg_session, "usr_admin", "admin", role="admin")
    seed_user(pg_session, "usr_mem", "mem")
    service = make_service(pg_engine)
    service.add_member(admin_principal(), "dept_eng", "usr_mem", "editor", "req_1")
    principal = user_principal("usr_mem", "mem")
    access = AccessControl(make_catalog(pg_engine))
    assert access.admin_departments(principal) == frozenset()
    service.set_member_role(
        admin_principal(), "dept_eng", "usr_mem", "dept_admin", "req_2"
    )
    fresh_access = AccessControl(make_catalog(pg_engine))
    assert fresh_access.admin_departments(principal) == {"dept_eng"}
    service.remove_member(admin_principal(), "dept_eng", "usr_mem", "req_3")
    newest_access = AccessControl(make_catalog(pg_engine))
    assert newest_access.admin_departments(principal) == frozenset()
    assert newest_access.visible_libraries(principal) == {"pub"}
