"""S1: P1-4 model round-trips for FR-RBAC-004 (ADR-018 D3/D4).

SQLite proof for the new storage shapes: project library rows,
folder rows, folder membership rows (including expires_at), and the
document location field. The production PostgreSQL proof lives in the
db_pg group; this file proves the shapes against SQLite.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from pivot.auth.ports import Folder, FolderMembership
from pivot.db.base import Base
from pivot.db.documents import SqlAlchemyDocumentStore
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.identity import Folder as FolderRow
from pivot.db.models.identity import FolderMembership as FolderMemberRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from pivot.documents.ports import DocumentRecord


@pytest.fixture
def sessions():
    engine = create_engine("sqlite://")
    for table in (
        "users",
        "libraries",
        "folders",
        "folder_memberships",
        "documents",
    ):
        Base.metadata.tables[table].create(engine)
    factory = session_factory(engine)
    with factory() as session:
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
            LibraryRow(
                id="dept_art", name="美术部", kind="department",
                dept_id="dept_art",
            )
        )
        session.commit()
    return factory


def test_FR_RBAC_004_p1_4_project_library_row_round_trip(sessions) -> None:
    with sessions() as session:
        session.add(
            LibraryRow(
                id="proj_x", name="跨部门项目", kind="project",
                dept_id="dept_art",
            )
        )
        session.commit()
        row = session.get(LibraryRow, "proj_x")
    assert row is not None
    assert row.kind == "project"
    # The owning department rides the existing dept_id column: the
    # department whose admin created the project, per ADR-018 D4.
    assert row.dept_id == "dept_art"


def test_FR_RBAC_004_p1_4_folder_and_member_rows_round_trip(sessions) -> None:
    with sessions() as session:
        session.add(
            FolderRow(id="fold_1", library_id="dept_art", name="项目甲")
        )
        session.add(
            FolderMemberRow(
                folder_id="fold_1", user_id="usr_dave", folder_role="full",
                granted_by="usr_admin", expires_at=None,
            )
        )
        session.commit()
        folder = session.get(FolderRow, "fold_1")
        member = session.get(FolderMemberRow, ("fold_1", "usr_dave"))
    assert folder is not None
    assert folder.library_id == "dept_art"
    assert member is not None
    assert member.folder_role == "full"
    # NULL expires_at means a long-term grant, like memberships.
    assert member.expires_at is None


def test_FR_RBAC_004_p1_4_document_folder_round_trip(sessions) -> None:
    store = SqlAlchemyDocumentStore(sessions)
    store.save(
        DocumentRecord(
            id="doc_a", title="t", space="", created_by="usr_admin",
            library_id="dept_art",
        )
    )
    found = store.get("doc_a")
    assert found is not None
    # No location means the default folder, which is the library itself.
    assert found.folder_id is None
    store.save(
        DocumentRecord(
            id="doc_a", title="t", space="", created_by="usr_admin",
            library_id="dept_art", folder_id="fold_1",
        )
    )
    found = store.get("doc_a")
    assert found is not None
    assert found.folder_id == "fold_1"
    # The ORM row carries the same value: the store mapping did not
    # drop the new field (the P1-1 library_id lesson).
    with sessions() as session:
        row = session.get(DocumentRow, "doc_a")
    assert row is not None
    assert row.folder_id == "fold_1"


def test_FR_RBAC_004_p1_4_kind_check_rejects_illegal_value(sessions) -> None:
    with sessions() as session:
        session.add(
            LibraryRow(id="lib_bad", name="B", kind="bogus", dept_id=None)
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_FR_RBAC_004_p1_4_folder_role_check_rejects_illegal_value(
    sessions,
) -> None:
    with sessions() as session:
        session.add(
            FolderRow(id="fold_1", library_id="dept_art", name="项目甲")
        )
        session.add(
            FolderMemberRow(
                folder_id="fold_1", user_id="usr_dave",
                folder_role="admin", granted_by="usr_admin",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_FR_RBAC_004_p1_4_folder_ports_shape() -> None:
    folder = Folder(id="fold_1", library_id="dept_art", name="项目甲")
    member = FolderMembership(
        folder_id="fold_1", user_id="usr_dave", folder_role="full",
        granted_by="usr_admin",
    )
    assert folder.library_id == "dept_art"
    assert member.folder_role == "full"
    assert member.expires_at is None
