"""Tests for RecoveryManager (04-C recovery logic).

Implements the recovery slice of the Red list planned in 04-A section 7:
version mismatch fails closed, recovery rechecks authorization, and a
restart resumes only from a confirmed checkpoint with the epoch
incremented and the persisted budget cursor preserved.
"""

from datetime import timedelta

import pytest

from pivot.agent.checkpoint import FencedCheckpointWriter
from pivot.agent.recovery import (
    NoConfirmedCheckpointError,
    RecoveryDeadlineExceededError,
    RecoveryManager,
    RecoveryNotAuthorizedError,
    RecoveryVersionMismatchError,
    RunTerminalRecoveryError,
)
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


def seed_recoverable_run(
    db_session,
    *,
    confirm=True,
    run_state="planning",
    user_status="active",
    deadline=None,
):
    """Seed a run with a written (and by default confirmed) checkpoint."""
    db_session.add(
        User(
            id="user-1",
            username="user-1",
            password_hash="hash",
            role="user",
            status=user_status,
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
    execution = RunExecution(
        run_id=run.id,
        thread_id="thread-1",
        state_version=0,
        execution_epoch=0,
        current_checkpoint_id=None,
        budget_ledger_cursor="ledger-42",
        original_deadline_at=deadline or (utc_now() + timedelta(days=1)),
        **LOCKED_VERSIONS,
    )
    db_session.add(execution)
    db_session.commit()

    if confirm is not None:
        writer = FencedCheckpointWriter(db_session)
        binding = writer.write_checkpoint(
            run_id=run.id,
            thread_id="thread-1",
            checkpoint_id="ckpt-1",
            checkpoint_data={"messages": []},
            fencing_token=1,
            expected_state_version=0,
        )
        if confirm:
            writer.confirm_checkpoint(binding.id)
        db_session.commit()
    return conversation, run, execution


def recover(db_session, run, **overrides):
    kwargs = {"owner_id": "user-1", "current_versions": dict(LOCKED_VERSIONS)}
    kwargs.update(overrides)
    return RecoveryManager(db_session).recover_from_checkpoint(run.id, **kwargs)


def test_FR_AGENT_006_restart_from_checkpoint(db_session):
    conversation, run, execution = seed_recoverable_run(db_session)

    context = recover(db_session, run)

    assert context.run_id == run.id
    assert context.conversation_id == conversation.id
    assert context.owner_id == "user-1"
    assert context.thread_id == "thread-1"
    assert context.checkpoint_id == "ckpt-1"
    assert context.state_version == 0
    # Epoch increments before the new graph invocation, and persists.
    assert context.execution_epoch == 1
    db_session.refresh(execution)
    assert execution.execution_epoch == 1
    # Budget position comes from the persisted ledger cursor.
    assert context.budget_ledger_cursor == "ledger-42"
    assert context.versions == LOCKED_VERSIONS


def test_FR_AGENT_006_version_mismatch_fails_closed(db_session):
    _, run, execution = seed_recoverable_run(db_session)
    current = dict(LOCKED_VERSIONS)
    current["model_version"] = "model-2"

    with pytest.raises(RecoveryVersionMismatchError) as excinfo:
        recover(db_session, run, current_versions=current)

    fields = [m.field for m in excinfo.value.result.mismatches]
    assert fields == ["model_version"]
    # A refused recovery must not consume an epoch.
    db_session.refresh(execution)
    assert execution.execution_epoch == 0


def test_FR_AGENT_006_missing_current_version_fails_closed(db_session):
    _, run, _ = seed_recoverable_run(db_session)
    current = dict(LOCKED_VERSIONS)
    del current["graph_version"]

    with pytest.raises(RecoveryVersionMismatchError):
        recover(db_session, run, current_versions=current)


def test_FR_AGENT_006_restore_rechecks_authorization(db_session):
    _, run, _ = seed_recoverable_run(db_session)

    with pytest.raises(RecoveryNotAuthorizedError):
        recover(db_session, run, owner_id="user-2")


def test_FR_AGENT_006_restore_rejects_inactive_user(db_session):
    _, run, _ = seed_recoverable_run(db_session, user_status="disabled")

    with pytest.raises(RecoveryNotAuthorizedError):
        recover(db_session, run)


def test_recovery_refuses_terminal_run(db_session):
    _, run, _ = seed_recoverable_run(db_session, run_state="answered")

    with pytest.raises(RunTerminalRecoveryError):
        recover(db_session, run)


def test_recovery_requires_confirmed_checkpoint(db_session):
    _, run, _ = seed_recoverable_run(db_session, confirm=False)

    with pytest.raises(NoConfirmedCheckpointError):
        recover(db_session, run)


def test_recovery_deadline_exceeded_fails_closed(db_session):
    _, run, _ = seed_recoverable_run(
        db_session, deadline=utc_now() - timedelta(hours=1)
    )

    with pytest.raises(RecoveryDeadlineExceededError):
        recover(db_session, run)
