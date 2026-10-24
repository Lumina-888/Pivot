"""Database-backed library catalog for FR-RBAC-004 (S2 gap B).

On the PostgreSQL path AccessControl must read libraries and
memberships from the S1 tables. Before this fix the production
catalog was an empty in-memory one, so every non-admin's visible set
degraded to the public library alone and department members could
never see their own department's documents in production.

This test proves the reader against SQLite: the S1 ORM types are
portable, and the reader reaches the tables through the same session
factory the PostgreSQL stores use. The reader covers exactly the
library methods AccessControl uses for visibility; the remaining
catalog methods stay on the composed catalog in bootstrap, so the
AccessControl assertions below exercise only those methods.
"""

from __future__ import annotations

import pytest
from pivot.auth.ports import Principal
from pivot.db.base import Base
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import Membership as MembershipRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from pivot.security.rbac import AccessControl
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
                id="usr_alice",
                username="alice",
                password_hash="hash",
                role="user",
                status="active",
            )
        )
        session.add(
            UserRow(
                id="usr_multi",
                username="multi",
                password_hash="hash",
                role="user",
                status="active",
            )
        )
        session.add(LibraryRow(id="pub", name="公共库", kind="public"))
        session.add(LibraryRow(id="unassigned", name="未分配", kind="system"))
        session.add(
            LibraryRow(
                id="dept_eng", name="技术部", kind="department", dept_id="dept_eng"
            )
        )
        session.add(
            LibraryRow(
                id="dept_art", name="美术部", kind="department", dept_id="dept_art"
            )
        )
        session.add(
            MembershipRow(
                user_id="usr_alice",
                dept_id="dept_eng",
                dept_role="reader",
                granted_by="usr_admin",
            )
        )
        session.add(
            MembershipRow(
                user_id="usr_multi",
                dept_id="dept_eng",
                dept_role="reader",
                granted_by="usr_admin",
            )
        )
        session.add(
            MembershipRow(
                user_id="usr_multi",
                dept_id="dept_art",
                dept_role="editor",
                granted_by="usr_admin",
            )
        )
        session.commit()
    return SqlAlchemyLibraryCatalog(sessions)


def _principal(user_id: str, role: str = "user") -> Principal:
    return Principal(user_id=user_id, username=user_id, role=role, token_version=1)


def test_FR_RBAC_004_db_catalog_lists_libraries_and_library(
    catalog: SqlAlchemyLibraryCatalog,
):
    assert {library.id for library in catalog.list_libraries()} == {
        "pub",
        "unassigned",
        "dept_eng",
        "dept_art",
    }
    eng = catalog.get_library("dept_eng")
    assert eng is not None
    assert eng.name == "技术部"
    assert eng.dept_id == "dept_eng"
    assert catalog.get_library("dept_missing") is None


def test_FR_RBAC_004_db_catalog_memberships_drive_visible_union(
    catalog: SqlAlchemyLibraryCatalog,
):
    access = AccessControl(catalog)
    assert access.visible_libraries(_principal("usr_alice")) == {"pub", "dept_eng"}
    assert access.visible_libraries(_principal("usr_multi")) == {
        "pub",
        "dept_eng",
        "dept_art",
    }
    assert access.visible_libraries(_principal("usr_nobody")) == {"pub"}
    admin_visible = access.visible_libraries(_principal("usr_admin", role="admin"))
    assert {"pub", "unassigned", "dept_eng", "dept_art"} <= admin_visible


def test_FR_RBAC_004_db_catalog_unknown_user_has_no_memberships(
    catalog: SqlAlchemyLibraryCatalog,
):
    assert catalog.get_memberships("usr_ghost") == ()
    memberships = catalog.get_memberships("usr_alice")
    assert len(memberships) == 1
    assert memberships[0].dept_id == "dept_eng"
    assert memberships[0].dept_role == "reader"
