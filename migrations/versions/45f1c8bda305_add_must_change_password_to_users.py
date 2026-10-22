"""add_must_change_password_to_users

Revision ID: 45f1c8bda305
Revises: 14fcf89c4926
Create Date: 2026-10-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "45f1c8bda305"
down_revision: Union[str, None] = "14fcf89c4926"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ND-GAP-03: persist the first-login password-change flag so the
    # server-side enforcement survives restarts and works across
    # instances. Existing users default to false (no forced change).
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
