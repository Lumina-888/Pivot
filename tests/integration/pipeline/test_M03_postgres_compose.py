"""Opt-in Alembic smoke against Compose Postgres. Not GATE-P0-003 verified."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "postgres-alembic.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_FIXTURE_URL = "postgresql+psycopg://pivot:pivot_dev_only@127.0.0.1:5432/pivot"
_HEAD = "8b19c9c86e1c"


def _require_compose() -> bool:
    return os.environ.get("PIVOT_REQUIRE_COMPOSE") == "1"


def _postgres_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.3):
            return True
    except OSError:
        return False


def _psycopg_available() -> bool:
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return False
    return True


def _skip_or_fail(reason: str) -> None:
    if _require_compose():
        pytest.fail(reason)
    pytest.skip(reason)


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", _FIXTURE_URL)


def _alembic_config(database_url: str) -> Config:
    config = Config(str(_ROOT / "migrations" / "alembic.ini"))
    config.set_main_option("script_location", str(_ROOT / "migrations"))
    config.set_main_option("prepend_sys_path", str(_ROOT / "api" / "src"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def test_M03_postgres_alembic_upgrade_head_when_compose_up():
    if not _postgres_reachable():
        _skip_or_fail("compose postgres is not reachable on 127.0.0.1:5432")
    if not _psycopg_available():
        _skip_or_fail("psycopg extra is not installed; pip install -e ./api[postgres]")

    database_url = _database_url()
    assert database_url.startswith("postgresql"), "fixture smoke must use PostgreSQL, not SQLite"
    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url, future=True)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "users" in tables
        assert "document_versions" in tables
        assert "audit_events" in tables
        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert version == _HEAD
            indexdef = connection.execute(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE tablename = 'document_versions' "
                    "AND indexname = 'uq_document_versions_one_current'"
                )
            ).scalar_one()
        assert "UNIQUE" in indexdef.upper()
        assert "current" in indexdef.lower()
    finally:
        engine.dispose()


def test_M03_postgres_user_directory_when_compose_up():
    if not _postgres_reachable():
        _skip_or_fail("compose postgres is not reachable on 127.0.0.1:5432")
    if not _psycopg_available():
        _skip_or_fail("psycopg extra is not installed; pip install -e ./api[postgres]")

    from pivot.auth.ports import UserAccount
    from pivot.db.models import User
    from pivot.db.session import session_factory
    from pivot.db.users import SqlAlchemyUserDirectory
    from pivot.shared.time import utc_now

    database_url = _database_url()
    assert database_url.startswith("postgresql"), "fixture smoke must use PostgreSQL, not SQLite"
    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url, future=True)
    try:
        directory = SqlAlchemyUserDirectory(session_factory(engine))
        now = utc_now()
        directory.save(
            UserAccount(
                id="usr_compose_dir",
                username="compose_dir",
                password_hash="$argon2id$v=19$m=8,t=1,p=1$c2FsdHNhbHQ$hash",
                role="user",
                status="active",
                token_version=1,
                created_at=now,
                updated_at=now,
            )
        )
        loaded = directory.get_by_username("compose_dir")
        assert loaded is not None
        assert loaded.id == "usr_compose_dir"
        assert loaded.password_hash.startswith("$argon2id$")
        with session_factory(engine)() as session:
            row = session.get(User, "usr_compose_dir")
            assert row is not None
            session.delete(row)
            session.commit()
    finally:
        engine.dispose()


def test_GATE_P0_003_not_verified_by_alembic_smoke_alone():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "atomic" in evidence.lower() or "原子" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")


def test_GATE_P0_003_not_verified_by_postgres_user_directory():
    evidence = (_ROOT / "evidence" / "wave3-m11" / "postgres-user-directory.md").read_text(
        encoding="utf-8"
    )
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "user directory" in evidence.lower() or "用户目录" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
