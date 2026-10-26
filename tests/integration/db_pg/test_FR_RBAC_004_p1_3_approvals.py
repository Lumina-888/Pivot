"""Real PostgreSQL proof for S2 publish approvals (FR-RBAC-004,
ADR-019 D1/D6).

Same shapes as the SQLite proof, against the production stores whose
schema comes from the Alembic migrations. Skipped without
PIVOT_TEST_PG_URL. Seeding commits in the CI #240/#256 order: users
first, then library rows, then documents, versions, and requests, so
every foreign-key target exists before its referrer is inserted.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pivot.audit.service import AuditService
from pivot.auth.approvals import ApprovalService
from pivot.auth.errors import AuthError
from pivot.auth.ports import ApprovalRequest, Principal
from pivot.db.audit import SqlAlchemyAuditStore
from pivot.db.documents import SqlAlchemyDocumentStore, SqlAlchemyVersionStore
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.documents import DocumentVersion as VersionRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import Membership as MembershipRow
from pivot.db.models.identity import User as UserRow
from pivot.db.scoped import shared_session
from pivot.db.session import session_factory
from pivot.security.rbac import AccessControl

from tests.unit.documents.fakes import MemoryObjects

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
ADMIN = Principal("usr_admin", "admin", "admin", 0)
ALICE = Principal("usr_alice", "alice", "user", 1)
FRANK = Principal("usr_frank", "frank", "user", 1)


class _Clock:
    def now(self) -> datetime:
        return NOW


def _seed(pg_session) -> None:
    for user_id, username, role in (
        ("usr_admin", "admin", "admin"),
        ("usr_alice", "alice", "user"),
        ("usr_frank", "frank", "user"),
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
        MembershipRow(
            user_id="usr_alice", dept_id="dept_eng",
            dept_role="dept_admin", granted_by="usr_admin",
        )
    )
    pg_session.commit()
    pg_session.add(
        DocumentRow(id="doc_a", title="t", created_by="usr_frank",
                    library_id="unassigned")
    )
    pg_session.commit()
    pg_session.add(
        VersionRow(
            id="ver_a", document_id="doc_a",
            content_sha256="sha", storage_key="key",
            state="pending_approval",
        )
    )
    pg_session.commit()


def _assembly(pg_engine):
    sessions = session_factory(pg_engine)
    catalog = SqlAlchemyLibraryCatalog(sessions)
    documents = SqlAlchemyDocumentStore(sessions)
    versions = SqlAlchemyVersionStore(sessions)
    audit_store = SqlAlchemyAuditStore(sessions)
    audits = AuditService(audit_store, _Clock())
    access = AccessControl(catalog, clock=_Clock())
    dispatched: list = []
    service = ApprovalService(
        store=catalog,
        documents=documents,
        versions=versions,
        objects=MemoryObjects(),
        access=access,
        audits=audits,
        clock=_Clock(),
        transaction=lambda: shared_session(sessions),
        ingest=lambda vid, rid, actor: dispatched.append((vid, actor)),
    )
    return catalog, documents, versions, audit_store, service, dispatched


def _request() -> ApprovalRequest:
    return ApprovalRequest(
        id="req_a", document_id="doc_a", version_id="ver_a",
        target_library_id="dept_eng", proposer="usr_frank",
        status="pending", created_at=NOW,
    )


def _events(audit_store, action: str) -> tuple:
    return tuple(
        event for event in audit_store.list() if event.action == action
    )


def test_FR_RBAC_004_p1_3_approve_flow_pg(pg_session, pg_engine) -> None:
    _seed(pg_session)
    catalog, documents, versions, audit_store, service, dispatched = _assembly(
        pg_engine
    )
    catalog.add_approval_request(_request())
    decided = service.approve(ALICE, "req_a", "req_approve")
    assert decided.status == "approved"
    assert decided.decided_by == "usr_alice"
    assert documents.get("doc_a").library_id == "dept_eng"
    assert versions.get("ver_a").state == "uploaded"
    assert dispatched == [("ver_a", "usr_alice")]
    approved = _events(audit_store, "authz.approval.approved")
    assert len(approved) == 1
    assert approved[0].metadata["dept_id"] == "dept_eng"


def test_FR_RBAC_004_p1_3_approve_audit_failure_rolls_back_pg(
    pg_session, pg_engine, monkeypatch
) -> None:
    _seed(pg_session)
    catalog, documents, versions, audit_store, service, dispatched = _assembly(
        pg_engine
    )
    catalog.add_approval_request(_request())

    def _boom(*args, **kwargs) -> None:
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(SqlAlchemyAuditStore, "append", _boom)
    with pytest.raises(RuntimeError):
        service.approve(ALICE, "req_a", "req_approve")
    # ADR-017 D4 same-transaction: the decision, the library
    # rewrite, and the version transition all roll back together,
    # and no ingest is dispatched for a refused approval.
    assert catalog.get_approval_request("req_a").status == "pending"
    assert documents.get("doc_a").library_id == "unassigned"
    assert versions.get("ver_a").state == "pending_approval"
    assert dispatched == []


def test_FR_RBAC_004_p1_3_approve_delegated_pg(pg_session, pg_engine) -> None:
    _seed(pg_session)
    catalog, _, _, audit_store, service, _ = _assembly(pg_engine)
    catalog.add_approval_request(_request())
    # O2: a super admin deciding a department queue acts by
    # delegation, recorded alongside the ordinary approval event.
    service.approve(ADMIN, "req_a", "req_approve")
    assert len(_events(audit_store, "authz.approval.approved")) == 1
    delegated = _events(audit_store, "authz.approval.delegated")
    assert len(delegated) == 1
    assert delegated[0].actor == "usr_admin"
    # A non-approver still sees nothing, even on PostgreSQL.
    with pytest.raises(AuthError) as excinfo:
        service.approve(FRANK, "req_a", "req_no")
    assert excinfo.value.code == "AUTH_FORBIDDEN"
