"""Real PostgreSQL proof for the exception delegation fix (FR-RBAC-004).

_LibraryBackedCatalog must proxy the four exception reads to the
PostgreSQL reader: with an empty inner memory catalog, every exception
row must still surface through the wrapper. Skipped without
PIVOT_TEST_PG_URL. Seed order follows the CI #240/#256 lesson: users
first, then the library row, then the exception rows (the exception
rows reference the seeded document).
"""

from __future__ import annotations

from pivot.auth.ports import DocumentException
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import User as UserRow
from pivot.db.session import session_factory
from pivot.http.bootstrap import _LibraryBackedCatalog
from pivot.http.memory import InMemoryResources


def _seed(pg_session) -> None:
    pg_session.add(
        UserRow(
            id="usr_dave", username="dave", password_hash="hash",
            role="user", status="active",
        )
    )
    # documents.created_by references users.id: the admin creator row
    # must exist, or PostgreSQL rejects the document insert (SQLite
    # does not enforce FKs, which is why the SQLite proof missed this).
    pg_session.add(
        UserRow(
            id="usr_admin", username="admin", password_hash="hash",
            role="admin", status="active",
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


def test_FR_RBAC_004_pg_exception_delegation_pg(pg_session, pg_engine) -> None:
    _seed(pg_session)
    pg_session.commit()
    reader = SqlAlchemyLibraryCatalog(session_factory(pg_engine))
    reader.add_exception(
        DocumentException(
            id="exc_personal", document_id="doc_a",
            target_user_id="usr_dave", granted_by="usr_admin",
        )
    )
    reader.add_exception(
        DocumentException(
            id="exc_dept", document_id="doc_a",
            target_dept_id="dept_art", granted_by="usr_admin",
        )
    )
    wrapped = _LibraryBackedCatalog(InMemoryResources(), reader)
    assert [row.id for row in wrapped.get_document_exceptions("doc_a")] == [
        "exc_dept",
        "exc_personal",
    ]
    assert [row.id for row in wrapped.get_exceptions_for_user("usr_dave")] == [
        "exc_personal"
    ]
    assert [
        row.id for row in wrapped.get_exceptions_for_department("dept_art")
    ] == ["exc_dept"]
    found = wrapped.get_exception("exc_personal")
    assert found is not None
    assert found.target_user_id == "usr_dave"
    assert wrapped.get_exception("exc_ghost") is None
