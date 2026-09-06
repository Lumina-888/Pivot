"""Append-only audit facts (SPEC §2.2 and §8.4)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from pivot.db.base import Base
from pivot.shared.time import utc_now


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(128))
    run_id: Mapped[str | None] = mapped_column(String(128))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


@event.listens_for(Session, "before_flush")
def _prevent_audit_mutation(session: Session, flush_context, instances) -> None:
    """Reject updates/deletes of audit facts at the application session boundary.

    PostgreSQL deployment should additionally revoke UPDATE/DELETE privileges or
    install an equivalent trigger; this listener protects all application paths.
    """
    for obj in session.dirty:
        if isinstance(obj, AuditEvent):
            raise ValueError("AuditEvent is append-only and cannot be updated")
    for obj in session.deleted:
        if isinstance(obj, AuditEvent):
            raise ValueError("AuditEvent is append-only and cannot be deleted")
