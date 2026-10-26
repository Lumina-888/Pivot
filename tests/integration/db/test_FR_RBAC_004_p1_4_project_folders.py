"""SQLite proof for S4 project folders (FR-RBAC-004, ADR-018 D4).

The S1 folder store is library-generic: the same rows serve a
project library with no kind restriction. This file proves folder
CRUD, member upsert with expiry, and rename/delete discipline
inside a project library, plus AccessControl reads over the real
SQLite catalog: the lead and the owning department's admin see the
project folder with no folder row, a plain project member does
not. The production PostgreSQL proof lives in the db_pg group.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pivot.auth.ports import (
    Folder,
    FolderMembership,
    Membership,
    Principal,
)
from pivot.db.base import Base
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from pivot.security.rbac import AccessControl
from sqlalchemy import create_engine

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


@pytest.fixture
def catalog() -> SqlAlchemyLibraryCatalog:
    engine = create_engine("sqlite://")
    for table in (
        "users",
        "libraries",
        "memberships",
        "folders",
        "folder_memberships",
    ):
        Base.metadata.tables[table].create(engine)
    sessions = session_factory(engine)
    with sessions() as session:
        for user_id, username in (
            ("usr_admin", "admin"),
            ("usr_alice", "alice"),
            ("usr_bob", "bob"),
            ("usr_dave", "dave"),
        ):
            session.add(
                UserRow(
                    id=user_id, username=username, password_hash="hash",
                    role="admin" if user_id == "usr_admin" else "user",
                    status="active",
                )
            )
        session.add(
            LibraryRow(
                id="proj_x", name="跨部门项目", kind="project",
                dept_id="dept_eng",
            )
        )
        session.commit()
    return SqlAlchemyLibraryCatalog(sessions)


def test_FR_RBAC_004_project_folder_crud_and_member_upsert(catalog) -> None:
    assert catalog.get_folder("fld_px") is None
    catalog.create_folder(
        Folder(id="fld_px", library_id="proj_x", name="项目文件夹")
    )
    folder = catalog.get_folder("fld_px")
    assert folder is not None and folder.name == "项目文件夹"
    assert [row.id for row in catalog.list_folders("proj_x")] == ["fld_px"]
    assert catalog.list_folders("dept_eng") == ()
    catalog.add_folder_member(
        FolderMembership(
            folder_id="fld_px", user_id="usr_dave", folder_role="reader",
            granted_by="usr_bob",
            expires_at=T0 + timedelta(days=30),
        )
    )
    (stored,) = catalog.get_folder_members("fld_px")
    assert (stored.folder_id, stored.user_id, stored.folder_role) == (
        "fld_px", "usr_dave", "reader",
    )
    assert stored.expires_at is not None
    catalog.add_folder_member(
        FolderMembership(
            folder_id="fld_px", user_id="usr_dave", folder_role="full",
            granted_by="usr_bob",
        )
    )
    (updated,) = catalog.get_folder_members("fld_px")
    assert updated.folder_role == "full"
    catalog.set_folder(
        Folder(id="fld_px", library_id="proj_x", name="新名字")
    )
    assert catalog.get_folder("fld_px").name == "新名字"
    (kept,) = catalog.get_folder_members("fld_px")
    assert kept.folder_role == "full"
    catalog.delete_folder("fld_px")
    assert catalog.get_folder("fld_px") is None
    assert catalog.get_folder_members("fld_px") == ()
    assert catalog.get_folder_memberships("usr_dave") == ()


def test_FR_RBAC_004_project_folder_visibility_reads_over_sql_catalog(
    catalog,
) -> None:
    catalog.create_folder(
        Folder(id="fld_px", library_id="proj_x", name="项目文件夹")
    )
    catalog.add_membership(
        Membership(
            user_id="usr_bob", dept_id="proj_x", dept_role="project_lead",
            granted_by="usr_alice",
        )
    )
    catalog.add_membership(
        Membership(
            user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
            granted_by="usr_admin",
        )
    )
    catalog.add_membership(
        Membership(
            user_id="usr_dave", dept_id="proj_x", dept_role="editor",
            granted_by="usr_bob",
        )
    )
    access = AccessControl(catalog)
    lead = Principal(
        user_id="usr_bob", username="bob", role="user", token_version=1
    )
    owning_admin = Principal(
        user_id="usr_alice", username="alice", role="user", token_version=1
    )
    member = Principal(
        user_id="usr_dave", username="dave", role="user", token_version=1
    )
    # Lead and owning-department admin see the folder with no row.
    assert access.visible_folder_ids(lead) == frozenset({"fld_px"})
    assert access.folder_visible(lead, "fld_px", "proj_x") is True
    assert access.visible_folder_ids(owning_admin) == frozenset({"fld_px"})
    assert access.folder_visible(owning_admin, "fld_px", "proj_x") is True
    # A plain project member without a folder row sees nothing.
    assert access.visible_folder_ids(member) == frozenset()
    assert access.folder_visible(member, "fld_px", "proj_x") is False
