"""SQLite proof for the S3 catalog reads (FR-RBAC-004, ADR-017 D1).

The new ResourceCatalog reads for S3: exceptions by department and
one exception by id. The production PostgreSQL proof lives in the
db_pg group; this file proves the query shapes against SQLite.
"""

from __future__ import annotations

import pytest
from pivot.auth.ports import DocumentException
from pivot.db.base import Base
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from sqlalchemy import create_engine


@pytest.fixture
def catalog() -> SqlAlchemyLibraryCatalog:
    engine = create_engine("sqlite://")
    for table in (
        "users",
        "libraries",
        "memberships",
        "documents",
        "document_exceptions",
    ):
        Base.metadata.tables[table].create(engine)
    sessions = session_factory(engine)
    with sessions() as session:
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
        session.add(DocumentRow(id="doc_a", title="t", created_by="usr_admin"))
        session.commit()
    return SqlAlchemyLibraryCatalog(sessions)


def test_FR_RBAC_004_exceptions_by_department_and_by_id(catalog) -> None:
    personal = DocumentException(
        id="exc_personal", document_id="doc_a",
        target_user_id="usr_dave", granted_by="usr_admin",
    )
    dept_grant = DocumentException(
        id="exc_dept", document_id="doc_a",
        target_dept_id="dept_art", granted_by="usr_admin",
    )
    catalog.add_exception(personal)
    catalog.add_exception(dept_grant)
    by_dept = catalog.get_exceptions_for_department("dept_art")
    assert [row.id for row in by_dept] == ["exc_dept"]
    assert catalog.get_exceptions_for_department("dept_eng") == ()
    found = catalog.get_exception("exc_personal")
    assert found is not None
    assert found.target_user_id == "usr_dave"
    assert catalog.get_exception("exc_ghost") is None
