"""Real PostgreSQL proof for S3 project rows (FR-RBAC-004, ADR-018 D4).

Project libraries and project_lead membership rows against the
production store whose schema comes from the Alembic migrations.
Skipped without PIVOT_TEST_PG_URL. Seed order follows the CI #240 /
#256 lesson: users first, then library rows, then membership rows,
each committed separately so foreign keys never see a half-flushed
batch.
"""

from __future__ import annotations

import pytest
from pivot.auth.ports import Membership
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import Membership as MembershipRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from sqlalchemy.exc import IntegrityError


def _seed(pg_session) -> None:
    pg_session.add(
        UserRow(
            id="usr_admin", username="admin", password_hash="hash",
            role="admin", status="active",
        )
    )
    pg_session.add(
        UserRow(
            id="usr_erin", username="erin", password_hash="hash",
            role="user", status="active",
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
        LibraryRow(
            id="proj_x", name="跨部门项目", kind="project",
            dept_id="dept_eng",
        )
    )
    pg_session.commit()


def test_FR_RBAC_004_p1_4_project_round_trip_pg(pg_session, pg_engine) -> None:
    _seed(pg_session)
    catalog = SqlAlchemyLibraryCatalog(session_factory(pg_engine))
    catalog.add_membership(
        Membership(
            user_id="usr_erin", dept_id="proj_x",
            dept_role="project_lead", granted_by="usr_admin",
        )
    )
    project = catalog.get_library("proj_x")
    assert project is not None
    assert project.kind == "project"
    assert project.dept_id == "dept_eng"
    members = catalog.get_department_members("proj_x")
    assert len(members) == 1
    assert members[0].dept_role == "project_lead"
    lead = next(
        m
        for m in catalog.get_memberships("usr_erin")
        if m.dept_id == "proj_x"
    )
    assert lead.dept_role == "project_lead"
    catalog.remove_membership("usr_erin", "proj_x")
    assert catalog.get_department_members("proj_x") == ()


def test_FR_RBAC_004_p1_4_project_role_check_rejects_illegal_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    pg_session.add(
        MembershipRow(
            user_id="usr_erin", dept_id="proj_x", dept_role="bogus",
            granted_by="usr_admin",
        )
    )
    with pytest.raises(IntegrityError):
        pg_session.commit()
