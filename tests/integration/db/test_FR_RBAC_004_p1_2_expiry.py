"""SQLite proof of the S2 lazy purge (FR-RBAC-004, ADR-017 D2, Q3).

get_department_members physically deletes expired rows before
returning; get_memberships never writes, so an expired row survives
there until an admin-side read purges it. The PostgreSQL proof lives
in the db_pg group.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pivot.auth.ports import Membership
from pivot.db.base import Base
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from sqlalchemy import create_engine


@pytest.fixture
def catalog() -> SqlAlchemyLibraryCatalog:
    engine = create_engine("sqlite://")
    for table in ("users", "libraries", "memberships"):
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
            UserRow(
                id="usr_dave", username="dave", password_hash="hash",
                role="user", status="active",
            )
        )
        session.add(
            UserRow(
                id="usr_erin", username="erin", password_hash="hash",
                role="user", status="active",
            )
        )
        session.add(
            LibraryRow(
                id="dept_eng", name="技术部", kind="department",
                dept_id="dept_eng",
            )
        )
        session.commit()
    return SqlAlchemyLibraryCatalog(sessions)


def _member(user_id: str, expires_at) -> Membership:
    return Membership(
        user_id=user_id, dept_id="dept_eng", dept_role="reader",
        granted_by="usr_admin", expires_at=expires_at,
    )


def test_FR_RBAC_004_expiry_sqlite_purge_on_department_members(
    catalog: SqlAlchemyLibraryCatalog,
) -> None:
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
    assert [m.user_id for m in catalog.get_memberships("usr_erin")] == [
        "usr_erin"
    ]


def test_FR_RBAC_004_expiry_sqlite_long_term_survives_purge(
    catalog: SqlAlchemyLibraryCatalog,
) -> None:
    catalog.add_membership(_member("usr_dave", None))
    assert [m.user_id for m in catalog.get_department_members("dept_eng")] == [
        "usr_dave"
    ]
