"""Tiered audit write-failure policy (ND-GAP-02, Owner decision 2026-10-22).

Security-critical audit events fail closed: when the audit write fails, the
business operation is refused rather than proceeding without a trace.
General events are best-effort: the failure is counted and logged through
AuditWriteFailures, never silently dropped.
"""

from __future__ import annotations

import logging
from typing import Protocol

from pivot.audit.catalog import canonicalize

logger = logging.getLogger("pivot.audit")

_CRITICAL_PREFIXES = ("auth.", "authz.", "export.")
_CRITICAL_ACTIONS = frozenset({"document.delete"})


def is_critical_action(action: str) -> bool:
    """Return True when a failed audit write must refuse the operation."""
    canonical = canonicalize(action)
    return canonical.startswith(_CRITICAL_PREFIXES) or canonical in _CRITICAL_ACTIONS


class AuditWriteFailures:
    """Process-local counter and log for best-effort audit write failures."""

    def __init__(self) -> None:
        self.count = 0

    def note(self, action: str, error: Exception) -> None:
        self.count += 1
        logger.error(
            "audit write failed (best-effort, action=%s): %s",
            canonicalize(action),
            error,
        )


class _Draft(Protocol):
    action: str


class _Sink(Protocol):
    def emit(self, event: _Draft) -> None: ...


class TieredAuditSink:
    """Wrap an audit sink with the tiered failure policy.

    Works for any draft type carrying an ``action`` attribute. Critical
    action failures propagate to the caller (fail closed); general action
    failures are recorded through the shared AuditWriteFailures counter.
    """

    def __init__(self, inner: _Sink, failures: AuditWriteFailures) -> None:
        self._inner = inner
        self._failures = failures

    def emit(self, event: _Draft) -> None:
        try:
            self._inner.emit(event)
        except Exception as exc:
            if is_critical_action(event.action):
                raise
            self._failures.note(event.action, exc)
