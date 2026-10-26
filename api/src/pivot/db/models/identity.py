"""Identity facts persisted in PostgreSQL (SPEC §2.2)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pivot.db.base import Base
from pivot.shared.time import utc_now


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        CheckConstraint("role IN ('admin', 'user')", name="ck_users_role"),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    documents: Mapped[list["Document"]] = relationship(back_populates="creator")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="owner")
    exports: Mapped[list["ExportTask"]] = relationship(back_populates="owner")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")
    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class Library(Base):
    """A document library (ADR-016 D1, ADR-018 D4).

    One row per library. A project library (kind 'project') records its
    owning department in dept_id: the department whose admin created it.
    """

    __tablename__ = "libraries"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('public', 'department', 'system', 'project')",
            name="ck_libraries_kind",
        ),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    dept_id: Mapped[str | None] = mapped_column(String(128))


class Membership(Base):
    """One user's role inside one department (ADR-016 D2)."""

    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(
            "dept_role IN ('dept_admin', 'editor', 'reader', 'project_lead')",
            name="ck_memberships_dept_role",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, nullable=False
    )
    dept_id: Mapped[str] = mapped_column(String(128), primary_key=True, nullable=False)
    dept_role: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    # ADR-017 D2: NULL means a long-term grant. Expiry semantics
    # (read-time exclusion, renewal, purge) land in S2; S1 only stores it.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="memberships")


class Folder(Base):
    """A restricted folder inside one library (ADR-018 D3).

    The default folder needs no row: it is the library itself, and a
    document with a NULL folder_id lives there. Only restricted folders
    have rows. Folders are single-level, never nested.
    """

    __tablename__ = "folders"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    library_id: Mapped[str] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class FolderMembership(Base):
    """One user's role inside one folder (ADR-018 D3).

    Mirrors Membership: folder_role is full, editor, or reader (full
    excludes member management, so it is not called admin). NULL
    expires_at means a long-term grant; expiry, renewal, and purge
    semantics follow ADR-017 D2 and land in S2. S1 only stores it.
    """

    __tablename__ = "folder_memberships"
    __table_args__ = (
        CheckConstraint(
            "folder_role IN ('full', 'editor', 'reader')",
            name="ck_folder_memberships_folder_role",
        ),
    )

    folder_id: Mapped[str] = mapped_column(
        ForeignKey("folders.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    folder_role: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentException(Base):
    """A grant-only document-level exception (ADR-017 D1, Q4).

    Exactly one target: target_user_id for a personal grant, or
    target_dept_id for a department grant (expanded at read time in
    S3). NULL expires_at means a permanent grant (ADR-017 Q2).
    granted_by carries no foreign key on purpose: grant provenance
    must survive the grantor's row. S1 is storage only; no endpoint
    and no visibility check reads this table yet.
    """

    __tablename__ = "document_exceptions"
    __table_args__ = (
        CheckConstraint(
            "(target_user_id IS NOT NULL AND target_dept_id IS NULL)"
            " OR (target_user_id IS NULL AND target_dept_id IS NOT NULL)",
            name="ck_document_exceptions_single_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    target_dept_id: Mapped[str | None] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"), index=True
    )
    granted_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    reason: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ApprovalRequest(Base):
    """A publish-approval request (ADR-019 D1, P1-3 S1).

    Storage only in S1: no service, no route reads this yet. One
    pending request per document is a partial unique index (same
    pattern as document_versions' one-current index), so the
    two-proposals-arrive-together race fails at the store, not just
    at the service check. Closed rows stay as history; S5's
    delete-cancels-requests marks them cancelled, it never deletes
    them (documents are tombstoned, never hard-deleted, so the
    CASCADE here only fires if a document row itself is removed).
    """

    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'withdrawn',"
            " 'cancelled')",
            name="ck_approval_requests_status",
        ),
        Index(
            "uq_approval_requests_one_pending",
            "document_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_library_id: Mapped[str] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposer: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(
        String(512), nullable=False, default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    decided_by: Mapped[str | None] = mapped_column(String(128))


class MoveRequest(Base):
    """A cross-library move request (ADR-019 D3, P1-3 S1).

    Same pending-uniqueness rule as ApprovalRequest, one per document.
    reconcile_status tracks the P1-2 D3 reconcile dispatch after
    approval (pending while the worker has not run, ok once
    reconciled, failed once retries are exhausted); reconcile_attempts
    counts attempts against the P1-2 S5 discipline (3 retries, 4
    attempts total). Both fields are S1 storage; S4 owns the semantics.
    """

    __tablename__ = "move_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'withdrawn',"
            " 'cancelled')",
            name="ck_move_requests_status",
        ),
        CheckConstraint(
            "reconcile_status IN ('pending', 'ok', 'failed')",
            name="ck_move_requests_reconcile_status",
        ),
        Index(
            "uq_move_requests_one_pending",
            "document_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_library_id: Mapped[str] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False
    )
    target_library_id: Mapped[str] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposer: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(
        String(512), nullable=False, default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    decided_by: Mapped[str | None] = mapped_column(String(128))
    reconcile_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    reconcile_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )


class RefreshToken(Base):
    """Hashed refresh sessions. Not a SPEC §2.2 core object; Redis must not hold them."""

    __tablename__ = "refresh_sessions"

    token_hash: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


if TYPE_CHECKING:
    from pivot.db.models.conversations import Conversation
    from pivot.db.models.documents import Document
    from pivot.db.models.operations import ExportTask
