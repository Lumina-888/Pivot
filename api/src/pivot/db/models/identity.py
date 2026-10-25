"""Identity facts persisted in PostgreSQL (SPEC §2.2)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
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
    """A document library (ADR-016 D1). One row per library."""

    __tablename__ = "libraries"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('public', 'department', 'system')", name="ck_libraries_kind"
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
            "dept_role IN ('dept_admin', 'editor', 'reader')",
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
