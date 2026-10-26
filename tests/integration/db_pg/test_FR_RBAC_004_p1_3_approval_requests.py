"""Real PostgreSQL proof for S1 approval/move requests (FR-RBAC-004,
ADR-019 D1/D3).

Same shapes as the SQLite proof, against the production store whose
schema comes from the Alembic migrations. Skipped without
PIVOT_TEST_PG_URL. Seeding commits in the CI #240/#256 order: users
first, then library rows, then documents, versions, and requests, so
every foreign-key target exists before its referrer is inserted.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pivot.auth.ports import ApprovalRequest, MoveRequest
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.documents import DocumentVersion as VersionRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from sqlalchemy.exc import IntegrityError

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)


def _seed(pg_session) -> None:
    pg_session.add(
        UserRow(
            id="usr_admin", username="admin", password_hash="hash",
            role="admin", status="active",
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
        DocumentRow(id="doc_a", title="t", created_by="usr_admin",
                    library_id="unassigned")
    )
    pg_session.commit()
    pg_session.add(
        VersionRow(
            id="ver_a", document_id="doc_a",
            content_sha256="sha", storage_key="key",
        )
    )
    pg_session.commit()


def _catalog(pg_engine) -> SqlAlchemyLibraryCatalog:
    return SqlAlchemyLibraryCatalog(session_factory(pg_engine))


def _approval(request_id: str, status: str) -> ApprovalRequest:
    return ApprovalRequest(
        id=request_id, document_id="doc_a", version_id="ver_a",
        target_library_id="dept_eng", proposer="usr_admin",
        status=status, created_at=NOW,
    )


def _move(request_id: str, status: str) -> MoveRequest:
    return MoveRequest(
        id=request_id, document_id="doc_a",
        source_library_id="dept_eng", target_library_id="dept_eng",
        proposer="usr_admin", status=status, created_at=NOW,
    )


def test_FR_RBAC_004_p1_3_approval_request_crud_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    catalog = _catalog(pg_engine)
    assert catalog.get_approval_request("ap_1") is None
    catalog.add_approval_request(_approval("ap_1", "pending"))
    row = catalog.get_approval_request("ap_1")
    assert row is not None and row.status == "pending"
    catalog.set_approval_request(_approval("ap_1", "approved"))
    assert catalog.get_approval_request("ap_1").status == "approved"
    assert [item.id for item in catalog.list_approval_requests("doc_a")] == [
        "ap_1"
    ]


def test_FR_RBAC_004_p1_3_approval_request_pending_unique_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    catalog = _catalog(pg_engine)
    catalog.add_approval_request(_approval("ap_1", "pending"))
    with pytest.raises(IntegrityError):
        catalog.add_approval_request(_approval("ap_2", "pending"))


def test_FR_RBAC_004_p1_3_move_request_crud_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    catalog = _catalog(pg_engine)
    catalog.add_move_request(_move("mv_1", "pending"))
    row = catalog.get_move_request("mv_1")
    assert row is not None
    assert row.reconcile_status == "pending"
    assert row.reconcile_attempts == 0
    with pytest.raises(IntegrityError):
        catalog.add_move_request(_move("mv_2", "pending"))
    catalog.set_move_request(
        MoveRequest(
            id="mv_1", document_id="doc_a",
            source_library_id="dept_eng", target_library_id="dept_eng",
            proposer="usr_admin", status="approved", created_at=NOW,
            reconcile_status="failed", reconcile_attempts=4,
        )
    )
    row = catalog.get_move_request("mv_1")
    assert row is not None and row.reconcile_status == "failed"
    assert row.reconcile_attempts == 4
