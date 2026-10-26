"""SQLite proof for S1 approval/move request storage (FR-RBAC-004,
ADR-019 D1/D3).

Proves request CRUD through the real SQLAlchemy catalog on SQLite,
including the partial-unique-index backstop: a second pending
request for the same document fails, while a closed request beside
a pending one succeeds. The production PostgreSQL proof lives in
the db_pg group.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from pivot.auth.ports import ApprovalRequest, MoveRequest
from pivot.db.base import Base
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.documents import DocumentVersion as VersionRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory

T0 = datetime(2026, 10, 26, 8, 0, tzinfo=UTC)


@pytest.fixture
def catalog() -> SqlAlchemyLibraryCatalog:
    engine = create_engine("sqlite://")
    for table in (
        "users",
        "libraries",
        "documents",
        "document_versions",
        "approval_requests",
        "move_requests",
    ):
        Base.metadata.tables[table].create(engine)
    sessions = session_factory(engine)
    with sessions() as session:
        session.add(
            UserRow(
                id="usr_admin", username="admin", password_hash="hash",
                role="admin", status="active",
            )
        )
        session.add(
            LibraryRow(
                id="dept_eng", name="技术部", kind="department",
                dept_id="dept_eng",
            )
        )
        session.add(
            DocumentRow(
                id="doc_a", title="t", created_by="usr_admin",
                library_id="unassigned",
            )
        )
        session.add(
            VersionRow(
                id="ver_a", document_id="doc_a",
                content_sha256="sha", storage_key="key",
            )
        )
        session.commit()
    return SqlAlchemyLibraryCatalog(sessions)


def _approval(request_id: str, status: str) -> ApprovalRequest:
    return ApprovalRequest(
        id=request_id, document_id="doc_a", version_id="ver_a",
        target_library_id="dept_eng", proposer="usr_admin",
        status=status, created_at=T0,
    )


def _move(request_id: str, status: str) -> MoveRequest:
    return MoveRequest(
        id=request_id, document_id="doc_a",
        source_library_id="dept_eng", target_library_id="dept_eng",
        proposer="usr_admin", status=status, created_at=T0,
    )


def test_FR_RBAC_004_p1_3_approval_request_crud(catalog) -> None:
    assert catalog.get_approval_request("ap_1") is None
    assert catalog.list_approval_requests("doc_a") == ()
    catalog.add_approval_request(_approval("ap_1", "pending"))
    row = catalog.get_approval_request("ap_1")
    assert row is not None and row.status == "pending"
    assert row.target_library_id == "dept_eng"
    assert [item.id for item in catalog.list_approval_requests("doc_a")] == [
        "ap_1"
    ]
    # set_ upserts: closing the request rewrites the status in place.
    catalog.set_approval_request(
        _approval("ap_1", "approved")
    )
    row = catalog.get_approval_request("ap_1")
    assert row is not None and row.status == "approved"


def test_FR_RBAC_004_p1_3_approval_request_pending_unique(catalog) -> None:
    catalog.add_approval_request(_approval("ap_1", "pending"))
    with pytest.raises(IntegrityError):
        catalog.add_approval_request(_approval("ap_2", "pending"))
    # A closed request beside the pending one is fine.
    catalog.add_approval_request(_approval("ap_3", "approved"))
    assert len(catalog.list_approval_requests("doc_a")) == 2
    # Reopening a closed row while another pending row exists fails
    # at the same index.
    with pytest.raises(IntegrityError):
        catalog.set_approval_request(_approval("ap_3", "pending"))


def test_FR_RBAC_004_p1_3_move_request_crud(catalog) -> None:
    assert catalog.get_move_request("mv_1") is None
    catalog.add_move_request(_move("mv_1", "pending"))
    row = catalog.get_move_request("mv_1")
    assert row is not None
    assert row.reconcile_status == "pending"
    assert row.reconcile_attempts == 0
    catalog.set_move_request(
        MoveRequest(
            id="mv_1", document_id="doc_a",
            source_library_id="dept_eng", target_library_id="dept_eng",
            proposer="usr_admin", status="approved", created_at=T0,
            reconcile_status="failed", reconcile_attempts=4,
        )
    )
    row = catalog.get_move_request("mv_1")
    assert row is not None and row.status == "approved"
    assert row.reconcile_status == "failed"
    assert row.reconcile_attempts == 4


def test_FR_RBAC_004_p1_3_move_request_pending_unique(catalog) -> None:
    catalog.add_move_request(_move("mv_1", "pending"))
    with pytest.raises(IntegrityError):
        catalog.add_move_request(_move("mv_2", "pending"))
    catalog.add_move_request(_move("mv_3", "rejected"))
    assert len(catalog.list_move_requests("doc_a")) == 2
