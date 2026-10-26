"""Real PostgreSQL proof for S4 project folders (FR-RBAC-004, ADR-018 D4).

Same shapes as the SQLite proof, against the production store whose
schema comes from the Alembic migrations. Skipped without
PIVOT_TEST_PG_URL. Seeding commits in the CI #240/#256 order: users
first, then library rows, then documents and memberships, so every
foreign-key target exists before its referrer is inserted.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pivot.audit.service import AuditService
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.errors import AuthError
from pivot.auth.ports import (
    Folder,
    FolderMembership,
    Principal,
    UserAccount,
)
from pivot.db.audit import SqlAlchemyAuditStore
from pivot.db.documents import SqlAlchemyDocumentStore
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.scoped import shared_session
from pivot.db.session import session_factory
from pivot.http.memory import InMemoryUserDirectory
from pivot.security.rbac import AccessControl

NOW = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)
ADMIN = Principal("usr_admin", "admin", "admin", 0)
LEAD = Principal("usr_bob", "bob", "user", 1)
ALICE = Principal("usr_alice", "alice", "user", 1)
DAVE = Principal("usr_dave", "dave", "user", 1)


class _Clock:
    def now(self) -> datetime:
        return NOW


def _seed(pg_session) -> None:
    for user_id, username, role in (
        ("usr_admin", "admin", "admin"),
        ("usr_alice", "alice", "user"),
        ("usr_bob", "bob", "user"),
        ("usr_dave", "dave", "user"),
    ):
        pg_session.add(
            UserRow(
                id=user_id, username=username, password_hash="hash",
                role=role, status="active",
            )
        )
    pg_session.commit()
    pg_session.add(
        LibraryRow(
            id="dept_eng", name="技术部", kind="department",
            dept_id="dept_eng",
        )
    )
    pg_session.commit()
    pg_session.add(
        LibraryRow(
            id="proj_x", name="跨部门项目", kind="project",
            dept_id="dept_eng",
        )
    )
    pg_session.commit()
    pg_session.add(
        DocumentRow(id="doc_px", title="t", created_by="usr_admin",
                    library_id="proj_x")
    )
    pg_session.commit()


def _assembly(pg_engine):
    sessions = session_factory(pg_engine)
    catalog = SqlAlchemyLibraryCatalog(sessions)
    documents = SqlAlchemyDocumentStore(sessions)
    audit_store = SqlAlchemyAuditStore(sessions)
    audits = AuditService(audit_store, _Clock())
    access = AccessControl(catalog, clock=_Clock())
    users = InMemoryUserDirectory(
        [
            UserAccount(
                id=user_id, username=username, password_hash="hash",
                role="admin" if user_id == "usr_admin" else "user",
                status="active",
            )
            for user_id, username in (
                ("usr_admin", "admin"),
                ("usr_alice", "alice"),
                ("usr_bob", "bob"),
                ("usr_dave", "dave"),
            )
        ]
    )
    service = DepartmentAdminService(
        store=catalog,
        documents=documents,
        users=users,
        access=access,
        audits=audits,
        clock=_Clock(),
        transaction=lambda: shared_session(sessions),
    )
    return catalog, documents, audit_store, service


def _events(audit_store, action: str) -> tuple:
    return tuple(
        event for event in audit_store.list() if event.action == action
    )


def test_FR_RBAC_004_project_folder_crud_and_members_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    catalog, _, _, _ = _assembly(pg_engine)
    assert catalog.get_folder("fld_px") is None
    catalog.create_folder(
        Folder(id="fld_px", library_id="proj_x", name="项目文件夹")
    )
    assert catalog.get_folder("fld_px").name == "项目文件夹"
    assert [row.id for row in catalog.list_folders("proj_x")] == ["fld_px"]
    catalog.add_folder_member(
        FolderMembership(
            folder_id="fld_px", user_id="usr_dave", folder_role="reader",
            granted_by="usr_bob",
        )
    )
    (member,) = catalog.get_folder_members("fld_px")
    assert member.folder_role == "reader"
    catalog.set_folder(
        Folder(id="fld_px", library_id="proj_x", name="新名字")
    )
    assert catalog.get_folder("fld_px").name == "新名字"
    (kept,) = catalog.get_folder_members("fld_px")
    assert kept.folder_role == "reader"
    catalog.delete_folder("fld_px")
    assert catalog.get_folder("fld_px") is None
    assert catalog.get_folder_members("fld_px") == ()


def test_FR_RBAC_004_project_folder_service_flow_and_visibility_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    catalog, documents, audit_store, service = _assembly(pg_engine)
    service.add_member(ADMIN, "dept_eng", "usr_alice", "dept_admin", "req_1")
    _, _ = service.appoint_project_lead(ADMIN, "proj_x", "usr_bob", "req_2")
    service.add_project_member(
        LEAD, "proj_x", "usr_dave", "editor", "req_3",
        expires_at=NOW + timedelta(days=30),
    )
    folder, created = service.create_project_folder(
        LEAD, "proj_x", "fld_px", "项目文件夹", "req_4"
    )
    assert created is True
    member, created = service.add_project_folder_member(
        LEAD, "proj_x", "fld_px", "usr_dave", "reader", "req_5",
        expires_at=NOW + timedelta(days=30),
    )
    assert created is True
    moved, changed = service.move_document_to_project_folder(
        LEAD, "proj_x", "doc_px", "fld_px", "req_6"
    )
    assert changed is True
    assert moved.folder_id == "fld_px"
    assert documents.get("doc_px").folder_id == "fld_px"
    # The SQL catalog read path behind AccessControl sees the folder
    # for the lead, the owning-department admin, and the member.
    access = AccessControl(catalog, clock=_Clock())
    assert access.visible_folder_ids(LEAD) == frozenset({"fld_px"})
    assert access.visible_folder_ids(ALICE) == frozenset({"fld_px"})
    assert access.visible_folder_ids(DAVE) == frozenset({"fld_px"})
    created_events = _events(audit_store, "authz.folder.created")
    assert len(created_events) == 1
    assert created_events[0].metadata.get("dept_id") == "dept_eng"
    assert created_events[0].metadata.get("project_id") == "proj_x"
    assert len(_events(audit_store, "authz.folder.member_added")) == 1
    assert len(_events(audit_store, "authz.folder.document_added")) == 1
    # A non-empty folder cannot be deleted, on PostgreSQL either.
    with pytest.raises(AuthError) as excinfo:
        service.delete_project_folder(LEAD, "proj_x", "fld_px", "req_7")
    assert excinfo.value.code == "RESOURCE_FORBIDDEN"
    assert catalog.get_folder("fld_px") is not None


def test_FR_RBAC_004_project_folder_audit_failure_rolls_back_create_pg(
    pg_session, pg_engine, monkeypatch
) -> None:
    _seed(pg_session)
    catalog, _, audit_store, service = _assembly(pg_engine)
    service.add_member(ADMIN, "dept_eng", "usr_alice", "dept_admin", "req_1")
    service.appoint_project_lead(ADMIN, "proj_x", "usr_bob", "req_2")

    def _boom(*args, **kwargs) -> None:
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(SqlAlchemyAuditStore, "append", _boom)
    with pytest.raises(RuntimeError):
        service.create_project_folder(
            LEAD, "proj_x", "fld_px", "项目文件夹", "req_3"
        )
    assert catalog.get_folder("fld_px") is None
    assert _events(audit_store, "authz.folder.created") == ()
