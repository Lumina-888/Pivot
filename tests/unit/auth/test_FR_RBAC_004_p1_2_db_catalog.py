"""Database-backed P1-2 catalog for FR-RBAC-004 (ADR-017 D1/D2).

Proves the SqlAlchemyLibraryCatalog extensions against SQLite: the
memberships.expires_at round trip and the document_exceptions
read/write methods, including the single-target CHECK constraint.
The production PostgreSQL proof lives in the db_pg group; this file
does not re-prove it.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pivot.auth.ports import DocumentException, Membership
from pivot.db.base import Base
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError


def _as_utc(moment: datetime | None) -> datetime | None:
    """SQLite drops tzinfo on DateTime(timezone=True) round trips.

    Normalize a stored moment to UTC-aware before comparing, so the
    same assertion shape works wherever the dialect preserves tz.
    """
    if moment is None:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


@pytest.fixture
def catalog() -> SqlAlchemyLibraryCatalog:
    engine = create_engine("sqlite://")
    for table in (
        "users",
        "libraries",
        "memberships",
        "documents",
        "document_exceptions",
    ):
        Base.metadata.tables[table].create(engine)
    sessions = session_factory(engine)
    with sessions() as session:
        session.add(
            UserRow(
                id="usr_admin",
                username="admin",
                password_hash="hash",
                role="admin",
                status="active",
            )
        )
        session.add(
            UserRow(
                id="usr_alice",
                username="alice",
                password_hash="hash",
                role="user",
                status="active",
            )
        )
        session.add(LibraryRow(id="pub", name="公共库", kind="public"))
        session.add(
            LibraryRow(
                id="dept_art", name="美术部", kind="department", dept_id="dept_art"
            )
        )
        session.add(
            DocumentRow(id="doc_a", title="t", created_by="usr_admin")
        )
        session.commit()
    return SqlAlchemyLibraryCatalog(sessions)


def test_FR_RBAC_004_db_catalog_membership_expires_at_round_trip(
    catalog: SqlAlchemyLibraryCatalog,
) -> None:
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
    assert _as_utc(stored[0].expires_at) == expires_at
    catalog.set_membership(
        Membership(
            user_id="usr_alice",
            dept_id="dept_art",
            dept_role="editor",
            granted_by="usr_admin",
            expires_at=None,
        )
    )
    stored = catalog.get_memberships("usr_alice")
    assert stored[0].dept_role == "editor"
    assert stored[0].expires_at is None


def test_FR_RBAC_004_db_catalog_exception_crud(
    catalog: SqlAlchemyLibraryCatalog,
) -> None:
    personal = DocumentException(
        id="exc_personal",
        document_id="doc_a",
        target_user_id="usr_alice",
        granted_by="usr_admin",
        reason="cross-team review",
    )
    dept_grant = DocumentException(
        id="exc_dept",
        document_id="doc_a",
        target_dept_id="dept_art",
        granted_by="usr_admin",
        reason="joint project",
        expires_at=datetime(2026, 12, 24, tzinfo=timezone.utc),
    )
    catalog.add_exception(personal)
    catalog.add_exception(dept_grant)
    by_doc = catalog.get_document_exceptions("doc_a")
    assert [item.id for item in by_doc] == ["exc_dept", "exc_personal"]
    assert by_doc[1].reason == "cross-team review"
    assert _as_utc(by_doc[0].expires_at) == datetime(
        2026, 12, 24, tzinfo=timezone.utc
    )
    assert catalog.get_document_exceptions("doc_missing") == ()
    by_user = catalog.get_exceptions_for_user("usr_alice")
    assert [item.id for item in by_user] == ["exc_personal"]
    catalog.remove_exception("exc_personal")
    assert [item.id for item in catalog.get_document_exceptions("doc_a")] == [
        "exc_dept"
    ]
    catalog.remove_exception("exc_missing")  # no-op, no raise


def test_FR_RBAC_004_db_catalog_exception_rejects_both_targets(
    catalog: SqlAlchemyLibraryCatalog,
) -> None:
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


def test_FR_RBAC_004_db_catalog_exception_rejects_no_target(
    catalog: SqlAlchemyLibraryCatalog,
) -> None:
    with pytest.raises(IntegrityError):
        catalog.add_exception(
            DocumentException(
                id="exc_bad",
                document_id="doc_a",
                granted_by="usr_admin",
            )
        )
