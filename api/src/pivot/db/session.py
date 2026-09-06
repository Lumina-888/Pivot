"""Database engine/session factories with injected URLs."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_db_engine(database_url: str, **kwargs) -> Engine:
    """Create an engine without hard-coded infrastructure endpoints."""
    return create_engine(database_url, future=True, **kwargs)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a configured synchronous Session factory."""
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield one session; callers should use UnitOfWork for transactions."""
    factory = session_factory(engine)
    with factory() as session:
        yield session
