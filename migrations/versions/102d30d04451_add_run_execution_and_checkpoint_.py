"""add_run_execution_and_checkpoint_binding_tables

Revision ID: 102d30d04451
Revises: 1ff9fb811713
Create Date: 2026-10-12 20:42:41.439064
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "102d30d04451"
down_revision: Union[str, None] = "1ff9fb811713"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create run_executions table
    op.create_table(
        "run_executions",
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("graph_version", sa.String(length=64), nullable=False),
        sa.Column("state_schema_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("tools_version", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("dependencies_lock_version", sa.String(length=64), nullable=False),
        sa.Column("budget_policy_version", sa.String(length=64), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_epoch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_checkpoint_id", sa.String(length=255), nullable=True),
        sa.Column("budget_ledger_cursor", sa.String(length=255), nullable=True),
        sa.Column("original_deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("run_id"),
        sa.UniqueConstraint("thread_id", name="uq_run_executions_thread_id"),
    )
    op.create_index("idx_run_executions_thread", "run_executions", ["thread_id"])

    # Create checkpoint_bindings table
    op.create_table(
        "checkpoint_bindings",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=255), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("execution_epoch", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("graph_version", sa.String(length=64), nullable=False),
        sa.Column("state_schema_version", sa.String(length=64), nullable=False),
        sa.Column("budget_ledger_version", sa.String(length=64), nullable=True),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "state_version", name="uq_checkpoint_run_version"
        ),
    )
    op.create_index("idx_checkpoint_bindings_run", "checkpoint_bindings", ["run_id"])

    # Conditional index for PostgreSQL
    # NOTE: no begin_transaction() block here; on PostgreSQL its exit
    # would commit the outer migration transaction early and corrupt
    # the rest of the upgrade chain (found by 04-F on real PG).
    if op.get_bind().dialect.name == "postgresql":
        op.create_index(
            "idx_checkpoint_bindings_confirmed",
            "checkpoint_bindings",
            ["run_id", "is_confirmed"],
            postgresql_where=sa.text("is_confirmed = TRUE"),
        )


def downgrade() -> None:
    # Drop conditional index for PostgreSQL
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("idx_checkpoint_bindings_confirmed", "checkpoint_bindings")

    op.drop_index("idx_checkpoint_bindings_run", "checkpoint_bindings")
    op.drop_table("checkpoint_bindings")

    op.drop_index("idx_run_executions_thread", "run_executions")
    op.drop_table("run_executions")
