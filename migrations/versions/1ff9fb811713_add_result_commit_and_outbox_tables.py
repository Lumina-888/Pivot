"""add_result_commit_and_outbox_tables

Revision ID: 1ff9fb811713
Revises: b7d4e8a21c90
Create Date: 2026-10-12 20:03:14.220517
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "1ff9fb811713"
down_revision: str | None = "b7d4e8a21c90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create result_commits table
    op.create_table(
        "result_commits",
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("result_id", sa.String(length=128), nullable=False),
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("terminal_state", sa.String(length=32), nullable=False),
        sa.Column("verification_version", sa.String(length=64), nullable=False),
        sa.Column("evidence_snapshot_id", sa.String(length=128), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
        ),
        sa.PrimaryKeyConstraint("run_id"),
    )

    # Create public_event_outbox table
    op.create_table(
        "public_event_outbox",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("publication_key", sa.String(length=255), nullable=False),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("envelope", sa.Text(), nullable=False),
        sa.Column("projection_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
        ),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("run_id", "seq", name="uq_outbox_run_seq"),
        sa.UniqueConstraint(
            "run_id", "publication_key", name="uq_outbox_run_publication_key"
        ),
    )
    op.create_index("idx_outbox_run_seq", "public_event_outbox", ["run_id", "seq"])
    # Conditional index for PostgreSQL only - SQLite doesn't support WHERE clause in CREATE INDEX
    # NOTE: no begin_transaction() block here; on PostgreSQL its exit
    # would commit the outer migration transaction early and corrupt
    # the rest of the upgrade chain (found by 04-F on real PG).
    if op.get_bind().dialect.name == "postgresql":
        op.create_index(
            "idx_outbox_undispatched",
            "public_event_outbox",
            ["dispatched_at"],
            postgresql_where=sa.text("dispatched_at IS NULL"),
        )

    # Add unique constraint to agent_events using batch mode for SQLite compatibility
    with op.batch_alter_table("agent_events", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_agent_events_run_seq", ["run_id", "seq"]
        )

    # Add indexes for claims and citations
    op.create_index("idx_claims_run", "claims", ["run_id"])
    op.create_index("idx_citations_run", "citations", ["run_id"])
    op.create_index("idx_citations_chunk", "citations", ["chunk_id"])
    # Conditional index for PostgreSQL
    if op.get_bind().dialect.name == "postgresql":
        op.create_index(
            "idx_citations_claim",
            "citations",
            ["claim_id"],
            postgresql_where=sa.text("claim_id IS NOT NULL"),
        )


def downgrade() -> None:
    # Drop indexes
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("idx_citations_claim", "citations")

    op.drop_index("idx_citations_chunk", "citations")
    op.drop_index("idx_citations_run", "citations")
    op.drop_index("idx_claims_run", "claims")

    # Drop unique constraint from agent_events using batch mode
    with op.batch_alter_table("agent_events", schema=None) as batch_op:
        batch_op.drop_constraint("uq_agent_events_run_seq", type_="unique")

    # Drop outbox indexes and table
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("idx_outbox_undispatched", "public_event_outbox")

    op.drop_index("idx_outbox_run_seq", "public_event_outbox")
    op.drop_table("public_event_outbox")

    # Drop result_commits table
    op.drop_table("result_commits")
