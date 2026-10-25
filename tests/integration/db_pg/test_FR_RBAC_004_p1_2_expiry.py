"""Real PostgreSQL proof of the S2 lazy purge (FR-RBAC-004, ADR-017 D2, Q3).

Same assertions as the SQLite file, against the production store whose
schema comes from the Alembic migrations. The full matrix stays covered
by the unit tests; this file proves the wiring on PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pivot.auth.ports import Membership
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory


def _seed(pg_session) -> None:
    if pg_session.get(UserRow, "usr_dave") is None:
        pg_session.add(
            UserRow(
                id="usr_dave", username="dave", password_hash="hash",
                role="user", status="active",
            )
        )
    if pg_session.get(UserRow, "usr_erin") is None:
        pg_session.add(
            UserRow(
                id="usr_erin", username="erin", password_hash="hash",
                role="user", status="active",
            )
        )
    if pg_session.get(LibraryRow, "dept_eng") is None:
        pg_session.add(
            LibraryRow(
                id="dept_eng", name="技术部", kind="department",
                dept_id="dept_eng",
            )
        )
    pg_session.commit()


def _member(user_id: str, expires_at) -> Membership:
    return Membership(
        user_id=user_id, dept_id="dept_eng", dept_role="reader",
        granted_by="usr_admin", expires_at=expires_at,
    )


def test_FR_RBAC_004_expiry_pg_purge_on_department_members(
    pg_engine, pg_session
) -> None:
    _seed(pg_session)
    catalog = SqlAlchemyLibraryCatalog(session_factory(pg_engine))
    catalog.add_membership(
        _member("usr_dave", datetime(2020, 1, 1, tzinfo=timezone.utc))
    )
    catalog.add_membership(
        _member("usr_erin", datetime(2030, 1, 1, tzinfo=timezone.utc))
    )
    raw_before = catalog.get_memberships("usr_dave")
    assert [m for m in raw_before if m.user_id == "usr_dave"]
    members = catalog.get_department_members("dept_eng")
    assert [m.user_id for m in members] == ["usr_erin"]
    assert catalog.get_memberships("usr_dave") == ()
