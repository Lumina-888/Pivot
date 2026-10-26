"""S1: P1-3 approval/move request migration (FR-RBAC-004, ADR-019).

Verifies the S1 migration on SQLite following the P1-4 migration
test pattern: fresh upgrade to head, data migration from the
pre-S1 head, and downgrade back to it.

The pre-S1 head is pinned, following the P1-1 migration test
precedent: reading "current head" as this migration's own head breaks
the moment a later migration lands (it already broke the P1-2 test).
Fresh upgrades still target "head"; the data-migration and downgrade
tests target the pinned pre-S1 head.
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


PRE_P1_3_HEAD = "6e6b5ec79a1c"


def _seed_rows(engine) -> None:
    # Commit order follows the CI #240/#256 lesson even though
    # SQLite does not enforce foreign keys: referenced rows first.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, username, password_hash, role, status,"
                " token_version, must_change_password, created_at, updated_at)"
                " VALUES ('usr_admin', 'admin', 'x', 'admin', 'active', 1,"
                " false, '2026-10-26T00:00:00+00:00', '2026-10-26T00:00:00+00:00')"
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
                "INSERT INTO documents (id, title, space, tags,"
                " classification, created_by, library_id, folder_id,"
                " deleted_at, created_at, updated_at)"
                " VALUES ('doc_a', 't', '', '[]', '', 'usr_admin',"
                " 'unassigned', NULL, NULL,"
                " '2026-10-26T00:00:00+00:00', '2026-10-26T00:00:00+00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO document_versions (id, document_id,"
                " version_label, content_sha256, storage_key, state,"
                " current, external_llm_allowed, parser_version,"
                " chunking_version, embedding_model_version, created_at)"
                " VALUES ('ver_a', 'doc_a', '', 'sha', 'key', 'uploaded',"
                " 0, 0, '', '', '', '2026-10-26T00:00:00+00:00')"
            )
        )


def _request_insert(table: str, request_id: str, status: str, extra: str = "") -> str:
    if table == "approval_requests":
        return (
            "INSERT INTO approval_requests (id, document_id, version_id,"
            " target_library_id, proposer, status, reason, created_at)"
            f" VALUES ('{request_id}', 'doc_a', 'ver_a', 'dept_eng',"
            f" 'usr_admin', '{status}', '', '2026-10-26T00:00:00+00:00')"
        )
    return (
        "INSERT INTO move_requests (id, document_id, source_library_id,"
        " target_library_id, proposer, status, reason, created_at"
        f"{extra})"
        f" VALUES ('{request_id}', 'doc_a', 'dept_eng', 'dept_eng',"
        f" 'usr_admin', '{status}', '', '2026-10-26T00:00:00+00:00'"
        f"{', \'pending\', 0' if extra else ''})"
    )


def test_FR_RBAC_004_p1_3_migration_creates_tables(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path}/p1_3.db"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            ).fetchall()
        }
    assert "approval_requests" in tables
    assert "move_requests" in tables
    _seed_rows(engine)
    # Each insert runs in its own transaction: after a failed
    # statement the connection must not be reused inside the same
    # transaction, and separate transactions match real usage.
    with engine.begin() as conn:
        conn.execute(text(_request_insert("approval_requests", "ap_1", "pending")))
    # One pending request per document per kind: the second
    # pending insert fails at the partial unique index.
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(_request_insert("approval_requests", "ap_2", "pending"))
            )
    # A closed request beside a pending one is fine: the index
    # only covers pending rows.
    with engine.begin() as conn:
        conn.execute(
            text(_request_insert("approval_requests", "ap_3", "approved"))
        )
        conn.execute(
            text(
                _request_insert(
                    "move_requests", "mv_1", "pending",
                    ", reconcile_status, reconcile_attempts",
                )
            )
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    _request_insert(
                        "move_requests", "mv_2", "pending",
                        ", reconcile_status, reconcile_attempts",
                    )
                )
            )
    # The status CHECK rejects an unknown value.
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(_request_insert("approval_requests", "ap_4", "bogus"))
            )
    # The reconcile_status CHECK rejects an unknown value.
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO move_requests (id, document_id,"
                    " source_library_id, target_library_id, proposer,"
                    " status, reason, created_at, reconcile_status,"
                    " reconcile_attempts)"
                    " VALUES ('mv_3', 'doc_a', 'dept_eng', 'dept_eng',"
                    " 'usr_admin', 'pending', '',"
                    " '2026-10-26T00:00:00+00:00', 'bogus', 0)"
                )
            )
    engine.dispose()


def test_FR_RBAC_004_p1_3_migration_keeps_rows(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path}/p1_3_keep.db"
    config = _alembic_config(database_url)
    command.upgrade(config, PRE_P1_3_HEAD)
    engine = create_engine(database_url)
    _seed_rows(engine)
    command.upgrade(config, "head")
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, title FROM documents")
        ).fetchall()
    assert rows == [("doc_a", "t")]
    engine.dispose()


def test_FR_RBAC_004_p1_3_migration_downgrade_drops_tables(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path}/p1_3_down.db"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    command.downgrade(config, PRE_P1_3_HEAD)
    engine = create_engine(database_url)
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            ).fetchall()
        }
    assert "approval_requests" not in tables
    assert "move_requests" not in tables
    engine.dispose()
