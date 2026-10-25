"""SQLite proof for the S3 project store (FR-RBAC-004, ADR-018 D4).

Project libraries and project_lead membership rows travel through
the same SqlAlchemyLibraryCatalog as departments: create/read a
project library, add/read/set/remove a project_lead membership, and
the lazy purge of expired project rows on the admin member read.
The production PostgreSQL proof lives in the db_pg group.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pivot.auth.ports import Library, Membership
from pivot.db.base import Base
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from sqlalchemy import create_engine

import pytest

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


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


def test_FR_RBAC_004_p1_4_project_catalog_round_trip(catalog) -> None:
    assert catalog.get_library("proj_x") is None
    catalog.create_library(
        Library(
            id="proj_x", name="跨部门项目", kind="project",
            dept_id="dept_eng",
        )
    )
    project = catalog.get_library("proj_x")
    assert project is not None
    assert project.kind == "project"
    assert project.dept_id == "dept_eng"
    assert catalog.get_department_members("proj_x") == ()
    catalog.add_membership(
        Membership(
            user_id="usr_erin", dept_id="proj_x",
            dept_role="project_lead", granted_by="usr_admin",
        )
    )
    members = catalog.get_department_members("proj_x")
    assert len(members) == 1
    assert members[0].dept_role == "project_lead"
    assert members[0].expires_at is None
    lead = next(
        m
        for m in catalog.get_memberships("usr_erin")
        if m.dept_id == "proj_x"
    )
    assert lead.dept_role == "project_lead"
    catalog.set_membership(
        Membership(
            user_id="usr_erin", dept_id="proj_x", dept_role="editor",
            granted_by="usr_admin",
        )
    )
    assert catalog.get_department_members("proj_x")[0].dept_role == "editor"
    catalog.remove_membership("usr_erin", "proj_x")
    assert catalog.get_department_members("proj_x") == ()


def test_FR_RBAC_004_p1_4_project_catalog_expired_purged(catalog) -> None:
    catalog.create_library(
        Library(
            id="proj_x", name="跨部门项目", kind="project",
            dept_id="dept_eng",
        )
    )
    catalog.add_membership(
        Membership(
            user_id="usr_erin", dept_id="proj_x", dept_role="reader",
            granted_by="usr_admin",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    # The admin member read purges expired rows (ADR-017 Q3).
    assert catalog.get_department_members("proj_x") == ()
    assert catalog.get_memberships("usr_erin") == ()
