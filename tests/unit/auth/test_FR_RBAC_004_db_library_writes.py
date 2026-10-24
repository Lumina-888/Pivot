"""Database-backed library/membership writes for FR-RBAC-004 (S4).

The S4 admin service writes through SqlAlchemyLibraryCatalog on the
PostgreSQL path. This test proves those writes against SQLite: the S1
ORM types are portable, and the writer reaches the tables through the
same session factory the PostgreSQL stores use. The remaining catalog
methods stay on the composed catalog in bootstrap, so only the S4
write surface is exercised here.
"""

from __future__ import annotations

import pytest
from pivot.auth.ports import Library, Membership
from pivot.db.base import Base
from pivot.db.libraries import SqlAlchemyLibraryCatalog
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
                id="usr_alice", username="alice", password_hash="hash",
                role="user", status="active",
            )
        )
        session.add(
            UserRow(
                id="usr_bob", username="bob", password_hash="hash",
                role="user", status="active",
            )
        )
        session.commit()
    return SqlAlchemyLibraryCatalog(sessions)


def test_FR_RBAC_004_db_library_writes_round_trip(catalog) -> None:
    catalog.create_library(
        Library(id="dept_eng", name="技术部", kind="department", dept_id="dept_eng")
    )
    assert catalog.get_library("dept_eng") is not None
    assert catalog.get_library("dept_eng").name == "技术部"
    catalog.add_membership(
        Membership(
            user_id="usr_alice", dept_id="dept_eng", dept_role="editor",
            granted_by="usr_admin",
        )
    )
    members = catalog.get_department_members("dept_eng")
    assert len(members) == 1
    assert members[0].dept_role == "editor"
    assert members[0].granted_by == "usr_admin"
    catalog.set_membership(
        Membership(
            user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
            granted_by="usr_admin",
        )
    )
    members = catalog.get_department_members("dept_eng")
    assert len(members) == 1
    assert members[0].dept_role == "dept_admin"
    catalog.remove_membership("usr_alice", "dept_eng")
    assert catalog.get_department_members("dept_eng") == ()
    catalog.delete_library("dept_eng")
    assert catalog.get_library("dept_eng") is None


def test_FR_RBAC_004_db_library_writes_list_libraries(catalog) -> None:
    catalog.create_library(
        Library(id="pub", name="公共库", kind="public")
    )
    catalog.create_library(
        Library(id="dept_art", name="美术部", kind="department", dept_id="dept_art")
    )
    ids = {library.id for library in catalog.list_libraries()}
    assert ids == {"pub", "dept_art"}
