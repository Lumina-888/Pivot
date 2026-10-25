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
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from pivot.auth.ports import DocumentException, Library, Membership
from pivot.db.models.identity import DocumentException as ExceptionRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import Membership as MembershipRow
from pivot.db.uow import UnitOfWork
from pivot.shared.time import utc_now


def _as_utc(value: datetime) -> datetime:
    # SQLite reads DateTime(timezone=True) back naive; stored values are
    # UTC, so a naive value reads as UTC rather than local time.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_expired(member: Membership, now: datetime) -> bool:
    return member.expires_at is not None and _as_utc(member.expires_at) <= now


def _to_library(row: LibraryRow) -> Library:
    return Library(id=row.id, name=row.name, kind=row.kind, dept_id=row.dept_id)


def _to_membership(row: MembershipRow) -> Membership:
    return Membership(
        user_id=row.user_id,
        dept_id=row.dept_id,
        dept_role=row.dept_role,
        granted_by=row.granted_by,
        granted_at=row.granted_at,
        expires_at=row.expires_at,
    )


def _to_exception(row: ExceptionRow) -> DocumentException:
    return DocumentException(
        id=row.id,
        document_id=row.document_id,
        target_user_id=row.target_user_id,
        target_dept_id=row.target_dept_id,
        granted_by=row.granted_by,
        reason=row.reason,
        expires_at=row.expires_at,
        created_at=row.created_at,
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

    def create_library(self, library: Library) -> None:
        with self._scope() as session:
            with UnitOfWork(session):
                session.add(
                    LibraryRow(
                        id=library.id,
                        name=library.name,
                        kind=library.kind,
                        dept_id=library.dept_id,
                    )
                )

    def delete_library(self, library_id: str) -> None:
        with self._scope() as session:
            with UnitOfWork(session):
                session.execute(
                    delete(LibraryRow).where(LibraryRow.id == library_id)
                )

    def get_department_members(self, dept_id: str) -> tuple[Membership, ...]:
        """Live members of a department (ADR-017 D2, Q3).

        Expired rows are physically deleted here (lazy purge): this is
        the admin-side read, not the per-request hot path, so the write
        stays off get_memberships. Filtering is done in Python, not in
        SQL, because SQLite returns DateTime(timezone=True) naive and a
        SQL comparison against an aware bound value is not portable.
        """
        with self._scope() as session:
            rows = session.scalars(
                select(MembershipRow)
                .where(MembershipRow.dept_id == dept_id)
                .order_by(MembershipRow.user_id)
            ).all()
            now = utc_now()
            live: list[Membership] = []
            expired: list[tuple[str, str]] = []
            for row in rows:
                member = _to_membership(row)
                if _is_expired(member, now):
                    expired.append((row.user_id, row.dept_id))
                else:
                    live.append(member)
            if expired:
                with UnitOfWork(session):
                    for user_id, expired_dept in expired:
                        session.execute(
                            delete(MembershipRow).where(
                                MembershipRow.user_id == user_id,
                                MembershipRow.dept_id == expired_dept,
                            )
                        )
            return tuple(live)

    def add_membership(self, membership: Membership) -> None:
        with self._scope() as session:
            with UnitOfWork(session):
                row = session.get(
                    MembershipRow, (membership.user_id, membership.dept_id)
                )
                if row is None:
                    session.add(
                        MembershipRow(
                            user_id=membership.user_id,
                            dept_id=membership.dept_id,
                            dept_role=membership.dept_role,
                            granted_by=membership.granted_by,
                            # An explicit None would override the column
                            # default with NULL and violate NOT NULL.
                            granted_at=membership.granted_at or utc_now(),
                            expires_at=membership.expires_at,
                        )
                    )
                else:
                    row.dept_role = membership.dept_role
                    row.granted_by = membership.granted_by
                    row.granted_at = membership.granted_at or utc_now()
                    row.expires_at = membership.expires_at

    def remove_membership(self, user_id: str, dept_id: str) -> None:
        with self._scope() as session:
            with UnitOfWork(session):
                session.execute(
                    delete(MembershipRow).where(
                        MembershipRow.user_id == user_id,
                        MembershipRow.dept_id == dept_id,
                    )
                )

    def set_membership(self, membership: Membership) -> None:
        self.add_membership(membership)

    def get_document_exceptions(
        self, document_id: str
    ) -> tuple[DocumentException, ...]:
        with self._scope() as session:
            rows = session.scalars(
                select(ExceptionRow)
                .where(ExceptionRow.document_id == document_id)
                .order_by(ExceptionRow.id)
            ).all()
            return tuple(_to_exception(row) for row in rows)

    def get_exceptions_for_user(
        self, user_id: str
    ) -> tuple[DocumentException, ...]:
        # Personal grants only. Department-target expansion reads the
        # user's memberships and is an S3 concern, not a storage one.
        with self._scope() as session:
            rows = session.scalars(
                select(ExceptionRow)
                .where(ExceptionRow.target_user_id == user_id)
                .order_by(ExceptionRow.id)
            ).all()
            return tuple(_to_exception(row) for row in rows)

    def add_exception(self, exception: DocumentException) -> None:
        with self._scope() as session:
            with UnitOfWork(session):
                row = session.get(ExceptionRow, exception.id)
                if row is None:
                    session.add(
                        ExceptionRow(
                            id=exception.id,
                            document_id=exception.document_id,
                            target_user_id=exception.target_user_id,
                            target_dept_id=exception.target_dept_id,
                            granted_by=exception.granted_by,
                            reason=exception.reason,
                            expires_at=exception.expires_at,
                            created_at=exception.created_at or utc_now(),
                        )
                    )
                else:
                    row.document_id = exception.document_id
                    row.target_user_id = exception.target_user_id
                    row.target_dept_id = exception.target_dept_id
                    row.granted_by = exception.granted_by
                    row.reason = exception.reason
                    row.expires_at = exception.expires_at
                    row.created_at = exception.created_at or utc_now()

    def remove_exception(self, exception_id: str) -> None:
        with self._scope() as session:
            with UnitOfWork(session):
                session.execute(
                    delete(ExceptionRow).where(ExceptionRow.id == exception_id)
                )

    @contextmanager
    def _scope(self) -> Iterator[Session]:
        session = self._sessions()
        try:
            yield session
        finally:
            session.close()
