"""add_project_libraries_folders

Revision ID: 67fd19930bb8
Revises: 921f033d5987
Create Date: 2026-10-25 20:10:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '67fd19930bb8'
down_revision: Union[str, None] = '921f033d5987'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADR-018 (P1-4 S1): project libraries, folders, folder memberships,
    # and the document location field. Storage only: no endpoint, no
    # retrieval wiring, no visibility change reads these yet (S2/S3).
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.drop_constraint("ck_libraries_kind", type_="check")
        batch_op.create_check_constraint(
            "ck_libraries_kind",
            "kind IN ('public', 'department', 'system', 'project')",
        )
    op.create_table(
        "folders",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column(
            "library_id", sa.String(length=128), nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["library_id"], ["libraries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_folders_library_id", "folders", ["library_id"])
    op.create_table(
        "folder_memberships",
        sa.Column(
            "folder_id", sa.String(length=128), nullable=False,
        ),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("folder_role", sa.String(length=32), nullable=False),
        sa.Column(
            "granted_by", sa.String(length=128), nullable=False,
        ),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=True,
        ),
        # Folder roles (ADR-018 D3): full (no member management, so
        # not admin), editor, reader. NULL expires_at means long-term,
        # exactly like memberships (ADR-017 D2); S2 owns the semantics.
        sa.CheckConstraint(
            "folder_role IN ('full', 'editor', 'reader')",
            name="ck_folder_memberships_folder_role",
        ),
        sa.ForeignKeyConstraint(
            ["folder_id"], ["folders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("folder_id", "user_id"),
    )
    op.create_index(
        "ix_folder_memberships_user_id", "folder_memberships", ["user_id"]
    )
    # ADR-018 D3: a document belongs to exactly one location. NULL
    # folder_id means the default folder, which is the library itself,
    # so existing rows need no data migration.
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(
            sa.Column("folder_id", sa.String(length=128), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("folder_id")
    op.drop_index(
        "ix_folder_memberships_user_id", "folder_memberships"
    )
    op.drop_table("folder_memberships")
    op.drop_index("ix_folders_library_id", "folders")
    op.drop_table("folders")
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.drop_constraint("ck_libraries_kind", type_="check")
        batch_op.create_check_constraint(
            "ck_libraries_kind",
            "kind IN ('public', 'department', 'system')",
        )
