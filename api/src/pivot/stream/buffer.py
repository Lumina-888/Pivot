"""In-run SSE buffer: monotonic seq, single terminal, Last-Event-ID replay."""

from __future__ import annotations

import threading
from typing import Any

from pivot.stream.events import TERMINAL_EVENTS, envelope


class EventLog:
    def __init__(self, run_id: str, message_id: str) -> None:
        self.run_id = run_id
        self.message_id = message_id
        self._events: list[tuple[str, dict[str, Any]]] = []
        self._terminal: str | None = None
        self._cv = threading.Condition()

    def emit(self, event: str, stage: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if event not in {
            "run_started",
            "stage",
            "token",
            "citation",
            "warning",
            "completed",
            "uncertain",
            "refused",
            "failed",
            "cancelled",
        }:
            raise ValueError(f"unknown event {event}")
        with self._cv:
            if self._terminal is not None:
                raise ValueError("terminal event already emitted")
            seq = len(self._events) + 1
            data = envelope(
                run_id=self.run_id,
                message_id=self.message_id,
                seq=seq,
                stage=stage,
                payload=payload,
            )
            self._events.append((event, data))
            if event in TERMINAL_EVENTS:
                self._terminal = event
            self._cv.notify_all()
        return data

    def wait_after(
        self, last_event_id: int, timeout: float | None = None
    ) -> tuple[tuple[str, dict[str, Any]], ...]:
        with self._cv:
            pending = self.replay(last_event_id=last_event_id)
            if pending or self._terminal is not None:
                return pending
            self._cv.wait(timeout=timeout)
            return self.replay(last_event_id=last_event_id)

    def replay(self, last_event_id: int | None = None) -> tuple[tuple[str, dict[str, Any]], ...]:
        start = 0 if last_event_id is None else last_event_id
        return tuple(
            (name, data) for name, data in self._events if data["seq"] > start
        )

    def persistable(self) -> tuple[tuple[str, dict[str, Any]], ...]:
        return tuple(self._events)

    @classmethod
    def from_persisted(
        cls,
        run_id: str,
        message_id: str,
        events: tuple[tuple[str, dict[str, Any]], ...] | list[tuple[str, dict[str, Any]]],
    ) -> EventLog:
        log = cls(run_id, message_id)
        log._events = list(events)
        for name, _data in log._events:
            if name in TERMINAL_EVENTS:
                log._terminal = name
        return log

    @property
    def terminal(self) -> str | None:
        return self._terminal
