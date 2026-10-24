"""Library and membership reads from PostgreSQL for AccessControl (FR-RBAC-004).

S1 created the libraries and memberships tables, but nothing read them
into AccessControl: the production catalog was an empty in-memory one,
so every non-admin's visible set degraded to the public library alone.
This reader closes that gap on the PostgreSQL path using the same
session factory as the other SQLAlchemy stores. It covers exactly the
three library methods AccessControl needs for visibility; every other
catalog method stays on the composed catalog in bootstrap.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pivot.auth.ports import Library, Membership
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import Membership as MembershipRow


def _to_library(row: LibraryRow) -> Library:
    return Library(id=row.id, name=row.name, kind=row.kind, dept_id=row.dept_id)


def _to_membership(row: MembershipRow) -> Membership:
    return Membership(
        user_id=row.user_id,
        dept_id=row.dept_id,
        dept_role=row.dept_role,
        granted_by=row.granted_by,
        granted_at=row.granted_at,
    )


class SqlAlchemyLibraryCatalog:
    """Read S1 library/membership facts through a shared session factory."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get_library(self, library_id: str) -> Library | None:
        with self._scope() as session:
            row = session.get(LibraryRow, library_id)
            return None if row is None else _to_library(row)

    def list_libraries(self) -> tuple[Library, ...]:
        with self._scope() as session:
            rows = session.scalars(select(LibraryRow).order_by(LibraryRow.id)).all()
            return tuple(_to_library(row) for row in rows)

    def get_memberships(self, user_id: str) -> tuple[Membership, ...]:
        with self._scope() as session:
            rows = session.scalars(
                select(MembershipRow)
                .where(MembershipRow.user_id == user_id)
                .order_by(MembershipRow.dept_id)
            ).all()
            return tuple(_to_membership(row) for row in rows)

    @contextmanager
    def _scope(self) -> Iterator[Session]:
        session = self._sessions()
        try:
            yield session
        finally:
            session.close()
