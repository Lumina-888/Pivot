"""Export, task, parsing and provider metadata facts."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pivot.db.base import Base
from pivot.shared.time import utc_now


class ExportTask(Base):
    __tablename__ = "export_tasks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="requested")
    storage_key: Mapped[str | None] = mapped_column(String(1024))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    owner: Mapped["User"] = relationship(back_populates="exports")


class CeleryTask(Base):
    __tablename__ = "celery_tasks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ParseError(Base):
    __tablename__ = "parse_errors"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    message_summary: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    version: Mapped["DocumentVersion"] = relationship(back_populates="parse_errors")


class ProviderCall(Base):
    __tablename__ = "provider_calls"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"))
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[float | None] = mapped_column()
    request_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run: Mapped["Run | None"] = relationship(back_populates="provider_calls")


class ProviderAttempt(Base):
    """
    One provider dispatch attempt with its budget reservation.

    Per 04-A sections 3 and 6: the (run_id, action_id, attempt_id)
    identity is unique and reservation_id is unique, so retried
    reserves and settles are idempotent. Amounts are integer
    microunits (02-B). Usage fields stay null while the attempt is
    unreconciled and are written exactly once, at settle.
    """

    __tablename__ = "provider_attempts"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "action_id", "attempt_id", name="uq_provider_attempt_identity"
        ),
        UniqueConstraint("reservation_id", name="uq_provider_attempt_reservation"),
    )

    attempt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    action_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reservation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    pricing_version: Mapped[str] = mapped_column(String(64), nullable=False)
    dispatch_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="reserved"
    )
    usage_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unreconciled"
    )
    reserved_cost_microunits: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_microunits: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    run: Mapped["Run"] = relationship()


if TYPE_CHECKING:
    from pivot.db.models.conversations import Run
    from pivot.db.models.documents import DocumentVersion
    from pivot.db.models.identity import User
