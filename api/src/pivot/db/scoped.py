"""One shared SQLAlchemy session per multi-store operation (ADR-017 D4).

Department administration touches three stores in one operation: the
library catalog, the document store (claims), and the audit store. Each
store used to open its own session and commit on its own, so the
service compensated a failed audit write by reverting the mutation
after the fact. Compensation cannot unwrite an audit event recorded
before a later one fails, and a failed compensation leaves an
unaudited change behind.

On the PostgreSQL path the service instead brackets the mutation and
its audit writes in one shared session (see ``shared_session``): the
scope commits once at the end, or rolls everything back when the
operation raises. Stores join the ambient session instead of opening
their own, and skip their own commit while joined: the scope owns the
transaction boundary. The memory path has no sessions, so it keeps the
compensation behavior unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy.orm import Session, sessionmaker

from pivot.db.uow import UnitOfWork

_current: ContextVar[Session | None] = ContextVar(
    "pivot_shared_session", default=None
)


def ambient_session() -> Session | None:
    """The session of the enclosing shared scope, if any."""
    return _current.get()


@contextmanager
def shared_session(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Open one session for a whole operation.

    Commits on clean exit, rolls back on any exception, always closes.
    Nested scopes join the outer session: only the outermost scope
    commits, so a service that brackets several store calls never
    commits halfway through.
    """
    existing = _current.get()
    if existing is not None:
        yield existing
        return
    session = factory()
    token = _current.set(session)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        _current.reset(token)


@contextmanager
def scoped_session(
    bound: Session | None, factory: sessionmaker[Session] | None
) -> Iterator[Session]:
    """Resolve the session a store call runs on.

    A bound session wins (its existing contract is untouched). In
    factory mode an ambient shared session wins over a fresh one, so
    store calls inside a service operation join that operation's
    transaction. Otherwise a fresh session is opened and closed here.
    """
    if bound is not None:
        yield bound
        return
    ambient = _current.get()
    if ambient is not None:
        yield ambient
        return
    assert factory is not None
    owned = factory()
    try:
        yield owned
    finally:
        owned.close()


@contextmanager
def write_scope(session: Session) -> Iterator[None]:
    """Commit boundary for one store write.

    A write on the ambient session joins the enclosing scope: no
    commit here, or the mutation would land before its audit write.
    Any other session commits (and rolls back on failure) as before.
    """
    if ambient_session() is session:
        yield
    else:
        with UnitOfWork(session):
            yield
