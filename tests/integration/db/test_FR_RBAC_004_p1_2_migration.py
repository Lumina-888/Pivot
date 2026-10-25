"""S1: P1-2 migration for FR-RBAC-004 (ADR-017 D1/D2).

Verifies the P1-2 migration on SQLite following the P1-1 migration
test pattern: fresh upgrade to head, data migration from the
pre-P1-2 head, and downgrade back to it.

Both heads are read from the migration scripts at runtime: the
current head from ScriptDirectory, the pre-P1-2 head from the new
migration's own down_revision. No revision id is hardcoded here.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


def _alembic_config(database_url: str) -> Config:
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "migrations" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _heads() -> tuple[str, str]:
    root = Path(__file__).resolve().parents[3]
    script = ScriptDirectory.from_config(
        Config(str(root / "migrations" / "alembic.ini"))
    )
    head = script.get_current_head()
    pre_head = script.get_revision(head).down_revision
    assert isinstance(pre_head, str)
    return head, pre_head


def _seed_pre_p1_2_rows(engine) -> None:
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
                "INSERT INTO memberships (user_id, dept_id, dept_role,"
                " granted_by, granted_at) VALUES ('usr_admin', 'dept_eng',"
                " 'editor', 'usr_admin', '2026-10-25T00:00:00+00:00')"
            )
        )


def test_FR_RBAC_004_p1_2_migration_creates_exceptions_table(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'p12.db').as_posix()}"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert "document_exceptions" in tables
    columns = {c["name"] for c in inspect(engine).get_columns("memberships")}
    assert "expires_at" in columns
    columns = {
        c["name"] for c in inspect(engine).get_columns("document_exceptions")
    }
    assert columns == {
        "id",
        "document_id",
        "target_user_id",
        "target_dept_id",
        "granted_by",
        "reason",
        "expires_at",
        "created_at",
    }
    engine.dispose()


def test_FR_RBAC_004_p1_2_migration_keeps_memberships_expiry_null(
    tmp_path,
) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'p12map.db').as_posix()}"
    config = _alembic_config(database_url)
    _, pre_head = _heads()
    command.upgrade(config, pre_head)
    engine = create_engine(database_url)
    _seed_pre_p1_2_rows(engine)
    command.upgrade(config, "head")
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT user_id, dept_id, expires_at FROM memberships")
        ).fetchall()
        exception_rows = conn.execute(
            text("SELECT COUNT(*) FROM document_exceptions")
        ).scalar_one()
    # Pre-existing memberships survive with a NULL expiry (long-term).
    assert rows == [("usr_admin", "dept_eng", None)]
    assert exception_rows == 0
    engine.dispose()


def test_FR_RBAC_004_p1_2_migration_downgrade_removes_artifacts(
    tmp_path,
) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'p12down.db').as_posix()}"
    config = _alembic_config(database_url)
    _, pre_head = _heads()
    command.upgrade(config, "head")
    command.downgrade(config, pre_head)
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert "document_exceptions" not in tables
    columns = {c["name"] for c in inspect(engine).get_columns("memberships")}
    assert "expires_at" not in columns
    engine.dispose()
