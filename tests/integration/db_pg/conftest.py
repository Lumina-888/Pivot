"""PostgreSQL fault-test harness (04-F).

These tests run against a real PostgreSQL, in real processes. Set
PIVOT_TEST_PG_URL to a maintenance database URL, for example
postgresql+psycopg://user:pass@host:5432/postgres. The harness
creates a dedicated pivot_pg_test database, builds its schema with
the Alembic migrations (the same path production uses, never
create_all), and truncates every table between tests.

Without the variable the whole directory skips. There is no SQLite
fallback, by design: row locks, transaction rollback on connection
death and cross-process visibility are exactly what is under test.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

MAINTENANCE_URL = os.environ.get("PIVOT_TEST_PG_URL")
TEST_DATABASE = "pivot_pg_test"


@pytest.fixture(scope="session")
def pg_engine():
    if not MAINTENANCE_URL:
        pytest.skip(
            "PIVOT_TEST_PG_URL is not set; PostgreSQL fault tests are opt-in"
        )
    maintenance = create_engine(MAINTENANCE_URL, isolation_level="AUTOCOMMIT")
    with maintenance.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DATABASE}"))
    test_url = make_url(MAINTENANCE_URL).set(database=TEST_DATABASE)
    url_string = test_url.render_as_string(hide_password=False)
    repo_root = Path(__file__).resolve().parents[3]
    config = Config(str(repo_root / "migrations" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url_string.replace("%", "%%"))
    command.upgrade(config, "head")
    engine = create_engine(test_url)
    yield engine
    engine.dispose()
    with maintenance.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE}"))
    maintenance.dispose()


@pytest.fixture(scope="session")
def pg_url(pg_engine):
    return pg_engine.url.render_as_string(hide_password=False)


@pytest.fixture()
def pg_session(pg_engine):
    factory = sessionmaker(bind=pg_engine)
    session = factory()
    yield session
    session.close()
    tables = [
        name
        for name in inspect(pg_engine).get_table_names()
        if name != "alembic_version"
    ]
    if tables:
        joined = ", ".join(f'"{name}"' for name in tables)
        with pg_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {joined} RESTART IDENTITY CASCADE"))
