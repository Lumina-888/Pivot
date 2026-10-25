"""Real PostgreSQL P1-2 catalog proof (FR-RBAC-004, ADR-017 D1/D2).

The P1-2 migration and the SqlAlchemyLibraryCatalog extensions were
proven on SQLite in the unit groups. These tests close the gap the
same way the P1-1 db_pg file did: they run the production store
against a real PostgreSQL whose schema comes from the Alembic
migrations, and assert the wiring itself — the expires_at round
trip, exception CRUD, and the single-target CHECK constraint. The
full matrix stays covered by the unit tests.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pivot.auth.ports import DocumentException, Membership
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from sqlalchemy.exc import IntegrityError


def _seed(pg_session) -> None:
    # Libraries are migration-seeded (pub/unassigned survive for the
    # session's first test only), so library seeds must be idempotent
    # like the P1-1 db_pg helpers. Users and documents are never
    # migration-seeded, so plain inserts are safe.
    pg_session.add(
        UserRow(
            id="usr_admin",
            username="admin",
            password_hash="hash",
            role="admin",
            status="active",
        )
    )
    pg_session.add(
        UserRow(
            id="usr_alice",
            username="alice",
            password_hash="hash",
            role="user",
            status="active",
        )
    )
    if pg_session.get(LibraryRow, "pub") is None:
        pg_session.add(LibraryRow(id="pub", name="公共库", kind="public"))
    if pg_session.get(LibraryRow, "dept_art") is None:
        pg_session.add(
            LibraryRow(
                id="dept_art",
                name="美术部",
                kind="department",
                dept_id="dept_art",
            )
        )
    pg_session.add(DocumentRow(id="doc_a", title="t", created_by="usr_admin"))
    pg_session.commit()


def test_FR_RBAC_004_pg_catalog_membership_expires_at_round_trip(
    pg_engine, pg_session
) -> None:
    _seed(pg_session)
    catalog = SqlAlchemyLibraryCatalog(session_factory(pg_engine))
    expires_at = datetime(2026, 12, 24, tzinfo=timezone.utc)
    catalog.add_membership(
        Membership(
            user_id="usr_alice",
            dept_id="dept_art",
            dept_role="reader",
            granted_by="usr_admin",
            expires_at=expires_at,
        )
    )
    stored = catalog.get_memberships("usr_alice")
    assert len(stored) == 1
    assert stored[0].expires_at == expires_at


def test_FR_RBAC_004_pg_catalog_exception_crud(pg_engine, pg_session) -> None:
    _seed(pg_session)
    catalog = SqlAlchemyLibraryCatalog(session_factory(pg_engine))
    catalog.add_exception(
        DocumentException(
            id="exc_personal",
            document_id="doc_a",
            target_user_id="usr_alice",
            granted_by="usr_admin",
            reason="cross-team review",
        )
    )
    catalog.add_exception(
        DocumentException(
            id="exc_dept",
            document_id="doc_a",
            target_dept_id="dept_art",
            granted_by="usr_admin",
            reason="joint project",
        )
    )
    by_doc = catalog.get_document_exceptions("doc_a")
    assert [item.id for item in by_doc] == ["exc_dept", "exc_personal"]
    assert [item.id for item in catalog.get_exceptions_for_user("usr_alice")] == [
        "exc_personal"
    ]
    catalog.remove_exception("exc_personal")
    assert [item.id for item in catalog.get_document_exceptions("doc_a")] == [
        "exc_dept"
    ]


def test_FR_RBAC_004_pg_catalog_exception_rejects_both_targets(
    pg_engine, pg_session
) -> None:
    _seed(pg_session)
    catalog = SqlAlchemyLibraryCatalog(session_factory(pg_engine))
    with pytest.raises(IntegrityError):
        catalog.add_exception(
            DocumentException(
                id="exc_bad",
                document_id="doc_a",
                target_user_id="usr_alice",
                target_dept_id="dept_art",
                granted_by="usr_admin",
            )
        )
