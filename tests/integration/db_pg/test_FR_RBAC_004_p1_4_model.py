"""Real PostgreSQL proof for the S1 model (FR-RBAC-004, ADR-018 D3/D4).

Same shapes as the SQLite proof: project library rows, folder rows,
folder membership rows (including expires_at), and the document
location field, against the production store whose schema comes
from the Alembic migrations. Skipped without PIVOT_TEST_PG_URL.
"""

from __future__ import annotations

import pytest
from pivot.db.documents import SqlAlchemyDocumentStore
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.identity import Folder as FolderRow
from pivot.db.models.identity import FolderMembership as FolderMemberRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from pivot.documents.ports import DocumentRecord
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
            id="usr_dave", username="dave", password_hash="hash",
            role="user", status="active",
        )
    )
    if pg_session.get(LibraryRow, "dept_art") is None:
        pg_session.add(
            LibraryRow(
                id="dept_art", name="美术部", kind="department",
                dept_id="dept_art",
            )
        )
    pg_session.add(DocumentRow(id="doc_a", title="t", created_by="usr_admin"))


def test_FR_RBAC_004_p1_4_model_round_trip_pg(pg_session, pg_engine) -> None:
    _seed(pg_session)
    pg_session.commit()
    pg_session.add(
        LibraryRow(
            id="proj_x", name="跨部门项目", kind="project",
            dept_id="dept_art",
        )
    )
    pg_session.add(
        FolderRow(id="fold_1", library_id="proj_x", name="项目甲")
    )
    pg_session.add(
        FolderMemberRow(
            folder_id="fold_1", user_id="usr_dave", folder_role="full",
            granted_by="usr_admin", expires_at=None,
        )
    )
    pg_session.commit()
    store = SqlAlchemyDocumentStore(session_factory(pg_engine))
    store.save(
        DocumentRecord(
            id="doc_a", title="t", space="", created_by="usr_admin",
            library_id="proj_x", folder_id="fold_1",
        )
    )
    found = store.get("doc_a")
    assert found is not None
    assert found.library_id == "proj_x"
    assert found.folder_id == "fold_1"
    project = pg_session.get(LibraryRow, "proj_x")
    member = pg_session.get(FolderMemberRow, ("fold_1", "usr_dave"))
    assert project is not None
    assert project.kind == "project"
    assert project.dept_id == "dept_art"
    assert member is not None
    assert member.folder_role == "full"
    assert member.expires_at is None


def test_FR_RBAC_004_p1_4_kind_check_rejects_illegal_value_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    pg_session.commit()
    pg_session.add(
        LibraryRow(id="lib_bad", name="B", kind="bogus", dept_id=None)
    )
    with pytest.raises(IntegrityError):
        pg_session.commit()
