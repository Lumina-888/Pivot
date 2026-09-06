"""SQLAlchemy declarative base for the PostgreSQL business fact source."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata imported by Alembic and test fixtures."""

    pass
