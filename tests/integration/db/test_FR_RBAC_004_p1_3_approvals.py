"""SQLite proof for S2 publish approvals (FR-RBAC-004, ADR-019 D1/D6).

Proves the approval service through the real SQLAlchemy stores on
SQLite: the approve decision rewrites the document library, moves
the version to uploaded, dispatches ingest, and writes the approval
audit event; and an audit-write failure rolls the decision, the
library rewrite, and the version transition back together (the
ADR-017 D4 same-transaction rule, mirrored on PostgreSQL in the
db_pg group). Seeding commits in order: users, then library and
membership rows, then documents and versions.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from tests.unit.documents.fakes import MemoryObjects

from pivot.audit.service import AuditService
from pivot.auth.approvals import ApprovalService
from pivot.auth.ports import ApprovalRequest, Principal
from pivot.db.audit import SqlAlchemyAuditStore
from pivot.db.base import Base
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

T0 = datetime(2026, 10, 26, 8, 0, tzinfo=UTC)
ALICE = Principal("usr_alice", "alice", "user", 1)


class _Clock:
    def now(self) -> datetime:
        return T0


@pytest.fixture
def assembly():
    engine = create_engine("sqlite://")
    for table in (
        "users",
        "libraries",
        "memberships",
        "documents",
        "document_versions",
        "approval_requests",
        "audit_events",
    ):
        Base.metadata.tables[table].create(engine)
    sessions = session_factory(engine)
    with sessions() as session:
        session.add(
            UserRow(
                id="usr_alice", username="alice", password_hash="hash",
                role="user", status="active",
            )
        )
        session.add(
            UserRow(
                id="usr_frank", username="frank", password_hash="hash",
                role="user", status="active",
            )
        )
        session.commit()
        session.add(
            LibraryRow(
                id="dept_eng", name="技术部", kind="department",
                dept_id="dept_eng",
            )
        )
        session.add(
            MembershipRow(
                user_id="usr_alice", dept_id="dept_eng",
                dept_role="dept_admin", granted_by="usr_admin",
            )
        )
        session.commit()
        session.add(
            DocumentRow(id="doc_a", title="t", created_by="usr_frank",
                        library_id="unassigned")
        )
        session.commit()
        session.add(
            VersionRow(
                id="ver_a", document_id="doc_a",
                content_sha256="sha", storage_key="key",
                state="pending_approval",
            )
        )
        session.commit()
    catalog = SqlAlchemyLibraryCatalog(sessions)
    documents = SqlAlchemyDocumentStore(sessions)
    versions = SqlAlchemyVersionStore(sessions)
    audit_store = SqlAlchemyAuditStore(sessions)
    audits = AuditService(audit_store, _Clock())
    dispatched: list = []
    service = ApprovalService(
        store=catalog,
        documents=documents,
        versions=versions,
        objects=MemoryObjects(),
        access=AccessControl(catalog, clock=_Clock()),
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
        status="pending", created_at=T0,
    )


def test_FR_RBAC_004_p1_3_approve_flow_sqlite(assembly) -> None:
    catalog, documents, versions, audit_store, service, dispatched = assembly
    catalog.add_approval_request(_request())
    decided = service.approve(ALICE, "req_a", "req_approve")
    assert decided.status == "approved"
    assert documents.get("doc_a").library_id == "dept_eng"
    assert versions.get("ver_a").state == "uploaded"
    assert dispatched == [("ver_a", "usr_alice")]
    approved = tuple(
        event for event in audit_store.list()
        if event.action == "authz.approval.approved"
    )
    assert len(approved) == 1
    assert approved[0].metadata["dept_id"] == "dept_eng"


def test_FR_RBAC_004_p1_3_approve_audit_failure_rolls_back_sqlite(
    assembly, monkeypatch
) -> None:
    catalog, documents, versions, _, service, dispatched = assembly
    catalog.add_approval_request(_request())

    def _boom(*args, **kwargs) -> None:
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(SqlAlchemyAuditStore, "append", _boom)
    with pytest.raises(RuntimeError):
        service.approve(ALICE, "req_a", "req_approve")
    assert catalog.get_approval_request("req_a").status == "pending"
    assert documents.get("doc_a").library_id == "unassigned"
    assert versions.get("ver_a").state == "pending_approval"
    assert dispatched == []
