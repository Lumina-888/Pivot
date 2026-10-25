"""SQLite proof for S4 same-transaction audit hardening (FR-RBAC-004, ADR-017 D4).

On the PostgreSQL path the department-admin mutation and its audit
writes share one session: a failed audit write rolls the mutation
back with it, including an event recorded before a later one fails
(the role-change plus renewal pair). The production PostgreSQL proof
lives in the db_pg group; this file proves the same mechanism against
SQLite using the real PostgreSQL-path store classes. The memory-path
compensation behavior is pinned here too: it must not change.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.ports import Library, Principal, UserAccount
from pivot.db.audit import SqlAlchemyAuditStore
from pivot.db.base import Base
from pivot.db.documents import SqlAlchemyDocumentStore
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.scoped import shared_session
from pivot.db.session import session_factory
from pivot.http.memory import InMemoryResources, InMemoryUserDirectory, MemoryDocuments
from pivot.security.rbac import AccessControl
from sqlalchemy import create_engine

NOW = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)
ADMIN = Principal("usr_admin", "admin", "admin", 0)


class _Clock:
    def __init__(self, now: datetime = NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class _Assembly:
    """Real PostgreSQL-path stores over SQLite, wired as bootstrap does."""

    def __init__(self) -> None:
        engine = create_engine("sqlite://")
        for table in (
            "users",
            "libraries",
            "memberships",
            "documents",
            "document_exceptions",
            "audit_events",
        ):
            Base.metadata.tables[table].create(engine)
        self.sessions = session_factory(engine)
        with self.sessions() as session:
            session.add(
                UserRow(
                    id="usr_admin", username="admin", password_hash="hash",
                    role="admin", status="active",
                )
            )
            session.add(
                UserRow(
                    id="usr_dave", username="dave", password_hash="hash",
                    role="user", status="active",
                )
            )
            session.add(
                LibraryRow(
                    id="dept_art", name="美术部", kind="department",
                    dept_id="dept_art",
                )
            )
            session.add(
                DocumentRow(
                    id="doc_a", title="t", created_by="usr_admin",
                    library_id="dept_art",
                )
            )
            session.add(
                DocumentRow(
                    id="doc_u", title="u", created_by="usr_admin",
                    library_id="unassigned",
                )
            )
            session.commit()
        self.catalog = SqlAlchemyLibraryCatalog(self.sessions)
        self.documents = SqlAlchemyDocumentStore(self.sessions)
        self.audit_store = SqlAlchemyAuditStore(self.sessions)
        self.audits = AuditService(self.audit_store, _Clock())
        self.access = AccessControl(self.catalog, clock=_Clock())
        self.users = InMemoryUserDirectory(
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
        self.service = DepartmentAdminService(
            store=self.catalog,
            documents=self.documents,
            users=self.users,
            access=self.access,
            audits=self.audits,
            clock=_Clock(),
            transaction=lambda: shared_session(self.sessions),
        )

    def events(self, action: str) -> tuple:
        return tuple(
            event for event in self.audit_store.list() if event.action == action
        )


@pytest.fixture
def assembly() -> _Assembly:
    return _Assembly()


def _fail_audits(monkeypatch, store) -> None:
    monkeypatch.setattr(store, "append", _boom)


def _boom(*args, **kwargs) -> None:
    raise RuntimeError("audit write failed")


def test_FR_RBAC_004_audit_failure_rolls_back_member_add(
    assembly, monkeypatch
) -> None:
    _fail_audits(monkeypatch, SqlAlchemyAuditStore)
    with pytest.raises(RuntimeError):
        assembly.service.add_member(
            ADMIN, "dept_art", "usr_dave", "reader", "req_1"
        )
    assert assembly.catalog.get_department_members("dept_art") == ()
    assert assembly.events("authz.permission_change") == ()


def test_FR_RBAC_004_audit_failure_rolls_back_department_create(
    assembly, monkeypatch
) -> None:
    _fail_audits(monkeypatch, SqlAlchemyAuditStore)
    with pytest.raises(RuntimeError):
        assembly.service.create_department(
            ADMIN, "dept_new", "新部门", "req_1"
        )
    assert assembly.catalog.get_library("dept_new") is None
    assert assembly.events("authz.department.create") == ()


def test_FR_RBAC_004_audit_failure_rolls_back_claim(
    assembly, monkeypatch
) -> None:
    _fail_audits(monkeypatch, SqlAlchemyAuditStore)
    with pytest.raises(RuntimeError):
        assembly.service.claim_document(ADMIN, "doc_u", "dept_art", "req_1")
    assert assembly.documents.get("doc_u").library_id == "unassigned"
    assert assembly.events("authz.library.claim") == ()


def test_FR_RBAC_004_audit_failure_rolls_back_exception_grant(
    assembly, monkeypatch
) -> None:
    _fail_audits(monkeypatch, SqlAlchemyAuditStore)
    with pytest.raises(RuntimeError):
        assembly.service.grant_exception(
            ADMIN, "doc_a", "req_1", target_user_id="usr_dave"
        )
    assert assembly.catalog.get_document_exceptions("doc_a") == ()
    assert assembly.events("authz.document_exception_granted") == ()


def test_FR_RBAC_004_audit_failure_keeps_exception_on_revoke(
    assembly, monkeypatch
) -> None:
    exception, _ = assembly.service.grant_exception(
        ADMIN, "doc_a", "req_1", target_user_id="usr_dave"
    )
    _fail_audits(monkeypatch, SqlAlchemyAuditStore)
    with pytest.raises(RuntimeError):
        assembly.service.revoke_exception(ADMIN, exception.id, "req_2")
    assert assembly.catalog.get_exception(exception.id) is not None
    assert assembly.events("authz.document_exception_revoked") == ()


def test_FR_RBAC_004_audit_failure_rolls_back_role_change_and_renewal(
    assembly, monkeypatch
) -> None:
    """Dual-event atomicity (the S2 residual S4 closes).

    A role change plus its renewal event share one transaction: when
    the audit write fails, neither event lands and the membership is
    untouched. Under the old compensation the first event would have
    persisted in the append-only audit.
    """
    assembly.service.add_member(
        ADMIN, "dept_art", "usr_dave", "reader", "req_1",
        expires_at=NOW + timedelta(days=30),
    )
    _fail_audits(monkeypatch, SqlAlchemyAuditStore)
    with pytest.raises(RuntimeError):
        assembly.service.set_member_role(
            ADMIN, "dept_art", "usr_dave", "editor", "req_2",
            expires_at=NOW + timedelta(days=60),
        )
    (member,) = assembly.catalog.get_department_members("dept_art")
    assert member.dept_role == "reader"
    expires = member.expires_at
    assert expires is not None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    assert expires == NOW + timedelta(days=30)
    # The successful add_member wrote one event; the failed role change
    # must not add a second one, nor its renewal event.
    assert len(assembly.events("authz.permission_change")) == 1
    assert assembly.events("authz.permission_renewed") == ()


def test_FR_RBAC_004_audit_failure_without_compensation_rolls_back(
    assembly, monkeypatch
) -> None:
    """A failed compensation must not leave an unaudited change (D4).

    The old path compensated after a failed audit write; if that
    compensation itself failed, the mutation persisted without a trace.
    The transaction path never compensates: the rollback below proves
    the compensation hook was not even attempted.
    """
    _fail_audits(monkeypatch, SqlAlchemyAuditStore)
    attempted: list = []

    def _recording(self, user_id: str, dept_id: str) -> None:
        attempted.append((user_id, dept_id))
        raise RuntimeError("compensation failed")

    monkeypatch.setattr(
        SqlAlchemyLibraryCatalog, "remove_membership", _recording
    )
    with pytest.raises(RuntimeError):
        assembly.service.add_member(
            ADMIN, "dept_art", "usr_dave", "reader", "req_1"
        )
    assert attempted == []
    assert assembly.catalog.get_department_members("dept_art") == ()
    assert assembly.events("authz.permission_change") == ()


def test_FR_RBAC_004_success_commits_member_and_audit_event(
    assembly,
) -> None:
    assembly.service.add_member(
        ADMIN, "dept_art", "usr_dave", "reader", "req_1"
    )
    (member,) = assembly.catalog.get_department_members("dept_art")
    assert member.user_id == "usr_dave"
    assert member.dept_role == "reader"
    (event,) = assembly.events("authz.permission_change")
    assert event.target == "usr_dave"


def test_FR_RBAC_004_success_commits_role_change_and_both_events(
    assembly,
) -> None:
    assembly.service.add_member(
        ADMIN, "dept_art", "usr_dave", "reader", "req_1",
        expires_at=NOW + timedelta(days=30),
    )
    updated = assembly.service.set_member_role(
        ADMIN, "dept_art", "usr_dave", "editor", "req_2",
        expires_at=NOW + timedelta(days=60),
    )
    assert updated.dept_role == "editor"
    assert len(assembly.events("authz.permission_change")) == 2
    (renewal,) = assembly.events("authz.permission_renewed")
    assert renewal.target == "usr_dave"


def test_FR_RBAC_004_memory_audit_failure_compensates_member_add(
    monkeypatch,
) -> None:
    """Memory path keeps compensation: no transaction scope, no change.

    The service is built exactly as the memory path builds it (no
    transaction scope), so a failed audit write reverts the mutation
    through the compensation hook instead of a transaction rollback.
    """
    resources = InMemoryResources()
    resources.libraries["dept_art"] = Library(
        id="dept_art", name="美术部", kind="department", dept_id="dept_art"
    )
    documents = MemoryDocuments()
    audit_store = AppendOnlyAuditStore()
    audits = AuditService(audit_store, _Clock())
    access = AccessControl(resources, clock=_Clock())
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
        store=resources,
        documents=documents,
        users=users,
        access=access,
        audits=audits,
        clock=_Clock(),
    )
    _fail_audits(monkeypatch, AppendOnlyAuditStore)
    with pytest.raises(RuntimeError):
        service.add_member(ADMIN, "dept_art", "usr_dave", "reader", "req_1")
    assert resources.get_department_members("dept_art") == ()
