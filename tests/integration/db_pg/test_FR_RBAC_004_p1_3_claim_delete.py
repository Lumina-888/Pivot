"""Real PostgreSQL proof for S5 claim interlock and delete-cancel
(FR-RBAC-004, ADR-019 D4).

Same shapes as the unit proof, against the production stores whose
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
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.errors import AuthError
from pivot.auth.moves import MoveService
from pivot.auth.ports import ApprovalRequest, MoveRequest, Principal
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
from pivot.db.users import SqlAlchemyUserDirectory
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
    pg_session.add(
        LibraryRow(id="pub", name="公共库", kind="public")
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
    pg_session.add(
        DocumentRow(id="doc_b", title="t", created_by="usr_frank",
                    library_id="dept_eng")
    )
    pg_session.commit()
    pg_session.add(
        VersionRow(
            id="ver_a", document_id="doc_a",
            content_sha256="sha", storage_key="key",
            state="pending_approval",
        )
    )
    pg_session.add(
        VersionRow(
            id="ver_b", document_id="doc_b",
            content_sha256="sha", storage_key="key",
            state="ready",
        )
    )
    pg_session.commit()


def _assembly(pg_engine):
    sessions = session_factory(pg_engine)
    catalog = SqlAlchemyLibraryCatalog(sessions)
    documents = SqlAlchemyDocumentStore(sessions)
    versions = SqlAlchemyVersionStore(sessions)
    users = SqlAlchemyUserDirectory(sessions)
    audit_store = SqlAlchemyAuditStore(sessions)
    audits = AuditService(audit_store, _Clock())
    access = AccessControl(catalog, clock=_Clock())
    approvals = ApprovalService(
        store=catalog,
        documents=documents,
        versions=versions,
        objects=MemoryObjects(),
        access=access,
        audits=audits,
        clock=_Clock(),
        transaction=lambda: shared_session(sessions),
    )
    moves = MoveService(
        store=catalog,
        documents=documents,
        access=access,
        audits=audits,
        clock=_Clock(),
        approvals=approvals,
        transaction=lambda: shared_session(sessions),
    )
    departments = DepartmentAdminService(
        store=catalog,
        documents=documents,
        users=users,
        access=access,
        audits=audits,
        clock=_Clock(),
        transaction=lambda: shared_session(sessions),
    )
    departments.bind_pending_request_checks(
        pending_approval_for=approvals.pending_request_for,
        pending_move_for=moves.pending_request_for,
    )
    return catalog, documents, versions, audit_store, approvals, moves, departments


def _events(audit_store, action: str) -> tuple:
    return tuple(
        event for event in audit_store.list() if event.action == action
    )


def test_FR_RBAC_004_p1_3_claim_refuses_pending_pg(pg_session, pg_engine) -> None:
    _seed(pg_session)
    catalog, documents, _, _, approvals, _, departments = _assembly(pg_engine)
    catalog.add_approval_request(
        ApprovalRequest(
            id="req_a", document_id="doc_a", version_id="ver_a",
            target_library_id="dept_eng", proposer="usr_frank",
            status="pending", created_at=NOW,
        )
    )
    with pytest.raises(AuthError) as excinfo:
        departments.claim_document(ALICE, "doc_a", "dept_eng", "req_no")
    assert excinfo.value.code == "RESOURCE_FORBIDDEN"
    with pytest.raises(AuthError) as excinfo:
        departments.claim_document(ADMIN, "doc_a", "dept_eng", "req_no")
    assert excinfo.value.code == "RESOURCE_FORBIDDEN"
    assert documents.get("doc_a").library_id == "unassigned"


def test_FR_RBAC_004_p1_3_delete_cancels_pending_pg(pg_session, pg_engine) -> None:
    _seed(pg_session)
    catalog, _, _, audit_store, approvals, moves, _ = _assembly(pg_engine)
    catalog.add_approval_request(
        ApprovalRequest(
            id="req_a", document_id="doc_a", version_id="ver_a",
            target_library_id="dept_eng", proposer="usr_frank",
            status="pending", created_at=NOW,
        )
    )
    catalog.add_move_request(
        MoveRequest(
            id="mv_b", document_id="doc_b",
            source_library_id="dept_eng", target_library_id="pub",
            proposer="usr_alice", status="pending", created_at=NOW,
        )
    )
    cancelled_a = approvals.cancel_pending_for_document(
        "doc_a", "usr_admin", "req_del"
    )
    cancelled_b = moves.cancel_pending_for_document(
        "doc_b", "usr_admin", "req_del"
    )
    assert cancelled_a is not None and cancelled_a.status == "cancelled"
    assert cancelled_b is not None and cancelled_b.status == "cancelled"
    assert catalog.get_approval_request("req_a").status == "cancelled"
    assert catalog.get_move_request("mv_b").status == "cancelled"
    assert len(_events(audit_store, "doc.approval.cancelled")) == 1
    assert len(_events(audit_store, "doc.move.cancelled")) == 1
