"""Tests for LeaseManager and fencing integration (04-D).

Implements the lease slice of the protocol in 04-A sections 3 and
4.1: monotonic fencing tokens, single live holder, takeover only
after expiry, renew that cannot revive a stale token, release that
keeps the counter row, and write paths that reject stale executors.
Multi-process contention proof belongs to 04-F on real PostgreSQL.
"""

from datetime import timedelta

import pytest

from pivot.agent.checkpoint import FencedCheckpointWriter, LeaseViolationError
from pivot.db.lease import (
    LeaseClaimRefusedError,
    LeaseHeldError,
    LeaseManager,
    LeaseNotHeldError,
)
from pivot.db.models import Conversation, Run, RunExecution, RunLease, User
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

TTL = timedelta(hours=1)


def seed_run(db_session, *, run_state="planning", deadline=None):
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
        state=run_state,
        created_at=utc_now(),
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(
        RunExecution(
            run_id=run.id,
            thread_id=f"thread-{run.id}",
            state_version=0,
            execution_epoch=0,
            budget_ledger_cursor="ledger-42",
            original_deadline_at=deadline or (utc_now() + timedelta(days=1)),
            **LOCKED_VERSIONS,
        )
    )
    db_session.commit()
    return run


def force_expire(db_session, run_id):
    lease = db_session.get(RunLease, run_id)
    lease.expires_at = utc_now() - timedelta(minutes=1)
    db_session.commit()


def test_FR_AGENT_006_lease_acquire_issues_first_token(db_session):
    run = seed_run(db_session)

    token = LeaseManager(db_session).acquire(run.id, "executor-1", ttl=TTL)
    db_session.commit()

    assert token.fencing_token == 1
    assert token.executor_id == "executor-1"
    lease = db_session.get(RunLease, run.id)
    assert lease.executor_id == "executor-1"
    assert lease.fencing_token == 1


def test_FR_AGENT_006_lease_acquire_refused_while_held(db_session):
    run = seed_run(db_session)
    manager = LeaseManager(db_session)
    manager.acquire(run.id, "executor-1", ttl=TTL)
    db_session.commit()

    with pytest.raises(LeaseHeldError):
        manager.acquire(run.id, "executor-2", ttl=TTL)


def test_FR_AGENT_006_lease_takeover_after_expiry_increments_token(db_session):
    run = seed_run(db_session)
    manager = LeaseManager(db_session)
    first = manager.acquire(run.id, "executor-1", ttl=TTL)
    db_session.commit()
    force_expire(db_session, run.id)

    second = manager.acquire(run.id, "executor-2", ttl=TTL)
    db_session.commit()

    assert first.fencing_token == 1
    assert second.fencing_token == 2
    assert second.executor_id == "executor-2"


def test_FR_AGENT_006_lease_renew_extends_expiry(db_session):
    run = seed_run(db_session)
    manager = LeaseManager(db_session)
    token = manager.acquire(run.id, "executor-1", ttl=timedelta(minutes=5))
    db_session.commit()

    renewed = manager.renew(token, ttl=timedelta(hours=2))
    db_session.commit()

    assert renewed.fencing_token == token.fencing_token
    assert renewed.expires_at > token.expires_at


def test_FR_AGENT_006_lease_renew_with_stale_token_is_refused(db_session):
    run = seed_run(db_session)
    manager = LeaseManager(db_session)
    stale = manager.acquire(run.id, "executor-1", ttl=TTL)
    db_session.commit()
    force_expire(db_session, run.id)
    manager.acquire(run.id, "executor-2", ttl=TTL)
    db_session.commit()

    with pytest.raises(LeaseNotHeldError):
        manager.renew(stale, ttl=TTL)


def test_FR_AGENT_006_lease_release_keeps_counter_row(db_session):
    run = seed_run(db_session)
    manager = LeaseManager(db_session)
    token = manager.acquire(run.id, "executor-1", ttl=TTL)
    db_session.commit()

    manager.release(token)
    db_session.commit()

    lease = db_session.get(RunLease, run.id)
    assert lease is not None
    assert lease.executor_id is None
    assert lease.fencing_token == 1

    # The counter is not reset: the next claim continues the sequence.
    nxt = manager.acquire(run.id, "executor-2", ttl=TTL)
    assert nxt.fencing_token == 2


def test_FR_AGENT_006_lease_stale_release_cannot_clear_new_holder(db_session):
    run = seed_run(db_session)
    manager = LeaseManager(db_session)
    stale = manager.acquire(run.id, "executor-1", ttl=TTL)
    db_session.commit()
    force_expire(db_session, run.id)
    manager.acquire(run.id, "executor-2", ttl=TTL)
    db_session.commit()

    with pytest.raises(LeaseNotHeldError):
        manager.release(stale)

    lease = db_session.get(RunLease, run.id)
    assert lease.executor_id == "executor-2"
    assert lease.fencing_token == 2


def test_FR_AGENT_006_lease_claim_refused_for_terminal_run(db_session):
    run = seed_run(db_session, run_state="answered")

    with pytest.raises(LeaseClaimRefusedError):
        LeaseManager(db_session).acquire(run.id, "executor-1", ttl=TTL)


def test_FR_AGENT_006_lease_claim_refused_after_deadline(db_session):
    run = seed_run(db_session, deadline=utc_now() - timedelta(hours=1))

    with pytest.raises(LeaseClaimRefusedError):
        LeaseManager(db_session).acquire(run.id, "executor-1", ttl=TTL)


def test_FR_AGENT_006_fencing_rejects_stale_executor(db_session):
    """A paused executor whose lease was taken over cannot write checkpoints."""
    run = seed_run(db_session)
    manager = LeaseManager(db_session)
    stale = manager.acquire(run.id, "executor-1", ttl=TTL)
    db_session.commit()
    force_expire(db_session, run.id)
    current = manager.acquire(run.id, "executor-2", ttl=TTL)
    db_session.commit()

    writer = FencedCheckpointWriter(db_session)
    with pytest.raises(LeaseViolationError):
        writer.write_checkpoint(
            run_id=run.id,
            thread_id=f"thread-{run.id}",
            checkpoint_id="ckpt-stale",
            checkpoint_data={"messages": []},
            fencing_token=stale.fencing_token,
            expected_state_version=0,
        )
    db_session.rollback()

    binding = writer.write_checkpoint(
        run_id=run.id,
        thread_id=f"thread-{run.id}",
        checkpoint_id="ckpt-current",
        checkpoint_data={"messages": []},
        fencing_token=current.fencing_token,
        expected_state_version=0,
    )
    assert binding.checkpoint_id == "ckpt-current"
    assert binding.fencing_token == current.fencing_token
