"""S1: library migration for FR-RBAC-004 (ADR-016 D1/D5).

Verifies the new migration on SQLite following the existing
test_M03_migrations.py pattern: fresh upgrade to head, data
migration from the pre-S1 head, and downgrade back to it.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

PRE_S1_HEAD = "45f1c8bda305"


def _alembic_config(database_url: str) -> Config:
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "migrations" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _seed_pre_s1_documents(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, username, password_hash, role, status,"
                " token_version, must_change_password, created_at, updated_at)"
                " VALUES ('usr_admin', 'admin', 'x', 'admin', 'active', 1,"
                " false, '2026-10-24T00:00:00+00:00', '2026-10-24T00:00:00+00:00')"
            )
        )
        for doc_id, space in (
            ("doc_shared", "shared"),
            ("doc_team", "team"),
            ("doc_empty_space", ""),
        ):
            conn.execute(
                text(
                    "INSERT INTO documents (id, title, space, tags,"
                    " classification, created_by, deleted_at, created_at,"
                    " updated_at) VALUES (:id, 't', :space, '[]', '',"
                    " 'usr_admin', NULL, '2026-10-24T00:00:00+00:00',"
                    " '2026-10-24T00:00:00+00:00')"
                ),
                {"id": doc_id, "space": space},
            )


def test_FR_RBAC_004_migration_creates_tables_and_seed_libraries(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'lib.db').as_posix()}"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert "libraries" in tables
    assert "memberships" in tables
    columns = {c["name"] for c in inspect(engine).get_columns("documents")}
    assert "library_id" in columns
    with engine.connect() as conn:
        rows = dict(
            conn.execute(text("SELECT id, kind FROM libraries")).fetchall()
        )
    assert rows == {"pub": "public", "unassigned": "system"}
    engine.dispose()


def test_FR_RBAC_004_migration_assigns_libraries_fail_closed(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'map.db').as_posix()}"
    config = _alembic_config(database_url)
    command.upgrade(config, PRE_S1_HEAD)
    engine = create_engine(database_url)
    _seed_pre_s1_documents(engine)
    command.upgrade(config, "head")
    with engine.connect() as conn:
        rows = dict(
            conn.execute(text("SELECT id, library_id FROM documents")).fetchall()
        )
    # Only exactly space == 'shared' lands in the public library.
    # Everything else fails closed into the unassigned library.
    assert rows == {
        "doc_shared": "pub",
        "doc_team": "unassigned",
        "doc_empty_space": "unassigned",
    }
    engine.dispose()


def test_FR_RBAC_004_migration_downgrade_removes_library_artifacts(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'down.db').as_posix()}"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    command.downgrade(config, PRE_S1_HEAD)
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert "libraries" not in tables
    assert "memberships" not in tables
    columns = {c["name"] for c in inspect(engine).get_columns("documents")}
    assert "library_id" not in columns
    engine.dispose()
