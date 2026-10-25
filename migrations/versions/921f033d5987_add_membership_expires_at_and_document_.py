"""add_membership_expires_at_and_document_exceptions

Revision ID: 921f033d5987
Revises: 256a7677d31f
Create Date: 2026-10-25 07:09:05.262821
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '921f033d5987'
down_revision: Union[str, None] = '256a7677d31f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADR-017 (P1-2 S1): temporary grants and document-level exceptions.
    # memberships.expires_at is NULL for long-term grants; the expiry
    # semantics (read-time exclusion, renewal, purge) land in S2.
    # document_exceptions is storage only in S1: no endpoint, no
    # visibility change, no authorize change reads it yet.
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.add_column(
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.create_table(
        "document_exceptions",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("target_user_id", sa.String(length=128), nullable=True),
        sa.Column("target_dept_id", sa.String(length=128), nullable=True),
        sa.Column("granted_by", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # Exactly one target: a personal grant or a department grant
        # (ADR-017 Q4), never both, never neither. Grant dedupe stays a
        # service concern in S3; the table does not invent it.
        sa.CheckConstraint(
            "(target_user_id IS NOT NULL AND target_dept_id IS NULL)"
            " OR (target_user_id IS NULL AND target_dept_id IS NOT NULL)",
            name="ck_document_exceptions_single_target",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_dept_id"], ["libraries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_exceptions_document_id",
        "document_exceptions",
        ["document_id"],
    )
    op.create_index(
        "ix_document_exceptions_target_user_id",
        "document_exceptions",
        ["target_user_id"],
    )
    op.create_index(
        "ix_document_exceptions_target_dept_id",
        "document_exceptions",
        ["target_dept_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_exceptions_target_dept_id", "document_exceptions"
    )
    op.drop_index(
        "ix_document_exceptions_target_user_id", "document_exceptions"
    )
    op.drop_index(
        "ix_document_exceptions_document_id", "document_exceptions"
    )
    op.drop_table("document_exceptions")
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.drop_column("expires_at")
