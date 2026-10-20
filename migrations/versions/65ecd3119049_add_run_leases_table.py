"""add_run_leases_table

Revision ID: 65ecd3119049
Revises: 102d30d04451
Create Date: 2026-10-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "65ecd3119049"
down_revision: Union[str, None] = "102d30d04451"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ExecutionLease of 04-A section 3: one row per Run, never deleted,
    # so the fencing token counter stays monotonic for the Run's life.
    op.create_table(
        "run_leases",
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("executor_id", sa.String(length=128), nullable=True),
        sa.Column("fencing_token", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("idx_run_leases_expires", "run_leases", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_run_leases_expires", "run_leases")
    op.drop_table("run_leases")
