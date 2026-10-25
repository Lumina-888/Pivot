"""Real PostgreSQL proof for the S5 claim audit surface (FR-RBAC-004,
ADR-017 D3).

Claim on the production store, then a sync_failed record, then the
department-scoped audit view: the target department sees it, another
department does not. Skipped without PIVOT_TEST_PG_URL.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pivot.audit.ports import Actor
from pivot.audit.service import AuditService
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.ports import Principal
from pivot.db.audit import SqlAlchemyAuditStore
from pivot.db.documents import SqlAlchemyDocumentStore
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from pivot.db.users import SqlAlchemyUserDirectory
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
ART_ADMIN = Actor(user_id="usr_carol", username="carol", role="user")
ENG_ADMIN = Actor(user_id="usr_alice", username="alice", role="user")


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


def _seed(pg_session) -> None:
    # documents.created_by references users.id: the creator row must
    # exist, or PostgreSQL rejects the document insert (the CI #240
    # lesson — SQLite does not enforce this).
    pg_session.add(
        UserRow(
            id="usr_admin", username="admin", password_hash="hash",
            role="admin", status="active",
        )
    )
    pg_session.add(
        LibraryRow(
            id="dept_art", name="美术部", kind="department",
            dept_id="dept_art",
        )
    )
    pg_session.add(DocumentRow(id="doc_a", title="t", created_by="usr_admin"))


def test_FR_RBAC_004_claim_sync_failed_event_scoped_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    pg_session.commit()
    sessions = session_factory(pg_engine)
    audits = AuditService(SqlAlchemyAuditStore(sessions), _Clock())
    service = DepartmentAdminService(
        store=SqlAlchemyLibraryCatalog(sessions),
        documents=SqlAlchemyDocumentStore(sessions),
        users=SqlAlchemyUserDirectory(sessions),
        access=AccessControl(SqlAlchemyLibraryCatalog(sessions)),
        audits=audits,
        clock=_Clock(),
    )
    claimed = service.claim_document(ADMIN, "doc_a", "dept_art", "req_claim")
    assert claimed.library_id == "dept_art"
    audits.record(
        actor="usr_admin",
        action="authz.library.sync_failed",
        target="doc_a",
        result="failed",
        request_id="req_sync",
        metadata={
            "dept_id": "dept_art",
            "from_library": "unassigned",
            "to_library": "dept_art",
            "attempts": 4,
        },
    )
    art_view = audits.list_department_events(
        ART_ADMIN, frozenset({"dept_art"}), "req_view_art"
    )
    assert any(
        item["action"] == "authz.library.sync_failed" and item["target"] == "doc_a"
        for item in art_view["items"]
    )
    eng_view = audits.list_department_events(
        ENG_ADMIN, frozenset({"dept_eng"}), "req_view_eng"
    )
    assert all(
        not (
            item["action"] == "authz.library.sync_failed"
            and item["target"] == "doc_a"
        )
        for item in eng_view["items"]
    )
