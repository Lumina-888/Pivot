"""S3: P1-4 project migration for FR-RBAC-004 (ADR-018 D4).

Verifies the S3 migration on SQLite following the P1-4 migration
test pattern: fresh upgrade to head, data migration from the
pre-S3 head, and downgrade back to it.

The pre-S3 head is pinned, following the P1-1 migration test
precedent: reading "current head" as this migration's own head breaks
the moment a later migration lands (it already broke the P1-2 test).
Fresh upgrades still target "head"; the data-migration and downgrade
tests target the pinned pre-S3 head.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

import pytest


def _alembic_config(database_url: str) -> Config:
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "migrations" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


PRE_S3_HEAD = "67fd19930bb8"


def _seed_pre_s3_rows(engine) -> None:
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
                " VALUES ('dept_eng', '技术部', 'department', 'dept_eng')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO memberships (user_id, dept_id, dept_role,"
                " granted_by, granted_at, expires_at)"
                " VALUES ('usr_admin', 'dept_eng', 'dept_admin',"
                " 'usr_admin', '2026-10-25T00:00:00+00:00', NULL)"
            )
        )


def test_FR_RBAC_004_p1_4_project_migration_extends_role_check(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path}/s3.db"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as conn:
        table_sql = conn.execute(
            text(
                "SELECT sql FROM sqlite_master"
                " WHERE type = 'table' AND name = 'memberships'"
            )
        ).scalar_one()
    assert "project_lead" in table_sql
    with engine.begin() as conn:
        # The extended CHECK accepts the new project_lead value...
        conn.execute(
            text(
                "INSERT INTO users (id, username, password_hash, role, status,"
                " token_version, must_change_password, created_at, updated_at)"
                " VALUES ('usr_erin', 'erin', 'x', 'user', 'active', 1,"
                " false, '2026-10-25T00:00:00+00:00', '2026-10-25T00:00:00+00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO libraries (id, name, kind, dept_id)"
                " VALUES ('proj_x', '跨部门项目', 'project', 'dept_eng')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO memberships (user_id, dept_id, dept_role,"
                " granted_by, granted_at, expires_at)"
                " VALUES ('usr_erin', 'proj_x', 'project_lead',"
                " 'usr_admin', '2026-10-25T00:00:00+00:00', NULL)"
            )
        )
    # ... and still rejects an illegal one (SQLite enforces CHECK).
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO memberships (user_id, dept_id, dept_role,"
                    " granted_by, granted_at, expires_at)"
                    " VALUES ('usr_erin', 'proj_x', 'bogus',"
                    " 'usr_admin', '2026-10-25T00:00:00+00:00', NULL)"
                )
            )
    engine.dispose()


def test_FR_RBAC_004_p1_4_project_migration_keeps_rows(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path}/s3keep.db"
    config = _alembic_config(database_url)
    command.upgrade(config, PRE_S3_HEAD)
    engine = create_engine(database_url)
    _seed_pre_s3_rows(engine)
    command.upgrade(config, "head")
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT user_id, dept_id, dept_role FROM memberships")
        ).fetchall()
    assert rows == [("usr_admin", "dept_eng", "dept_admin")]
    engine.dispose()


def test_FR_RBAC_004_p1_4_project_migration_downgrade_restores_check(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path}/s3down.db"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    command.downgrade(config, PRE_S3_HEAD)
    engine = create_engine(database_url)
    with engine.connect() as conn:
        table_sql = conn.execute(
            text(
                "SELECT sql FROM sqlite_master"
                " WHERE type = 'table' AND name = 'memberships'"
            )
        ).scalar_one()
    assert "project_lead" not in table_sql
    assert "dept_admin" in table_sql
    engine.dispose()
