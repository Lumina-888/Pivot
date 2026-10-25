"""S1: P1-4 migration for FR-RBAC-004 (ADR-018 D3/D4).

Verifies the P1-4 S1 migration on SQLite following the P1-2 migration
test pattern: fresh upgrade to head, data migration from the
pre-P1-4 head, and downgrade back to it.

The pre-P1-4 head is pinned, following the P1-1 migration test
precedent: reading "current head" as this migration's own head breaks
the moment a later migration lands (it already broke the P1-2 test).
Fresh upgrades still target "head"; the data-migration and downgrade
tests target the pinned pre-P1-4 head.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

import pytest


def _alembic_config(database_url: str) -> Config:
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "migrations" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


PRE_P1_4_HEAD = "921f033d5987"


def _seed_pre_p1_4_rows(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, username, password_hash, role, status,"
                " token_version, must_change_password, created_at, updated_at)"
                " VALUES ('usr_admin', 'admin', 'x', 'admin', 'active', 1,"
                " false, '2026-10-25T00:00:00+00:00', '2026-10-25T00:00:00+00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO libraries (id, name, kind, dept_id)"
                " VALUES ('dept_art', '美术部', 'department', 'dept_art')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO documents (id, title, space, tags,"
                " classification, created_by, library_id, created_at,"
                " updated_at) VALUES ('doc_a', 't', '', '[]', '',"
                " 'usr_admin', 'dept_art', '2026-10-25T00:00:00+00:00',"
                " '2026-10-25T00:00:00+00:00')"
            )
        )


def test_FR_RBAC_004_p1_4_migration_creates_folders_tables(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'p14.db').as_posix()}"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert "folders" in tables
    assert "folder_memberships" in tables
    assert {c["name"] for c in inspect(engine).get_columns("folders")} == {
        "id",
        "library_id",
        "name",
        "created_at",
    }
    assert {
        c["name"] for c in inspect(engine).get_columns("folder_memberships")
    } == {
        "folder_id",
        "user_id",
        "folder_role",
        "granted_by",
        "granted_at",
        "expires_at",
    }
    columns = {c["name"] for c in inspect(engine).get_columns("documents")}
    assert "folder_id" in columns
    with engine.begin() as conn:
        # The extended kind CHECK accepts the new project value.
        conn.execute(
            text(
                "INSERT INTO libraries (id, name, kind, dept_id)"
                " VALUES ('proj_x', 'X', 'project', 'dept_art')"
            )
        )
    # ... and still rejects an illegal one (SQLite enforces CHECK).
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO libraries (id, name, kind, dept_id)"
                    " VALUES ('lib_bad', 'B', 'bogus', NULL)"
                )
            )
    engine.dispose()


def test_FR_RBAC_004_p1_4_migration_keeps_rows_folder_null(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'p14map.db').as_posix()}"
    config = _alembic_config(database_url)
    command.upgrade(config, PRE_P1_4_HEAD)
    engine = create_engine(database_url)
    _seed_pre_p1_4_rows(engine)
    command.upgrade(config, "head")
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, library_id, folder_id FROM documents")
        ).fetchall()
        libraries = conn.execute(
            text("SELECT id, kind FROM libraries")
        ).fetchall()
    # Pre-existing rows survive; the default-folder semantics need no
    # data migration, so the new location column stays NULL. The
    # migration itself seeds the pub library, so assert membership,
    # not exact equality.
    assert rows == [("doc_a", "dept_art", None)]
    assert ("dept_art", "department") in libraries
    assert ("pub", "public") in libraries
    engine.dispose()


def test_FR_RBAC_004_p1_4_migration_downgrade_removes_artifacts(
    tmp_path,
) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'p14down.db').as_posix()}"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    command.downgrade(config, PRE_P1_4_HEAD)
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert "folders" not in tables
    assert "folder_memberships" not in tables
    columns = {c["name"] for c in inspect(engine).get_columns("documents")}
    assert "folder_id" not in columns
    # The restored CHECK rejects the project value again.
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO libraries (id, name, kind, dept_id)"
                    " VALUES ('proj_x', 'X', 'project', 'dept_art')"
                )
            )
    engine.dispose()
