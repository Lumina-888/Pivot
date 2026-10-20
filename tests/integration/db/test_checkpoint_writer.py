"""Tests for FencedCheckpointWriter (04-C checkpoint framework).

The writer had no test coverage before ND-AGENT-04 S2. These tests pin
the binding lifecycle from 04-A section 4.2: a checkpoint write creates
an unconfirmed binding, only confirmation makes it recoverable, and a
state_version mismatch rejects the write.
"""

from datetime import timedelta

import pytest

from pivot.agent.checkpoint import (
    FencedCheckpointWriter,
    StateVersionMismatchError,
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


def seed_run_with_execution(db_session):
    """Seed an owner, conversation, run and its RunExecution lock."""
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
        thread_id="thread-1",
        state_version=0,
        execution_epoch=0,
        current_checkpoint_id=None,
        budget_ledger_cursor="ledger-42",
        original_deadline_at=utc_now() + timedelta(days=1),
        **LOCKED_VERSIONS,
    )
    db_session.add(execution)
    db_session.commit()
    return conversation, run, execution


def write_one(writer, run, checkpoint_id="ckpt-1", expected_state_version=0):
    return writer.write_checkpoint(
        run_id=run.id,
        thread_id="thread-1",
        checkpoint_id=checkpoint_id,
        checkpoint_data={"messages": []},
        fencing_token=1,
        expected_state_version=expected_state_version,
    )


def test_FR_AGENT_006_checkpoint_write_creates_unconfirmed_binding(db_session):
    _, run, _ = seed_run_with_execution(db_session)
    writer = FencedCheckpointWriter(db_session)

    binding = write_one(writer, run)

    assert binding.is_confirmed is False
    assert binding.run_id == run.id
    assert binding.checkpoint_id == "ckpt-1"
    assert binding.state_version == 0
    assert binding.graph_version == "graph-1"
    assert binding.state_schema_version == "state-1"
    assert binding.budget_ledger_version == "ledger-42"
    # An unconfirmed write is an orphan: not a recovery source.
    assert writer.get_latest_confirmed_binding(run.id) is None


def test_FR_AGENT_006_confirm_checkpoint_marks_binding_recoverable(db_session):
    _, run, execution = seed_run_with_execution(db_session)
    writer = FencedCheckpointWriter(db_session)
    binding = write_one(writer, run)

    writer.confirm_checkpoint(binding.id)
    db_session.commit()

    latest = writer.get_latest_confirmed_binding(run.id)
    assert latest is not None
    assert latest.id == binding.id
    db_session.refresh(execution)
    assert execution.current_checkpoint_id == "ckpt-1"


def test_FR_AGENT_006_checkpoint_write_rejects_state_version_mismatch(db_session):
    _, run, _ = seed_run_with_execution(db_session)
    writer = FencedCheckpointWriter(db_session)

    with pytest.raises(StateVersionMismatchError):
        write_one(writer, run, expected_state_version=7)


def test_FR_AGENT_006_latest_confirmed_binding_picks_highest_state_version(
    db_session,
):
    _, run, execution = seed_run_with_execution(db_session)
    writer = FencedCheckpointWriter(db_session)

    first = write_one(writer, run, checkpoint_id="ckpt-1", expected_state_version=0)
    writer.confirm_checkpoint(first.id)

    execution.state_version = 1
    db_session.flush()
    second = write_one(writer, run, checkpoint_id="ckpt-2", expected_state_version=1)
    writer.confirm_checkpoint(second.id)
    db_session.commit()

    latest = writer.get_latest_confirmed_binding(run.id)
    assert latest is not None
    assert latest.checkpoint_id == "ckpt-2"
    assert latest.state_version == 1
