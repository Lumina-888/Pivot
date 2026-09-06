"""Exception-safe SQLAlchemy transaction boundary."""

from __future__ import annotations

from sqlalchemy.orm import Session


class UnitOfWork:
    """Commit on successful exit and roll back on any exception."""

    def __init__(self, session: Session):
        self.session = session

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if exc_type is not None:
            self.session.rollback()
            return False
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return False
