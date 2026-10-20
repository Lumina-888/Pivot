"""Tests for BudgetLedger and ProviderAttempt (04-E).

Implements the budget slice of the Red list planned in 04-A section
7: reservations are fenced and idempotent, a crash after dispatch
leaves the attempt unreconciled with its reservation held (never
zeroed), settle is idempotent and never rewrites usage, and the
persisted ledger survives a restart with its cursor intact.
"""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from pivot.db.budget_ledger import (
    AttemptConflictError,
    AttemptStateError,
    BudgetError,
    BudgetExceededError,
    BudgetLedger,
)
from pivot.db.lease import LeaseManager, LeaseNotHeldError
from pivot.db.models import Conversation, Run, RunExecution, User
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now

LOCKED_VERSIONS = {
    "graph_version": "graph-1",
    "state_schema_version": "state-1",
    "prompt_version": "prompt-1",
    "tools_version": "tools-1",
    "model_version": "model-1",
    "dependencies_lock_version": "lock-1",
    "budget_policy_version": "budget-1",
}

CAP = 10_000


def seed_run_with_lease(db_session):
    db_session.add(
        User(
            id="user-1",
            username="user-1",
            password_hash="hash",
            role="user",
            status="active",
        )
    )
    conversation = Conversation(
        id=new_id("conversation"),
        owner_id="user-1",
        title="Test",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db_session.add(conversation)
    run = Run(
        id=new_id("run"),
        conversation_id=conversation.id,
        question="Test question",
        idempotency_key=new_id("run"),
        state="planning",
        created_at=utc_now(),
    )
    db_session.add(run)
    db_session.flush()
    execution = RunExecution(
        run_id=run.id,
        thread_id=f"thread-{run.id}",
        state_version=0,
        execution_epoch=0,
        budget_ledger_cursor=None,
        original_deadline_at=utc_now() + timedelta(days=1),
        **LOCKED_VERSIONS,
    )
    db_session.add(execution)
    db_session.commit()
    token = LeaseManager(db_session).acquire(
        run.id, "executor-1", ttl=timedelta(hours=1)
    )
    db_session.commit()
    return run, execution, token.fencing_token


def reserve(db_session, run, token, **overrides):
    kwargs = {
        "run_id": run.id,
        "action_id": "action-1",
        "reservation_id": "reservation-1",
        "role": "planner",
        "model_version": "model-1",
        "pricing_version": "pricing-1",
        "currency": "USD",
        "reserved_cost_microunits": 500,
        "cap_microunits": CAP,
        "fencing_token": token,
    }
    kwargs.update(overrides)
    return BudgetLedger(db_session).reserve(**kwargs)


def test_FR_AUDIT_003_reserve_creates_attempt_and_syncs_cursor(db_session):
    run, execution, token = seed_run_with_lease(db_session)

    attempt = reserve(db_session, run, token)
    db_session.commit()

    assert attempt.dispatch_state == "reserved"
    assert attempt.usage_status == "unreconciled"
    assert attempt.input_tokens is None
    assert attempt.estimated_cost_microunits is None
    assert attempt.reserved_cost_microunits == 500
    db_session.refresh(execution)
    assert execution.budget_ledger_cursor == "ledger:1:0:500"


def test_FR_AUDIT_003_reserve_is_idempotent(db_session):
    run, _, token = seed_run_with_lease(db_session)
    ledger = BudgetLedger(db_session)

    first = reserve(db_session, run, token)
    second = reserve(db_session, run, token)
    db_session.commit()

    assert second.attempt_id == first.attempt_id
    totals = ledger.reconcile(run.id)
    assert totals.attempt_count == 1
    assert totals.reserved_outstanding_microunits == 500


def test_FR_AUDIT_003_reserve_enforces_budget_cap(db_session):
    run, _, token = seed_run_with_lease(db_session)
    reserve(db_session, run, token, reserved_cost_microunits=700, cap_microunits=1000)
    db_session.commit()

    with pytest.raises(BudgetExceededError):
        reserve(
            db_session,
            run,
            token,
            action_id="action-2",
            reservation_id="reservation-2",
            reserved_cost_microunits=400,
            cap_microunits=1000,
        )


def test_FR_AUDIT_003_reserve_rejects_stale_fencing_token(db_session):
    run, _, _ = seed_run_with_lease(db_session)

    with pytest.raises(LeaseNotHeldError):
        reserve(db_session, run, 999)


def test_FR_AUDIT_003_reserve_validates_role_and_currency(db_session):
    run, _, token = seed_run_with_lease(db_session)

    with pytest.raises(BudgetError):
        reserve(db_session, run, token, role="unknown-role")
    with pytest.raises(BudgetError):
        reserve(db_session, run, token, currency="usd")


def test_FR_AUDIT_003_dispatching_crash_stays_unreconciled(db_session):
    run, _, token = seed_run_with_lease(db_session)
    ledger = BudgetLedger(db_session)
    attempt = reserve(db_session, run, token)
    ledger.mark_dispatching(attempt.attempt_id, fencing_token=token, request_id="req-1")
    db_session.commit()

    # Simulated crash: no settle ever arrives.
    totals = ledger.reconcile(run.id)
    assert totals.unreconciled_attempt_ids == (attempt.attempt_id,)
    assert totals.reported_cost_microunits == 0
    # The reservation stays held; it is never treated as zero usage.
    assert totals.reserved_outstanding_microunits == 500

    # A dispatched attempt cannot be released as if never sent.
    with pytest.raises(AttemptStateError):
        ledger.release(attempt.attempt_id, fencing_token=token)


def test_FR_AUDIT_003_settle_is_idempotent_and_reports_usage(db_session):
    run, execution, token = seed_run_with_lease(db_session)
    ledger = BudgetLedger(db_session)
    attempt = reserve(db_session, run, token)
    ledger.mark_dispatching(attempt.attempt_id, fencing_token=token)
    db_session.commit()

    settled = ledger.settle(
        attempt.attempt_id,
        fencing_token=token,
        input_tokens=100,
        output_tokens=50,
        estimated_cost_microunits=420,
    )
    db_session.commit()
    assert settled.usage_status == "reported"
    assert settled.dispatch_state == "returned"

    totals = ledger.reconcile(run.id)
    assert totals.reported_cost_microunits == 420
    assert totals.reserved_outstanding_microunits == 0
    db_session.refresh(execution)
    assert execution.budget_ledger_cursor == "ledger:1:420:0"

    again = ledger.settle(
        attempt.attempt_id,
        fencing_token=token,
        input_tokens=100,
        output_tokens=50,
        estimated_cost_microunits=420,
    )
    assert again.attempt_id == attempt.attempt_id

    with pytest.raises(AttemptConflictError):
        ledger.settle(
            attempt.attempt_id,
            fencing_token=token,
            input_tokens=100,
            output_tokens=50,
            estimated_cost_microunits=421,
        )


def test_FR_AUDIT_003_settle_before_dispatch_is_refused(db_session):
    run, _, token = seed_run_with_lease(db_session)
    ledger = BudgetLedger(db_session)
    attempt = reserve(db_session, run, token)
    db_session.commit()

    with pytest.raises(AttemptStateError):
        ledger.settle(
            attempt.attempt_id,
            fencing_token=token,
            input_tokens=1,
            output_tokens=1,
            estimated_cost_microunits=1,
        )


def test_FR_AUDIT_003_release_frees_reservation(db_session):
    run, _, token = seed_run_with_lease(db_session)
    ledger = BudgetLedger(db_session)
    attempt = reserve(db_session, run, token)
    db_session.commit()

    released = ledger.release(attempt.attempt_id, fencing_token=token)
    db_session.commit()
    assert released.dispatch_state == "not_dispatched"

    totals = ledger.reconcile(run.id)
    assert totals.reserved_outstanding_microunits == 0
    assert totals.unreconciled_attempt_ids == ()


def test_FR_AGENT_004_persisted_budget_survives_restart(db_session):
    run, _, token = seed_run_with_lease(db_session)
    ledger = BudgetLedger(db_session)
    done = reserve(db_session, run, token)
    ledger.mark_dispatching(done.attempt_id, fencing_token=token)
    ledger.settle(
        done.attempt_id,
        fencing_token=token,
        input_tokens=10,
        output_tokens=5,
        estimated_cost_microunits=420,
    )
    stuck = reserve(
        db_session,
        run,
        token,
        action_id="action-2",
        reservation_id="reservation-2",
        reserved_cost_microunits=300,
    )
    ledger.mark_dispatching(stuck.attempt_id, fencing_token=token)
    db_session.commit()

    # A new session (the restarted process) reads the same ledger.
    engine = db_session.get_bind()
    with Session(engine) as other:
        totals = BudgetLedger(other).reconcile(run.id)
        assert totals.reported_cost_microunits == 420
        assert totals.reserved_outstanding_microunits == 300
        assert totals.unreconciled_attempt_ids == (stuck.attempt_id,)
        execution = other.get(RunExecution, run.id)
        assert execution.budget_ledger_cursor == totals.cursor
