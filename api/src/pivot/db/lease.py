"""Execution leases and fencing tokens for Runs.

Implements the ExecutionLease object and claim protocol of 04-A
sections 3 and 4.1:

- One lease row per Run, keyed by run_id. The row is never deleted:
  release and takeover keep it, so fencing_token is monotonic for
  the life of the Run.
- A claim succeeds only when no live holder exists (never claimed,
  released, or expired). Each successful claim increments the token.
- Renew requires the current holder, the current token and an
  unexpired lease; a stale token can never be revived.
- Lease duration is a caller-supplied policy value. Production
  durations are TBD-P0, so this module provides no default TTL.

Write paths (checkpoint writer, result-commit UoW) re-verify the
token through require_current_token inside their own transaction,
following the fixed lock order of 04-A section 4.1: RunExecution,
Run, Lease.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from pivot.db.models import Run, RunExecution, RunLease
from pivot.runs.machine import is_terminal
from pivot.shared.time import utc_now


class LeaseError(Exception):
    """Base exception for lease failures."""


class LeaseHeldError(LeaseError):
    """Raised when claiming a Run that has a live holder."""


class LeaseNotHeldError(LeaseError):
    """Raised when a token is not the Run's current live lease token."""


class LeaseClaimRefusedError(LeaseError):
    """Raised when a Run may not be claimed at all (terminal, past deadline)."""


@dataclass(frozen=True)
class LeaseToken:
    """A granted lease: holder identity plus its fencing token."""

    run_id: str
    executor_id: str
    fencing_token: int
    expires_at: datetime


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class LeaseManager:
    """Claims, renews and verifies per-Run execution leases."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def acquire(
        self, run_id: str, executor_id: str, *, ttl: timedelta
    ) -> LeaseToken:
        """Claim the lease for ``run_id``, incrementing the fencing token.

        Raises LeaseClaimRefusedError for a terminal Run or a Run past
        its original deadline, and LeaseHeldError while another
        executor's lease is still live.
        """
        execution = (
            self.session.query(RunExecution)
            .filter(RunExecution.run_id == run_id)
            .with_for_update()
            .one_or_none()
        )
        run = (
            self.session.query(Run)
            .filter(Run.id == run_id)
            .with_for_update()
            .one_or_none()
        )
        if run is None:
            raise LeaseError(f"Run {run_id} not found")
        if execution is None:
            raise LeaseError(f"RunExecution not found for run {run_id}")
        if is_terminal(run.state):
            raise LeaseClaimRefusedError(
                f"Run {run_id} is terminal ({run.state}) and cannot be claimed"
            )
        now = utc_now()
        if _aware(execution.original_deadline_at) <= now:
            raise LeaseClaimRefusedError(
                f"Run {run_id} is past its original deadline"
            )

        lease = self._lock_lease(run_id)
        if lease is not None and self._is_live(lease, now):
            raise LeaseHeldError(
                f"Run {run_id} is held by {lease.executor_id} "
                f"until {_aware(lease.expires_at).isoformat()}"
            )
        if lease is None:
            lease = RunLease(run_id=run_id, fencing_token=0)
            self.session.add(lease)
        lease.executor_id = executor_id
        lease.fencing_token += 1
        lease.expires_at = now + ttl
        lease.updated_at = now
        self.session.flush()
        return LeaseToken(
            run_id=run_id,
            executor_id=executor_id,
            fencing_token=lease.fencing_token,
            expires_at=lease.expires_at,
        )

    def renew(self, token: LeaseToken, *, ttl: timedelta) -> LeaseToken:
        """Extend the current lease. Stale or expired leases stay dead."""
        lease = self._require_holder(token)
        now = utc_now()
        lease.expires_at = now + ttl
        lease.updated_at = now
        self.session.flush()
        return LeaseToken(
            run_id=token.run_id,
            executor_id=token.executor_id,
            fencing_token=token.fencing_token,
            expires_at=lease.expires_at,
        )

    def release(self, token: LeaseToken) -> None:
        """Release the lease, keeping the row and its token counter.

        The holder and token must still match. Releasing after expiry
        is a harmless cleanup when nobody took over; after a takeover
        the token no longer matches and the release is refused, so a
        stale executor can never clear the new holder's lease.
        """
        lease = self._lock_lease(token.run_id)
        if (
            lease is None
            or lease.executor_id != token.executor_id
            or lease.fencing_token != token.fencing_token
        ):
            raise LeaseNotHeldError(
                f"Lease token {token.fencing_token} is not the current "
                f"lease for run {token.run_id}"
            )
        lease.executor_id = None
        lease.expires_at = None
        lease.updated_at = utc_now()
        self.session.flush()

    def require_current_token(self, run_id: str, fencing_token: int) -> RunLease:
        """Return the lease row if ``fencing_token`` is live, else raise.

        This is the write-path fencing check of 04-A section 4.1:
        token must match the current holder's and be unexpired.
        """
        lease = self._lock_lease(run_id)
        if (
            lease is None
            or lease.executor_id is None
            or lease.fencing_token != fencing_token
            or not self._is_live(lease, utc_now())
        ):
            raise LeaseNotHeldError(
                f"Fencing token {fencing_token} is not a live lease "
                f"for run {run_id}"
            )
        return lease

    def _lock_lease(self, run_id: str) -> RunLease | None:
        return (
            self.session.query(RunLease)
            .filter(RunLease.run_id == run_id)
            .with_for_update()
            .one_or_none()
        )

    def _require_holder(self, token: LeaseToken) -> RunLease:
        lease = self._lock_lease(token.run_id)
        if (
            lease is None
            or lease.executor_id != token.executor_id
            or lease.fencing_token != token.fencing_token
            or not self._is_live(lease, utc_now())
        ):
            raise LeaseNotHeldError(
                f"Lease token {token.fencing_token} is not a live lease "
                f"for run {token.run_id}"
            )
        return lease

    @staticmethod
    def _is_live(lease: RunLease, now: datetime) -> bool:
        return (
            lease.executor_id is not None
            and lease.expires_at is not None
            and _aware(lease.expires_at) > now
        )
