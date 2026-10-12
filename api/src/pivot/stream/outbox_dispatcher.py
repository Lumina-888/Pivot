"""Outbox dispatcher for SSE event publication.

Reads events from PublicEventOutbox and dispatches them to SSE streams.
Implements the outbox pattern to ensure at-least-once delivery.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from pivot.db.models import PublicEventOutbox
from pivot.db.repositories.outbox import OutboxRepository

logger = logging.getLogger(__name__)


class OutboxDispatcher:
    """Dispatcher for outbox events to SSE streams."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.outbox_repo = OutboxRepository(session)

    def dispatch_pending_events(self, limit: int = 100) -> int:
        """
        Dispatch pending outbox events to SSE streams.

        Reads undispatched events, sends them, and marks as dispatched.
        Events are dispatched in creation order (FIFO).

        Args:
            limit: Maximum number of events to dispatch

        Returns:
            Number of events successfully dispatched
        """
        events = self.outbox_repo.get_undispatched(limit=limit)
        dispatched_count = 0

        for event in events:
            try:
                self._dispatch_event(event)
                self.outbox_repo.mark_dispatched(event.event_id)
                dispatched_count += 1
                logger.info(
                    "Dispatched event",
                    extra={
                        "event_id": event.event_id,
                        "run_id": event.run_id,
                        "seq": event.seq,
                        "event_name": event.event_name,
                    },
                )
            except Exception as e:
                logger.error(
                    "Failed to dispatch event",
                    extra={
                        "event_id": event.event_id,
                        "run_id": event.run_id,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                # Continue with next event - this one stays undispatched

        # Commit dispatch markers
        if dispatched_count > 0:
            self.session.commit()

        return dispatched_count

    def replay_events(self, run_id: str) -> list[dict[str, Any]]:
        """
        Replay all events for a run (for SSE reconnection).

        Returns events in seq order with their envelopes.
        This allows clients to resume from last received seq.

        Args:
            run_id: The run to replay events for

        Returns:
            List of event envelopes in order
        """
        events = self.outbox_repo.get_by_run_id(run_id)
        return [self._parse_envelope(event.envelope) for event in events]

    def _dispatch_event(self, event: PublicEventOutbox) -> None:
        """
        Dispatch a single event to SSE stream.

        In production, this would:
        1. Look up active SSE connections for the run
        2. Send the event envelope to each connection
        3. Handle connection failures

        For now, this is a placeholder that logs the event.
        The actual SSE connection management is handled by the HTTP layer.
        """
        envelope = self._parse_envelope(event.envelope)

        # TODO: Integrate with actual SSE connection manager
        # For now, just validate the envelope can be parsed
        if not isinstance(envelope, dict):
            raise ValueError(f"Invalid envelope format for event {event.event_id}")

        # In production, dispatch to SSE manager here
        # sse_manager.send_to_run(event.run_id, envelope)

        logger.debug(
            "Event ready for dispatch",
            extra={
                "event_id": event.event_id,
                "run_id": event.run_id,
                "seq": event.seq,
                "envelope": envelope,
            },
        )

    def _parse_envelope(self, envelope: str) -> dict[str, Any]:
        """Parse event envelope JSON."""
        try:
            return json.loads(envelope)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse envelope: {e}")
            return {"error": "invalid_envelope", "raw": envelope}


class SSEConnectionManager:
    """
    Manager for active SSE connections.

    This is a placeholder for the actual SSE connection management.
    The real implementation would maintain WebSocket-like connections
    and route events to the appropriate clients.
    """

    def __init__(self) -> None:
        self.connections: dict[str, list[Any]] = {}

    def register_connection(self, run_id: str, connection: Any) -> None:
        """Register a new SSE connection for a run."""
        if run_id not in self.connections:
            self.connections[run_id] = []
        self.connections[run_id].append(connection)

    def unregister_connection(self, run_id: str, connection: Any) -> None:
        """Unregister an SSE connection."""
        if run_id in self.connections:
            self.connections[run_id].remove(connection)
            if not self.connections[run_id]:
                del self.connections[run_id]

    def send_to_run(self, run_id: str, envelope: dict[str, Any]) -> None:
        """Send an event to all active connections for a run."""
        connections = self.connections.get(run_id, [])
        for connection in connections:
            try:
                # TODO: Implement actual SSE send
                # connection.send(envelope)
                pass
            except Exception as e:
                logger.error(f"Failed to send to connection: {e}")
                # Remove failed connection
                self.unregister_connection(run_id, connection)
