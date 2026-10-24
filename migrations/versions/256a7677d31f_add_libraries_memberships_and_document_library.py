"""add_libraries_memberships_and_document_library

Revision ID: 256a7677d31f
Revises: 45f1c8bda305
Create Date: 2026-10-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "256a7677d31f"
down_revision: Union[str, None] = "45f1c8bda305"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADR-016 (P1-1 S1): library-level isolation. PostgreSQL stays the
    # single authority; Qdrant collections per library arrive in S3.
    op.create_table(
        "libraries",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("dept_id", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "kind IN ('public', 'department', 'system')", name="ck_libraries_kind"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "memberships",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("dept_id", sa.String(length=128), nullable=False),
        sa.Column("dept_role", sa.String(length=32), nullable=False),
        sa.Column("granted_by", sa.String(length=128), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "dept_role IN ('dept_admin', 'editor', 'reader')",
            name="ck_memberships_dept_role",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "dept_id"),
    )
    # Fixed seed libraries. 'unassigned' is a system library visible
    # only to the super admin; admins claim its documents later.
    op.execute(
        sa.text(
            "INSERT INTO libraries (id, name, kind, dept_id) VALUES"
            " ('pub', '公共库', 'public', NULL),"
            " ('unassigned', '未分配库', 'system', NULL)"
        )
    )
    op.add_column(
        "documents",
        sa.Column("library_id", sa.String(length=128), nullable=True),
    )
    # Fail-closed data migration. The stored equivalent of
    # "shared_visible" is space == 'shared' (see documents/service.py:
    # non-admin visibility requires space == 'shared'; the database
    # has no shared_visible column). Only exactly 'shared' lands in
    # the public library; everything else goes to unassigned. Never
    # default a non-shared document into the public library.
    op.execute(
        sa.text("UPDATE documents SET library_id = 'pub' WHERE space = 'shared'")
    )
    op.execute(
        sa.text("UPDATE documents SET library_id = 'unassigned' WHERE space <> 'shared'")
    )
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column(
            "library_id", nullable=False, server_default="unassigned"
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("library_id")
    op.drop_table("memberships")
    op.drop_table("libraries")
