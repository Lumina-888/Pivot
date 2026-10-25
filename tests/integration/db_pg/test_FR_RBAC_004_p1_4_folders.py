"""Real PostgreSQL proof for the S2 folder store (FR-RBAC-004, ADR-018 D3).

Same shapes as the SQLite proof, against the production store whose
schema comes from the Alembic migrations. Skipped without
PIVOT_TEST_PG_URL. The service tests prove the S4 same-transaction
rule for folders: a failed audit write rolls the folder mutation back
with it, instead of landing without its trace.
"""

from __future__ import annotations

from datetime import datetime, timezone

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


class _Clock:
    def now(self) -> datetime:
        return NOW


def _seed(pg_session) -> None:
    # Users first: folder_memberships references users.id, and
    # documents.created_by references it too (the S3 CI #240 lesson:
    # SQLite does not enforce these foreign keys, PostgreSQL does).
    pg_session.add(
        UserRow(
            id="usr_admin", username="admin", password_hash="hash",
            role="admin", status="active",
        )
    )
    pg_session.add(
        UserRow(
            id="usr_alice", username="alice", password_hash="hash",
            role="user", status="active",
        )
    )
    pg_session.add(
        UserRow(
            id="usr_dave", username="dave", password_hash="hash",
            role="user", status="active",
        )
    )
    if pg_session.get(LibraryRow, "dept_eng") is None:
        pg_session.add(
            LibraryRow(
                id="dept_eng", name="技术部", kind="department",
                dept_id="dept_eng",
            )
        )
    pg_session.add(
        DocumentRow(id="doc_a", title="t", created_by="usr_admin",
                    library_id="dept_eng")
    )


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
                id="usr_admin", username="admin", password_hash="hash",
                role="admin", status="active",
            ),
            UserAccount(
                id="usr_alice", username="alice", password_hash="hash",
                role="user", status="active",
            ),
            UserAccount(
                id="usr_dave", username="dave", password_hash="hash",
                role="user", status="active",
            ),
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


def test_FR_RBAC_004_folder_crud_and_members_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    pg_session.commit()
    catalog, _, _, _ = _assembly(pg_engine)
    assert catalog.get_folder("fld_a") is None
    catalog.create_folder(
        Folder(id="fld_a", library_id="dept_eng", name="文件夹 A")
    )
    assert catalog.get_folder("fld_a").name == "文件夹 A"
    assert [row.id for row in catalog.list_folders("dept_eng")] == ["fld_a"]
    catalog.add_folder_member(
        FolderMembership(
            folder_id="fld_a", user_id="usr_dave", folder_role="reader",
            granted_by="usr_admin",
        )
    )
    (member,) = catalog.get_folder_members("fld_a")
    assert member.folder_role == "reader"
    catalog.set_folder(
        Folder(id="fld_a", library_id="dept_eng", name="新名字")
    )
    assert catalog.get_folder("fld_a").name == "新名字"
    (kept,) = catalog.get_folder_members("fld_a")
    assert kept.folder_role == "reader"
    catalog.delete_folder("fld_a")
    assert catalog.get_folder("fld_a") is None
    assert catalog.get_folder_members("fld_a") == ()


def test_FR_RBAC_004_folder_service_flow_and_visibility_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    pg_session.commit()
    catalog, documents, audit_store, service = _assembly(pg_engine)
    service.add_member(ADMIN, "dept_eng", "usr_alice", "dept_admin", "req_1")
    # Folder members come only from department members.
    service.add_member(ADMIN, "dept_eng", "usr_dave", "reader", "req_1b")
    folder, created = service.create_folder(
        ADMIN, "dept_eng", "fld_a", "文件夹 A", "req_2"
    )
    assert created is True
    member, created = service.add_folder_member(
        ADMIN, "dept_eng", "fld_a", "usr_dave", "reader", "req_3"
    )
    assert created is True
    moved, changed = service.move_document_to_folder(
        ADMIN, "dept_eng", "doc_a", "fld_a", "req_4"
    )
    assert changed is True
    assert moved.folder_id == "fld_a"
    assert documents.get("doc_a").folder_id == "fld_a"
    # The SQL catalog read path behind AccessControl sees the folder
    # for both the member and the department admin.
    access = AccessControl(catalog, clock=_Clock())
    dave = Principal("usr_dave", "dave", "user", 1)
    assert access.visible_folder_ids(dave) == frozenset({"fld_a"})
    alice = Principal("usr_alice", "alice", "user", 1)
    assert access.visible_folder_ids(alice) == frozenset({"fld_a"})
    assert len(_events(audit_store, "authz.folder.created")) == 1
    assert len(_events(audit_store, "authz.folder.member_added")) == 1
    assert len(_events(audit_store, "authz.folder.document_added")) == 1
    # A non-empty folder cannot be deleted, on PostgreSQL either.
    with pytest.raises(AuthError) as excinfo:
        service.delete_folder(ADMIN, "dept_eng", "fld_a", "req_5")
    assert excinfo.value.code == "RESOURCE_FORBIDDEN"
    assert catalog.get_folder("fld_a") is not None


def test_FR_RBAC_004_folder_audit_failure_rolls_back_create_pg(
    pg_session, pg_engine, monkeypatch
) -> None:
    _seed(pg_session)
    pg_session.commit()
    catalog, _, audit_store, service = _assembly(pg_engine)

    def _boom(*args, **kwargs) -> None:
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(SqlAlchemyAuditStore, "append", _boom)
    with pytest.raises(RuntimeError):
        service.create_folder(
            ADMIN, "dept_eng", "fld_a", "文件夹 A", "req_1"
        )
    assert catalog.get_folder("fld_a") is None
    assert _events(audit_store, "authz.folder.created") == ()


def test_FR_RBAC_004_folder_audit_failure_rolls_back_move_pg(
    pg_session, pg_engine, monkeypatch
) -> None:
    _seed(pg_session)
    pg_session.commit()
    catalog, documents, audit_store, service = _assembly(pg_engine)
    service.create_folder(ADMIN, "dept_eng", "fld_a", "文件夹 A", "req_1")

    def _boom(*args, **kwargs) -> None:
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(SqlAlchemyAuditStore, "append", _boom)
    with pytest.raises(RuntimeError):
        service.move_document_to_folder(
            ADMIN, "dept_eng", "doc_a", "fld_a", "req_2"
        )
    assert documents.get("doc_a").folder_id is None
    assert _events(audit_store, "authz.folder.document_added") == ()
