"""SQLite proof for the S2 folder store (FR-RBAC-004, ADR-018 D3).

Folder rows, folder membership rows (with the same lazy-purge /
hot-path discipline as department memberships), rename via set_folder
without touching member rows, and delete_folder dropping member rows
with the folder. The production PostgreSQL proof lives in the db_pg
group; this file proves the query shapes against SQLite.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pivot.auth.ports import Folder, FolderMembership, Principal
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
        session.add(
            UserRow(
                id="usr_admin", username="admin", password_hash="hash",
                role="admin", status="active",
            )
        )
        session.add(
            UserRow(
                id="usr_alice", username="alice", password_hash="hash",
                role="user", status="active",
            )
        )
        session.add(
            UserRow(
                id="usr_dave", username="dave", password_hash="hash",
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


def test_FR_RBAC_004_folder_crud_and_member_upsert(catalog) -> None:
    assert catalog.get_folder("fld_a") is None
    catalog.create_folder(
        Folder(id="fld_a", library_id="dept_eng", name="文件夹 A")
    )
    folder = catalog.get_folder("fld_a")
    assert folder is not None and folder.name == "文件夹 A"
    assert [row.id for row in catalog.list_folders("dept_eng")] == ["fld_a"]
    assert catalog.list_folders("dept_art") == ()
    member = FolderMembership(
        folder_id="fld_a", user_id="usr_dave", folder_role="reader",
        granted_by="usr_admin",
    )
    catalog.add_folder_member(member)
    # The store fills granted_at on insert, so compare identity fields
    # rather than full dataclass equality.
    (stored,) = catalog.get_folder_members("fld_a")
    assert (stored.folder_id, stored.user_id, stored.folder_role) == (
        "fld_a", "usr_dave", "reader",
    )
    # Upsert: re-adding updates the role instead of duplicating.
    catalog.add_folder_member(
        FolderMembership(
            folder_id="fld_a", user_id="usr_dave", folder_role="full",
            granted_by="usr_admin",
        )
    )
    (updated,) = catalog.get_folder_members("fld_a")
    assert updated.folder_role == "full"
    (hot,) = catalog.get_folder_memberships("usr_dave")
    assert hot.folder_role == "full"
    # Rename via set_folder keeps the member rows.
    catalog.set_folder(
        Folder(id="fld_a", library_id="dept_eng", name="新名字")
    )
    assert catalog.get_folder("fld_a").name == "新名字"
    (kept,) = catalog.get_folder_members("fld_a")
    assert kept.folder_role == "full"
    # Delete drops the member rows with the folder.
    catalog.delete_folder("fld_a")
    assert catalog.get_folder("fld_a") is None
    assert catalog.get_folder_members("fld_a") == ()
    assert catalog.get_folder_memberships("usr_dave") == ()


def test_FR_RBAC_004_folder_member_expiry_purge_and_hot_path(catalog) -> None:
    catalog.create_folder(
        Folder(id="fld_a", library_id="dept_eng", name="文件夹 A")
    )
    expired = FolderMembership(
        folder_id="fld_a", user_id="usr_dave", folder_role="reader",
        granted_by="usr_admin",
        expires_at=T0 - timedelta(seconds=1),
    )
    catalog.add_folder_member(expired)
    # The hot path never writes: the expired row is still there.
    (hot,) = catalog.get_folder_memberships("usr_dave")
    assert (hot.folder_id, hot.user_id, hot.folder_role) == (
        "fld_a", "usr_dave", "reader",
    )
    # The admin-side read purges it physically.
    assert catalog.get_folder_members("fld_a") == ()
    assert catalog.get_folder_memberships("usr_dave") == ()


def test_FR_RBAC_004_folder_visibility_reads_over_sql_catalog(catalog) -> None:
    from pivot.auth.ports import Membership

    catalog.create_folder(
        Folder(id="fld_a", library_id="dept_eng", name="文件夹 A")
    )
    catalog.add_folder_member(
        FolderMembership(
            folder_id="fld_a", user_id="usr_dave", folder_role="reader",
            granted_by="usr_admin",
        )
    )
    catalog.add_membership(
        Membership(
            user_id="usr_dave", dept_id="dept_eng", dept_role="reader",
            granted_by="usr_admin",
        )
    )
    access = AccessControl(catalog)
    dave = Principal(
        user_id="usr_dave", username="dave", role="user", token_version=1
    )
    assert access.visible_folder_ids(dave) == frozenset({"fld_a"})
    assert access.folder_visible(dave, "fld_a", "dept_eng") is True
    # A department admin with no folder row still sees the folder.
    catalog.add_membership(
        Membership(
            user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
            granted_by="usr_admin",
        )
    )
    dept_admin = Principal(
        user_id="usr_alice", username="alice", role="user", token_version=1
    )
    assert access.visible_folder_ids(dept_admin) == frozenset({"fld_a"})
