"""extend_membership_role_check_project_lead

Revision ID: 6e6b5ec79a1c
Revises: 67fd19930bb8
Create Date: 2026-10-25 23:10:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = '6e6b5ec79a1c'
down_revision: Union[str, None] = '67fd19930bb8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADR-018 (P1-4 S3): project members reuse the memberships table
    # with dept_id set to the project id, so the role CHECK must admit
    # the project_lead value (Q3). Batch mode recreates the table on
    # SQLite and issues ALTER on PostgreSQL, mirroring the S1 kind
    # CHECK replacement.
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.drop_constraint("ck_memberships_dept_role", type_="check")
        batch_op.create_check_constraint(
            "ck_memberships_dept_role",
            "dept_role IN ('dept_admin', 'editor', 'reader', 'project_lead')",
        )


def downgrade() -> None:
    # Rows carrying project_lead would violate the restored CHECK;
    # downgrade callers clear project memberships first (project
    # removal refuses while members remain, so no live project_lead
    # row can survive a clean downgrade path).
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.drop_constraint("ck_memberships_dept_role", type_="check")
        batch_op.create_check_constraint(
            "ck_memberships_dept_role",
            "dept_role IN ('dept_admin', 'editor', 'reader')",
        )
