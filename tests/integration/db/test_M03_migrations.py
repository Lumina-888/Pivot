from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _alembic_config(database_url: str) -> Config:
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "migrations" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def test_M03_migrations_upgrade_and_downgrade(tmp_path):
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'migration.db').as_posix()}"
    config = _alembic_config(database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert "users" in tables
    assert "document_versions" in tables
    assert "audit_events" in tables
    assert "refresh_sessions" in tables
    assert "conversations" in tables
    command.downgrade(config, "base")
    # Alembic keeps its version bookkeeping table after downgrade; business tables are gone.
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
