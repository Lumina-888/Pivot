"""Repository for PublicEventOutbox persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pivot.db.models import PublicEventOutbox
from pivot.shared.time import utc_now


class OutboxRepository:
    """Repository for managing public event outbox records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_run_id(self, run_id: str) -> list[PublicEventOutbox]:
        """Get all outbox events for a run, ordered by seq."""
        stmt = (
            select(PublicEventOutbox)
            .where(PublicEventOutbox.run_id == run_id)
            .order_by(PublicEventOutbox.seq)
        )
        return list(self.session.execute(stmt).scalars())

    def get_undispatched(self, limit: int = 100) -> list[PublicEventOutbox]:
        """Get undispatched outbox events, oldest first."""
        stmt = (
            select(PublicEventOutbox)
            .where(PublicEventOutbox.dispatched_at.is_(None))
            .order_by(PublicEventOutbox.created_at)
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())

    def append_event(self, event: PublicEventOutbox) -> PublicEventOutbox:
        """
        Append a new event to the outbox.

        Raises:
            IntegrityError: If (run_id, seq) or (run_id, publication_key) already exists.
        """
        self.session.add(event)
        self.session.flush()
        return event

    def mark_dispatched(self, event_id: str, dispatched_at: datetime | None = None) -> None:
        """Mark an event as dispatched."""
        if dispatched_at is None:
            dispatched_at = utc_now()

        event = self.session.get(PublicEventOutbox, event_id)
        if event is not None:
            event.dispatched_at = dispatched_at
            self.session.flush()

    def get_next_seq(self, run_id: str) -> int:
        """Get the next sequence number for a run."""
        stmt = (
            select(PublicEventOutbox.seq)
            .where(PublicEventOutbox.run_id == run_id)
            .order_by(PublicEventOutbox.seq.desc())
            .limit(1)
        )
        max_seq = self.session.execute(stmt).scalar_one_or_none()
        return 0 if max_seq is None else max_seq + 1
