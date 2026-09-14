"""SQLAlchemy refresh token store backed by hashed session rows."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pivot.auth.ports import RefreshSession
from pivot.db.models import RefreshToken
from pivot.db.uow import UnitOfWork
from pivot.shared.time import ensure_utc


def _session_scope(
    session: Session | None, factory: sessionmaker[Session] | None
) -> Iterator[Session]:
    if session is not None:
        yield session
        return
    assert factory is not None
    owned = factory()
    try:
        yield owned
    finally:
        owned.close()


def _to_session(row: RefreshToken) -> RefreshSession:
    return RefreshSession(
        token_hash=row.token_hash,
        user_id=row.user_id,
        token_version=row.token_version,
        expires_at=ensure_utc(row.expires_at),
        revoked=row.revoked,
    )


class SqlAlchemyRefreshTokenStore:
    """RefreshTokenStore that reads and writes hashed refresh_sessions rows."""

    def __init__(self, sessions: Session | sessionmaker[Session]) -> None:
        if isinstance(sessions, Session):
            self._session: Session | None = sessions
            self._factory: sessionmaker[Session] | None = None
        else:
            self._session = None
            self._factory = sessions

    @contextmanager
    def _scope(self) -> Iterator[Session]:
        yield from _session_scope(self._session, self._factory)

    def save(self, session: RefreshSession) -> None:
        if not session.token_hash or not session.user_id:
            raise ValueError("refresh sessions require a token_hash and user_id")
        with self._scope() as db:
            with UnitOfWork(db):
                row = db.get(RefreshToken, session.token_hash)
                if row is None:
                    db.add(
                        RefreshToken(
                            token_hash=session.token_hash,
                            user_id=session.user_id,
                            token_version=session.token_version,
                            expires_at=session.expires_at,
                            revoked=session.revoked,
                        )
                    )
                    return
                row.user_id = session.user_id
                row.token_version = session.token_version
                row.expires_at = session.expires_at
                row.revoked = session.revoked

    def get(self, token_hash: str) -> RefreshSession | None:
        with self._scope() as db:
            row = db.get(RefreshToken, token_hash)
            return _to_session(row) if row is not None else None

    def revoke(self, token_hash: str) -> None:
        with self._scope() as db:
            with UnitOfWork(db):
                row = db.get(RefreshToken, token_hash)
                if row is not None:
                    row.revoked = True

    def revoke_user(self, user_id: str) -> None:
        with self._scope() as db:
            with UnitOfWork(db):
                rows = db.scalars(
                    select(RefreshToken).where(RefreshToken.user_id == user_id)
                ).all()
                for row in rows:
                    row.revoked = True
