"""PG-path exception delegation for FR-RBAC-004 (ADR-017 D1, S3 residual).

_LibraryBackedCatalog proxies library and folder reads to the
PostgreSQL reader but used to leave the four exception reads to
__getattr__, which falls through to the inner memory catalog. On the
PostgreSQL path the memory catalog carries no exception rows, so the
exception channel silently read empty: QA authorize, the retriever
exception channel, and the search exception channel all lost grants
without erroring. These tests pin the delegation: an inner catalog
with no exceptions plus a reader with exceptions must surface the
reader's rows through all four methods, and AccessControl over the
wrapper must compute the exception set (personal grants plus live
department expansion, exclusive expiry boundary per ADR-017 D2).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fakes import FakeClock
from pivot.auth.ports import DocumentException, Membership, Principal
from pivot.http.bootstrap import _LibraryBackedCatalog
from pivot.http.memory import InMemoryResources
from pivot.security.rbac import AccessControl

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)
DAVE = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)


class _ReaderStub:
    """PostgreSQL-reader stand-in: exception rows live here only."""

    def __init__(self) -> None:
        self.exceptions = {
            "exc_personal": DocumentException(
                id="exc_personal", document_id="doc_personal",
                target_user_id="usr_dave", granted_by="usr_admin",
            ),
            "exc_expired": DocumentException(
                id="exc_expired", document_id="doc_expired",
                target_user_id="usr_dave", granted_by="usr_admin",
                expires_at=T0,
            ),
            "exc_dept": DocumentException(
                id="exc_dept", document_id="doc_dept",
                target_dept_id="dept_art", granted_by="usr_admin",
            ),
        }

    def get_memberships(self, user_id: str):
        if user_id == "usr_dave":
            return (
                Membership(
                    user_id="usr_dave", dept_id="dept_art",
                    dept_role="reader", granted_by="usr_admin",
                ),
            )
        return ()

    def get_document_exceptions(self, document_id: str):
        return tuple(
            exception
            for exception in sorted(
                self.exceptions.values(), key=lambda item: item.id
            )
            if exception.document_id == document_id
        )

    def get_exceptions_for_user(self, user_id: str):
        return tuple(
            exception
            for exception in sorted(
                self.exceptions.values(), key=lambda item: item.id
            )
            if exception.target_user_id == user_id
        )

    def get_exceptions_for_department(self, dept_id: str):
        return tuple(
            exception
            for exception in sorted(
                self.exceptions.values(), key=lambda item: item.id
            )
            if exception.target_dept_id == dept_id
        )

    def get_exception(self, exception_id: str):
        return self.exceptions.get(exception_id)


def _wrapped() -> _LibraryBackedCatalog:
    # Inner catalog carries no exceptions: any row surfacing through
    # the wrapper must come from the reader, never from the inner side.
    return _LibraryBackedCatalog(InMemoryResources(), _ReaderStub())


def test_FR_RBAC_004_pg_exception_delegation_reads() -> None:
    wrapped = _wrapped()
    assert [row.id for row in wrapped.get_document_exceptions("doc_personal")] == [
        "exc_personal"
    ]
    assert [row.id for row in wrapped.get_exceptions_for_user("usr_dave")] == [
        "exc_expired",
        "exc_personal",
    ]
    assert [
        row.id for row in wrapped.get_exceptions_for_department("dept_art")
    ] == ["exc_dept"]
    found = wrapped.get_exception("exc_personal")
    assert found is not None
    assert found.document_id == "doc_personal"
    assert wrapped.get_exception("exc_ghost") is None
    assert wrapped.get_document_exceptions("doc_ghost") == ()


def test_FR_RBAC_004_pg_exception_delegation_access_control() -> None:
    access = AccessControl(_wrapped(), clock=FakeClock(T0))
    doc_ids = access.exception_document_ids(DAVE)
    # Personal live grant counts; the grant expiring exactly at now is
    # already gone (exclusive boundary); the department grant expands
    # over the live dept_art membership.
    assert doc_ids == frozenset({"doc_personal", "doc_dept"})


def test_FR_RBAC_004_pg_exception_delegation_expired_membership() -> None:
    reader = _ReaderStub()
    reader.exceptions["exc_dept_expired_member"] = DocumentException(
        id="exc_dept_expired_member", document_id="doc_dept_old",
        target_dept_id="dept_old", granted_by="usr_admin",
    )
    original = reader.get_memberships

    def _memberships(user_id: str):
        rows = list(original(user_id))
        rows.append(
            Membership(
                user_id="usr_dave", dept_id="dept_old",
                dept_role="reader", granted_by="usr_admin",
                expires_at=T0 - timedelta(seconds=1),
            )
        )
        return tuple(rows)

    reader.get_memberships = _memberships
    access = AccessControl(
        _LibraryBackedCatalog(InMemoryResources(), reader),
        clock=FakeClock(T0),
    )
    # The expired dept_old membership never expands into its grant.
    assert "doc_dept_old" not in access.exception_document_ids(DAVE)
    assert "doc_dept" in access.exception_document_ids(DAVE)
