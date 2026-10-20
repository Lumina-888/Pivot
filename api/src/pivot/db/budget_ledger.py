"""Provider attempt reservations and the per-Run budget ledger.

Implements 04-A sections 3 and 6 on top of the provider_attempts
table:

- Every dispatch is preceded, inside a fenced transaction, by a
  reservation. reserve() is idempotent on reservation_id: a retried
  reserve returns the existing attempt instead of double-counting.
- dispatch_state walks reserved -> dispatching -> returned, or
  reserved -> not_dispatched (release, only when the attempt provably
  was never dispatched). An attempt stuck in dispatching after a
  crash keeps its reservation and stays unreconciled: it is never
  treated as zero usage.
- settle() is idempotent for identical usage and refuses different
  usage for the same attempt; recorded usage is never rewritten.
- Amounts are integer microunits in a single currency per Run
  (02-B). The budget cap is supplied by the caller from the Run's
  approved policy; production values are TBD-P0. The cap is checked
  at reserve time against reported plus outstanding amounts;
  settle records actual usage as reported, even if it exceeds the
  reservation, because stranded unrecorded usage is worse.

After each mutation the RunExecution budget cursor is rewritten from
the ledger's derived state, so a checkpoint snapshots a cursor that
always matches the persisted attempts. Late usage from a stale
executor is not accepted here; it belongs to the audited
reconciliation entry of 04-A section 6 (M06), not this ledger.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from pivot.db.lease import LeaseManager
from pivot.db.models import ProviderAttempt, RunExecution
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now

ROLES = frozenset({"planner", "finalizer", "verifier", "embedding", "rerank"})
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")

DISPATCH_RESERVED = "reserved"
DISPATCH_DISPATCHING = "dispatching"
DISPATCH_RETURNED = "returned"
DISPATCH_NOT_DISPATCHED = "not_dispatched"
USAGE_REPORTED = "reported"
USAGE_UNRECONCILED = "unreconciled"


class BudgetError(Exception):
    """Base exception for budget ledger failures."""


class BudgetExceededError(BudgetError):
    """Raised when a reservation would exceed the Run's budget cap."""


class AttemptStateError(BudgetError):
    """Raised when a transition is illegal for the attempt's state."""


class AttemptConflictError(BudgetError):
    """Raised when an idempotent replay carries different facts."""


@dataclass(frozen=True)
class Reconciliation:
    """Derived ledger totals for one Run, read from persisted attempts."""

    run_id: str
    currency: str | None
    attempt_count: int
    reported_cost_microunits: int
    reserved_outstanding_microunits: int
    unreconciled_attempt_ids: tuple[str, ...]

    @property
    def cursor(self) -> str:
        return (
            f"ledger:{self.attempt_count}:{self.reported_cost_microunits}"
            f":{self.reserved_outstanding_microunits}"
        )


class BudgetLedger:
    """Reserves, dispatches, settles and reconciles provider attempts."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._leases = LeaseManager(session)

    def reserve(
        self,
        *,
        run_id: str,
        action_id: str,
        reservation_id: str,
        role: str,
        model_version: str,
        pricing_version: str,
        currency: str,
        reserved_cost_microunits: int,
        cap_microunits: int,
        fencing_token: int,
    ) -> ProviderAttempt:
        """Reserve budget for one dispatch, or return the prior reservation."""
        if role not in ROLES:
            raise BudgetError(f"Unknown provider role: {role!r}")
        if not _CURRENCY_RE.match(currency):
            raise BudgetError(f"Invalid currency code: {currency!r}")
        if reserved_cost_microunits < 0 or cap_microunits <= 0:
            raise BudgetError("Amounts must be non-negative and cap positive")
        self._leases.require_current_token(run_id, fencing_token)

        existing = (
            self.session.query(ProviderAttempt)
            .filter(ProviderAttempt.reservation_id == reservation_id)
            .one_or_none()
        )
        if existing is not None:
            if existing.run_id != run_id or existing.action_id != action_id:
                raise AttemptConflictError(
                    f"Reservation {reservation_id} already belongs to "
                    f"run {existing.run_id} action {existing.action_id}"
                )
            return existing

        totals = self.reconcile(run_id)
        if totals.currency is not None and totals.currency != currency:
            raise AttemptConflictError(
                f"Run {run_id} already ledgers in {totals.currency}"
            )
        committed = (
            totals.reported_cost_microunits + totals.reserved_outstanding_microunits
        )
        if committed + reserved_cost_microunits > cap_microunits:
            raise BudgetExceededError(
                f"Run {run_id} budget exceeded: committed {committed} + "
                f"reserve {reserved_cost_microunits} > cap {cap_microunits}"
            )

        attempt = ProviderAttempt(
            attempt_id=new_id("attempt"),
            run_id=run_id,
            action_id=action_id,
            reservation_id=reservation_id,
            fencing_token=fencing_token,
            request_id=None,
            role=role,
            model_version=model_version,
            pricing_version=pricing_version,
            dispatch_state=DISPATCH_RESERVED,
            usage_status=USAGE_UNRECONCILED,
            reserved_cost_microunits=reserved_cost_microunits,
            currency=currency,
        )
        self.session.add(attempt)
        self.session.flush()
        self._sync_cursor(run_id)
        return attempt

    def mark_dispatching(
        self, attempt_id: str, *, fencing_token: int, request_id: str | None = None
    ) -> ProviderAttempt:
        """Move a reserved attempt to dispatching, just before the call."""
        attempt = self._get(attempt_id)
        self._leases.require_current_token(attempt.run_id, fencing_token)
        if attempt.usage_status == USAGE_REPORTED:
            raise AttemptStateError(f"Attempt {attempt_id} is already settled")
        if attempt.dispatch_state == DISPATCH_NOT_DISPATCHED:
            raise AttemptStateError(f"Attempt {attempt_id} was released")
        if attempt.dispatch_state == DISPATCH_RESERVED:
            attempt.dispatch_state = DISPATCH_DISPATCHING
        if request_id is not None:
            attempt.request_id = request_id
        attempt.updated_at = utc_now()
        self.session.flush()
        return attempt

    def settle(
        self,
        attempt_id: str,
        *,
        fencing_token: int,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_microunits: int,
    ) -> ProviderAttempt:
        """Record reported usage for a dispatched attempt, idempotently."""
        if min(input_tokens, output_tokens, estimated_cost_microunits) < 0:
            raise BudgetError("Usage amounts must be non-negative")
        attempt = self._get(attempt_id)
        self._leases.require_current_token(attempt.run_id, fencing_token)
        if attempt.usage_status == USAGE_REPORTED:
            if (
                attempt.input_tokens == input_tokens
                and attempt.output_tokens == output_tokens
                and attempt.estimated_cost_microunits == estimated_cost_microunits
            ):
                return attempt
            raise AttemptConflictError(
                f"Attempt {attempt_id} already settled with different usage"
            )
        if attempt.dispatch_state != DISPATCH_DISPATCHING:
            raise AttemptStateError(
                f"Attempt {attempt_id} is {attempt.dispatch_state}, not dispatching"
            )
        attempt.dispatch_state = DISPATCH_RETURNED
        attempt.usage_status = USAGE_REPORTED
        attempt.input_tokens = input_tokens
        attempt.output_tokens = output_tokens
        attempt.estimated_cost_microunits = estimated_cost_microunits
        attempt.updated_at = utc_now()
        self.session.flush()
        self._sync_cursor(attempt.run_id)
        return attempt

    def release(self, attempt_id: str, *, fencing_token: int) -> ProviderAttempt:
        """Free a reservation that provably was never dispatched."""
        attempt = self._get(attempt_id)
        self._leases.require_current_token(attempt.run_id, fencing_token)
        if attempt.dispatch_state == DISPATCH_NOT_DISPATCHED:
            return attempt
        if attempt.dispatch_state != DISPATCH_RESERVED:
            raise AttemptStateError(
                f"Attempt {attempt_id} is {attempt.dispatch_state}; "
                "only a reserved attempt can be released"
            )
        attempt.dispatch_state = DISPATCH_NOT_DISPATCHED
        attempt.updated_at = utc_now()
        self.session.flush()
        self._sync_cursor(attempt.run_id)
        return attempt

    def reconcile(self, run_id: str) -> Reconciliation:
        """Compute the Run's ledger totals from persisted attempts."""
        attempts = (
            self.session.query(ProviderAttempt)
            .filter(ProviderAttempt.run_id == run_id)
            .all()
        )
        reported = sum(
            a.estimated_cost_microunits or 0
            for a in attempts
            if a.usage_status == USAGE_REPORTED
        )
        outstanding = sum(
            a.reserved_cost_microunits
            for a in attempts
            if a.dispatch_state in (DISPATCH_RESERVED, DISPATCH_DISPATCHING)
        )
        unreconciled = tuple(
            a.attempt_id
            for a in attempts
            if a.usage_status == USAGE_UNRECONCILED
            and a.dispatch_state == DISPATCH_DISPATCHING
        )
        return Reconciliation(
            run_id=run_id,
            currency=attempts[0].currency if attempts else None,
            attempt_count=len(attempts),
            reported_cost_microunits=reported,
            reserved_outstanding_microunits=outstanding,
            unreconciled_attempt_ids=unreconciled,
        )

    def _get(self, attempt_id: str) -> ProviderAttempt:
        attempt = self.session.get(ProviderAttempt, attempt_id)
        if attempt is None:
            raise BudgetError(f"ProviderAttempt {attempt_id} not found")
        return attempt

    def _sync_cursor(self, run_id: str) -> None:
        execution = self.session.get(RunExecution, run_id)
        if execution is None:
            raise BudgetError(f"RunExecution not found for run {run_id}")
        execution.budget_ledger_cursor = self.reconcile(run_id).cursor
        execution.updated_at = utc_now()
        self.session.flush()
