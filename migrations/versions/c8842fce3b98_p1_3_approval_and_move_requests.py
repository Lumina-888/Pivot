"""p1-3 approval and move request tables

Revision ID: c8842fce3b98
Revises: 6e6b5ec79a1c
Create Date: 2026-10-26 11:55:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c8842fce3b98'
down_revision: Union[str, None] = '6e6b5ec79a1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADR-019 (P1-3 S1): approval and move request records. Storage
    # only: no service, no route, no behavior reads these yet (S2/S4).
    # One pending request per document per kind is a partial unique
    # index, not application logic: it holds on both backends (the
    # document_versions one-current index is the same pattern) and
    # closes the two-proposals-arrive-together race the service check
    # alone cannot. Closed requests stay readable as history.
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column(
            "document_id", sa.String(length=128), nullable=False,
        ),
        sa.Column(
            "version_id", sa.String(length=128), nullable=False,
        ),
        sa.Column(
            "target_library_id", sa.String(length=128), nullable=False,
        ),
        sa.Column("proposer", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "decided_by", sa.String(length=128), nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'withdrawn',"
            " 'cancelled')",
            name="ck_approval_requests_status",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_library_id"], ["libraries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approval_requests_document_id", "approval_requests",
        ["document_id"],
    )
    op.create_index(
        "ix_approval_requests_target_library_id", "approval_requests",
        ["target_library_id"],
    )
    op.create_index(
        "uq_approval_requests_one_pending", "approval_requests",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "move_requests",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column(
            "document_id", sa.String(length=128), nullable=False,
        ),
        sa.Column(
            "source_library_id", sa.String(length=128), nullable=False,
        ),
        sa.Column(
            "target_library_id", sa.String(length=128), nullable=False,
        ),
        sa.Column("proposer", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "decided_by", sa.String(length=128), nullable=True,
        ),
        # ADR-019 leaves the reconcile failure shape to the plan:
        # pending while the worker has not run, ok once reconciled,
        # failed once retries are exhausted (P1-2 S5 retry discipline:
        # 3 retries, 4 attempts total, tracked in reconcile_attempts).
        sa.Column(
            "reconcile_status", sa.String(length=32), nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "reconcile_attempts", sa.Integer(), nullable=False,
            server_default="0",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'withdrawn',"
            " 'cancelled')",
            name="ck_move_requests_status",
        ),
        sa.CheckConstraint(
            "reconcile_status IN ('pending', 'ok', 'failed')",
            name="ck_move_requests_reconcile_status",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_library_id"], ["libraries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_library_id"], ["libraries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_move_requests_document_id", "move_requests", ["document_id"],
    )
    op.create_index(
        "ix_move_requests_target_library_id", "move_requests",
        ["target_library_id"],
    )
    op.create_index(
        "uq_move_requests_one_pending", "move_requests",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_move_requests_one_pending", table_name="move_requests"
    )
    op.drop_index(
        "ix_move_requests_target_library_id", table_name="move_requests"
    )
    op.drop_index(
        "ix_move_requests_document_id", table_name="move_requests"
    )
    op.drop_table("move_requests")
    op.drop_index(
        "uq_approval_requests_one_pending",
        table_name="approval_requests",
    )
    op.drop_index(
        "ix_approval_requests_target_library_id",
        table_name="approval_requests",
    )
    op.drop_index(
        "ix_approval_requests_document_id", table_name="approval_requests"
    )
    op.drop_table("approval_requests")
