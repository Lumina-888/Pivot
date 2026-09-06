"""Timezone-aware UTC helpers (SPEC §5.1, Appendix B.3)."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current timezone-aware UTC instant."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC, rejecting naive values only when ambiguous.

    Naive values are interpreted as UTC at this persistence boundary because all
    API/database timestamps in SPEC are explicitly UTC. Callers should prefer
    passing timezone-aware values so accidental local-time values are detectable.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
