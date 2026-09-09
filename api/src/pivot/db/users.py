"""SQLAlchemy UserDirectory backed by the PostgreSQL fact model.

This adapter maps SPEC §2.2 User columns. `must_change_password` is an M01
domain flag and is not a persisted User column.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pivot.auth.ports import UserAccount
from pivot.db.models import User
from pivot.db.uow import UnitOfWork
from pivot.shared.time import utc_now


def _to_account(row: User) -> UserAccount:
    return UserAccount(
        id=row.id,
        username=row.username,
        password_hash=row.password_hash,
        role=row.role,
        status=row.status,
        token_version=row.token_version,
        must_change_password=False,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _apply(row: User, user: UserAccount) -> None:
    row.username = user.username
    row.password_hash = user.password_hash
    row.role = user.role
    row.status = user.status
    row.token_version = user.token_version
    if user.updated_at is not None:
        row.updated_at = user.updated_at


class SqlAlchemyUserDirectory:
    """UserDirectory that reads and writes the SQLAlchemy User fact table."""

    def __init__(self, sessions: Session | sessionmaker[Session]) -> None:
        if isinstance(sessions, Session):
            self._session: Session | None = sessions
            self._factory: sessionmaker[Session] | None = None
        else:
            self._session = None
            self._factory = sessions

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        if self._session is not None:
            yield self._session
            return
        assert self._factory is not None
        session = self._factory()
        try:
            yield session
        finally:
            session.close()

    def get_by_id(self, user_id: str) -> UserAccount | None:
        with self._session_scope() as session:
            row = session.get(User, user_id)
            return _to_account(row) if row is not None else None

    def get_by_username(self, username: str) -> UserAccount | None:
        with self._session_scope() as session:
            row = session.scalar(select(User).where(User.username == username))
            return _to_account(row) if row is not None else None

    def save(self, user: UserAccount) -> None:
        if not user.id or not user.username:
            raise ValueError("users require a non-empty id and username")
        with self._session_scope() as session:
            with UnitOfWork(session):
                row = session.get(User, user.id)
                if row is None:
                    session.add(
                        User(
                            id=user.id,
                            username=user.username,
                            password_hash=user.password_hash,
                            role=user.role,
                            status=user.status,
                            token_version=user.token_version,
                            created_at=user.created_at or utc_now(),
                            updated_at=user.updated_at or utc_now(),
                        )
                    )
                else:
                    _apply(row, user)

    def list(self) -> tuple[UserAccount, ...]:
        with self._session_scope() as session:
            rows = session.scalars(select(User).order_by(User.created_at, User.id)).all()
            return tuple(_to_account(row) for row in rows)
