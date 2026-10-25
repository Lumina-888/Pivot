"""Real PostgreSQL proof for the S3 catalog reads (FR-RBAC-004, ADR-017 D1).

Same shapes as the SQLite proof: exceptions by department and one
exception by id, against the production store whose schema comes
from the Alembic migrations. Skipped without PIVOT_TEST_PG_URL.
"""

from __future__ import annotations

from pivot.auth.ports import DocumentException
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory


def _seed(pg_session) -> None:
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


def test_FR_RBAC_004_exceptions_by_department_and_by_id_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    pg_session.commit()
    catalog = SqlAlchemyLibraryCatalog(session_factory(pg_engine))
    catalog.add_exception(
        DocumentException(
            id="exc_personal", document_id="doc_a",
            target_user_id="usr_dave", granted_by="usr_admin",
        )
    )
    catalog.add_exception(
        DocumentException(
            id="exc_dept", document_id="doc_a",
            target_dept_id="dept_art", granted_by="usr_admin",
        )
    )
    by_dept = catalog.get_exceptions_for_department("dept_art")
    assert [row.id for row in by_dept] == ["exc_dept"]
    found = catalog.get_exception("exc_personal")
    assert found is not None
    assert found.target_user_id == "usr_dave"
    assert catalog.get_exception("exc_ghost") is None
