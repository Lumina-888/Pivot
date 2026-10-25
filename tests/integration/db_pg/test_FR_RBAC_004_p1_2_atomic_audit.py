"""Real PostgreSQL proof for S4 same-transaction audit hardening (FR-RBAC-004, ADR-017 D4).

Same shapes as the SQLite proof, against the production store whose
schema comes from the Alembic migrations. Skipped without
PIVOT_TEST_PG_URL. The dual-event test fails the renewal audit write
only: under the old compensation the first event would persist in the
append-only audit, while the shared transaction rolls both events and
the membership change back together.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pivot.audit.service import AuditService
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.ports import Principal, UserAccount
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
    # documents.created_by references users.id: the admin creator row
    # must exist, or PostgreSQL rejects the document insert (the S3
    # CI #240 lesson: SQLite does not enforce this foreign key).
    pg_session.add(
        UserRow(
            id="usr_admin", username="admin", password_hash="hash",
            role="admin", status="active",
        )
    )
    pg_session.add(
        UserRow(
            id="usr_dave", username="dave", password_hash="hash",
            role="user", status="active",
        )
    )
    if pg_session.get(LibraryRow, "dept_art") is None:
        pg_session.add(
            LibraryRow(
                id="dept_art", name="美术部", kind="department",
                dept_id="dept_art",
            )
        )
    pg_session.add(
        DocumentRow(
            id="doc_a", title="t", created_by="usr_admin",
            library_id="dept_art",
        )
    )
    pg_session.add(
        DocumentRow(
            id="doc_u", title="u", created_by="usr_admin",
            library_id="unassigned",
        )
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


def _boom(*args, **kwargs) -> None:
    raise RuntimeError("audit write failed")


def _events(audit_store, action: str) -> tuple:
    return tuple(
        event for event in audit_store.list() if event.action == action
    )


def test_FR_RBAC_004_audit_failure_rolls_back_member_add_pg(
    pg_session, pg_engine, monkeypatch
) -> None:
    _seed(pg_session)
    pg_session.commit()
    catalog, _, audit_store, service = _assembly(pg_engine)
    monkeypatch.setattr(SqlAlchemyAuditStore, "append", _boom)
    with pytest.raises(RuntimeError):
        service.add_member(ADMIN, "dept_art", "usr_dave", "reader", "req_1")
    assert catalog.get_department_members("dept_art") == ()
    assert _events(audit_store, "authz.permission_change") == ()


def test_FR_RBAC_004_audit_failure_rolls_back_role_change_and_renewal_pg(
    pg_session, pg_engine, monkeypatch
) -> None:
    _seed(pg_session)
    pg_session.commit()
    catalog, _, audit_store, service = _assembly(pg_engine)
    service.add_member(
        ADMIN, "dept_art", "usr_dave", "reader", "req_1",
        expires_at=NOW + timedelta(days=30),
    )
    original = SqlAlchemyAuditStore.append

    def _selective(self, event):
        if event.action == "authz.permission_renewed":
            raise RuntimeError("renewal audit failed")
        return original(self, event)

    monkeypatch.setattr(SqlAlchemyAuditStore, "append", _selective)
    with pytest.raises(RuntimeError):
        service.set_member_role(
            ADMIN, "dept_art", "usr_dave", "editor", "req_2",
            expires_at=NOW + timedelta(days=60),
        )
    (member,) = catalog.get_department_members("dept_art")
    assert member.dept_role == "reader"
    expires = member.expires_at
    assert expires is not None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    assert expires == NOW + timedelta(days=30)
    assert len(_events(audit_store, "authz.permission_change")) == 1
    assert _events(audit_store, "authz.permission_renewed") == ()


def test_FR_RBAC_004_audit_failure_rolls_back_claim_pg(
    pg_session, pg_engine, monkeypatch
) -> None:
    _seed(pg_session)
    pg_session.commit()
    _, documents, audit_store, service = _assembly(pg_engine)
    monkeypatch.setattr(SqlAlchemyAuditStore, "append", _boom)
    with pytest.raises(RuntimeError):
        service.claim_document(ADMIN, "doc_u", "dept_art", "req_1")
    assert documents.get("doc_u").library_id == "unassigned"
    assert _events(audit_store, "authz.library.claim") == ()


def test_FR_RBAC_004_success_commits_member_and_audit_event_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    pg_session.commit()
    catalog, _, audit_store, service = _assembly(pg_engine)
    service.add_member(ADMIN, "dept_art", "usr_dave", "reader", "req_1")
    (member,) = catalog.get_department_members("dept_art")
    assert member.user_id == "usr_dave"
    assert member.dept_role == "reader"
    (event,) = _events(audit_store, "authz.permission_change")
    assert event.target == "usr_dave"
