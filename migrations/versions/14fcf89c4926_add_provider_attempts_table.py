"""add_provider_attempts_table

Revision ID: 14fcf89c4926
Revises: 65ecd3119049
Create Date: 2026-10-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "14fcf89c4926"
down_revision: Union[str, None] = "65ecd3119049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ProviderAttempt / BudgetLedger of 04-A sections 3 and 6.
    op.create_table(
        "provider_attempts",
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("action_id", sa.String(length=128), nullable=False),
        sa.Column("reservation_id", sa.String(length=128), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("pricing_version", sa.String(length=64), nullable=False),
        sa.Column("dispatch_state", sa.String(length=32), nullable=False),
        sa.Column("usage_status", sa.String(length=32), nullable=False),
        sa.Column("reserved_cost_microunits", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_microunits", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint(
            "run_id", "action_id", "attempt_id", name="uq_provider_attempt_identity"
        ),
        sa.UniqueConstraint("reservation_id", name="uq_provider_attempt_reservation"),
    )
    op.create_index("idx_provider_attempts_run", "provider_attempts", ["run_id"])


def downgrade() -> None:
    op.drop_index("idx_provider_attempts_run", "provider_attempts")
    op.drop_table("provider_attempts")
