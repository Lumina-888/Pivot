"""PostgreSQL fault test matrix (04-F).

Real processes against a real PostgreSQL, built by the Alembic
migrations. Each test injects the crash window it names: a process
killed mid-transaction, a writer killed between checkpoint write
and confirm, a stalled executor whose lease is taken over. All
synchronization is deadline-based polling or events, never fixed
sleeps on the assertion path.
"""

import multiprocessing as mp
import time
from datetime import timedelta
from pathlib import Path

import pytest
from pivot.agent.checkpoint import FencedCheckpointWriter
from pivot.agent.recovery import NoConfirmedCheckpointError, RecoveryManager
from pivot.db.lease import LeaseHeldError, LeaseManager
from pivot.db.models import (
    CheckpointBinding,
    Chunk,
    Claim,
    Conversation,
    Document,
    DocumentVersion,
    ResultCommit,
    Run,
    RunExecution,
    RunLease,
    User,
)
from pivot.db.result_commit_uow import (
    CitationData,
    ClaimData,
    CommitmentUnitOfWork,
    ResultCandidate,
)
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

CTX = mp.get_context("fork")
DEADLINE_S = 60

LOCKED_VERSIONS = {
    "graph_version": "graph-1",
    "state_schema_version": "state-1",
    "prompt_version": "prompt-1",
    "tools_version": "tools-1",
    "model_version": "model-1",
    "dependencies_lock_version": "lock-1",
    "budget_policy_version": "budget-1",
}


def seed_run(session, *, with_chunks=False):
    session.add(
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
        title="PG fault test",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(conversation)
    run = Run(
        id=new_id("run"),
        conversation_id=conversation.id,
        question="PG fault test question",
        idempotency_key=new_id("run"),
        state="planning",
        created_at=utc_now(),
    )
    session.add(run)
    session.flush()
    session.add(
        RunExecution(
            run_id=run.id,
            thread_id=f"thread-{run.id}",
            state_version=0,
            execution_epoch=0,
            budget_ledger_cursor=None,
            original_deadline_at=utc_now() + timedelta(days=1),
            **LOCKED_VERSIONS,
        )
    )
    if with_chunks:
        session.add(Document(id="doc-1", title="Doc 1", created_by="user-1"))
        session.add(
            DocumentVersion(
                id="ver-1",
                document_id="doc-1",
                content_sha256="0" * 64,
                storage_key="doc-1/ver-1",
            )
        )
        session.add(
            Chunk(
                id="chunk-1", version_id="ver-1", text="evidence", text_hash="hash-1"
            )
        )
        session.add(
            Chunk(
                id="chunk-2",
                version_id="ver-1",
                text="evidence 2",
                text_hash="hash-2",
            )
        )
    session.commit()
    return run.id, conversation.id


def candidate(result_id):
    return ResultCandidate(
        result_id=result_id,
        terminal_state="answered",
        claims=[ClaimData(text="Claim 1", support="supported", confidence=0.9)],
        citations=[
            CitationData(
                claim_index=0,
                document_id="doc-1",
                version_id="ver-1",
                chunk_id="chunk-1",
                locator="page 1",
                snippet="evidence",
            )
        ],
        final_markdown="# Answer\n\nClaim 1.",
        verification_version="0.1.0",
    )


def child_session(url):
    engine = create_engine(url)
    return engine, sessionmaker(bind=engine)()


def wait_until(predicate, description):
    deadline = time.monotonic() + DEADLINE_S
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for: {description}")


# --- Child processes -------------------------------------------------------


def _child_acquire(url, run_id, executor_id, barrier, queue):
    _, session = child_session(url)
    barrier.wait(timeout=DEADLINE_S)
    try:
        token = LeaseManager(session).acquire(
            run_id, executor_id, ttl=timedelta(minutes=5)
        )
        session.commit()
        queue.put((executor_id, "ok", token.fencing_token))
    except LeaseHeldError:
        session.rollback()
        queue.put((executor_id, "held", None))
    finally:
        session.close()


def _child_commit_then_hang(url, run_id, conversation_id, marker, queue):
    _, session = child_session(url)
    token = LeaseManager(session).acquire(
        run_id, "executor-doomed", ttl=timedelta(minutes=5)
    )
    session.commit()
    uow = CommitmentUnitOfWork(session)
    uow.commit_result(
        run_id=run_id,
        candidate=candidate(new_id("run")),
        owner_id="user-1",
        conversation_id=conversation_id,
        fencing_token=token.fencing_token,
    )
    # Writes are flushed inside an open transaction; nothing is
    # committed. The parent now kills this process: the connection
    # dies and PostgreSQL must roll the transaction back.
    Path(marker).write_text("staged", encoding="utf-8")
    queue.put("staged")
    time.sleep(300)


def _child_write_checkpoint_then_hang(url, run_id, queue):
    _, session = child_session(url)
    token = LeaseManager(session).acquire(
        run_id, "executor-doomed", ttl=timedelta(minutes=5)
    )
    session.commit()
    writer = FencedCheckpointWriter(session)
    binding = writer.write_checkpoint(
        run_id=run_id,
        thread_id=f"thread-{run_id}",
        checkpoint_id="ckpt-doomed",
        checkpoint_data={"messages": []},
        fencing_token=token.fencing_token,
        expected_state_version=0,
    )
    session.commit()
    queue.put(binding.id)
    time.sleep(300)


def _child_complete_run(url, run_id, queue):
    _, session = child_session(url)
    token = LeaseManager(session).acquire(
        run_id, "executor-1", ttl=timedelta(minutes=5)
    )
    session.commit()
    writer = FencedCheckpointWriter(session)
    binding = writer.write_checkpoint(
        run_id=run_id,
        thread_id=f"thread-{run_id}",
        checkpoint_id="ckpt-restart",
        checkpoint_data={"messages": []},
        fencing_token=token.fencing_token,
        expected_state_version=0,
    )
    session.flush()
    writer.confirm_checkpoint(binding.id)
    session.commit()
    queue.put("done")


def _child_stalled_holder(url, run_id, conversation_id, acquired, release, queue):
    _, session = child_session(url)
    token = LeaseManager(session).acquire(
        run_id, "executor-stale", ttl=timedelta(seconds=3)
    )
    session.commit()
    acquired.set()
    release.wait(timeout=DEADLINE_S)
    try:
        CommitmentUnitOfWork(session).commit_result(
            run_id=run_id,
            candidate=candidate(new_id("run")),
            owner_id="user-1",
            conversation_id=conversation_id,
            fencing_token=token.fencing_token,
        )
        session.commit()
        queue.put("committed")
    except Exception as exc:  # reported to the parent verbatim
        session.rollback()
        queue.put(type(exc).__name__)
    finally:
        session.close()


# --- Matrix ----------------------------------------------------------------


def test_FR_AGENT_006_only_one_executor_per_run(pg_session, pg_url):
    run_id, _ = seed_run(pg_session)
    barrier = CTX.Barrier(2)
    queue = CTX.Queue()
    children = [
        CTX.Process(
            target=_child_acquire,
            args=(pg_url, run_id, f"executor-{n}", barrier, queue),
        )
        for n in (1, 2)
    ]
    for child in children:
        child.start()
    results = [queue.get(timeout=DEADLINE_S) for _ in children]
    for child in children:
        child.join(timeout=DEADLINE_S)

    outcomes = sorted(outcome for _, outcome, _ in results)
    assert outcomes == ["held", "ok"]
    winner = next(r for r in results if r[1] == "ok")
    assert winner[2] == 1
    lease = pg_session.get(RunLease, run_id)
    assert lease.executor_id == winner[0]
    assert lease.fencing_token == 1


def test_FR_AGENT_006_result_commit_kill_rolls_back(pg_session, pg_url, tmp_path):
    run_id, conversation_id = seed_run(pg_session, with_chunks=True)
    marker = tmp_path / "staged.txt"
    queue = CTX.Queue()
    child = CTX.Process(
        target=_child_commit_then_hang,
        args=(pg_url, run_id, conversation_id, str(marker), queue),
    )
    child.start()
    assert queue.get(timeout=DEADLINE_S) == "staged"
    child.kill()
    child.join(timeout=DEADLINE_S)

    # The killed transaction left nothing behind.
    assert pg_session.query(ResultCommit).count() == 0
    assert pg_session.query(Claim).count() == 0
    run = pg_session.get(Run, run_id)
    assert run.state == "planning"
    execution = pg_session.get(RunExecution, run_id)
    assert execution.state_version == 0

    # A fresh executor (after the dead holder's lease is expired by
    # the harness, standing in for time passing) commits cleanly.
    pg_session.execute(
        text("UPDATE run_leases SET expires_at = :past WHERE run_id = :run_id"),
        {"past": utc_now() - timedelta(minutes=1), "run_id": run_id},
    )
    pg_session.commit()
    token = LeaseManager(pg_session).acquire(
        run_id, "executor-2", ttl=timedelta(minutes=5)
    )
    pg_session.commit()
    receipt = CommitmentUnitOfWork(pg_session).commit_result(
        run_id=run_id,
        candidate=candidate(new_id("run")),
        owner_id="user-1",
        conversation_id=conversation_id,
        fencing_token=token.fencing_token,
    )
    pg_session.commit()
    assert receipt is not None
    assert pg_session.query(ResultCommit).count() == 1


def test_FR_AGENT_006_checkpoint_kill_before_confirm_fails_closed(
    pg_session, pg_url
):
    run_id, _ = seed_run(pg_session)
    queue = CTX.Queue()
    child = CTX.Process(
        target=_child_write_checkpoint_then_hang, args=(pg_url, run_id, queue)
    )
    child.start()
    binding_id = queue.get(timeout=DEADLINE_S)
    child.kill()
    child.join(timeout=DEADLINE_S)

    binding = pg_session.get(CheckpointBinding, binding_id)
    assert binding is not None
    assert binding.is_confirmed is False
    execution = pg_session.get(RunExecution, run_id)
    assert execution.current_checkpoint_id is None

    # Recovery stays fail-closed: an unconfirmed binding is no source.
    with pytest.raises(NoConfirmedCheckpointError):
        RecoveryManager(pg_session).recover_from_checkpoint(
            run_id, owner_id="user-1", current_versions=dict(LOCKED_VERSIONS)
        )


def test_FR_AGENT_006_restart_from_checkpoint(pg_session, pg_url):
    run_id, _ = seed_run(pg_session)
    queue = CTX.Queue()
    child = CTX.Process(
        target=_child_complete_run, args=(pg_url, run_id, queue)
    )
    child.start()
    assert queue.get(timeout=DEADLINE_S) == "done"
    child.join(timeout=DEADLINE_S)
    assert child.exitcode == 0

    # A brand-new session (the restarted process) recovers.
    context = RecoveryManager(pg_session).recover_from_checkpoint(
        run_id, owner_id="user-1", current_versions=dict(LOCKED_VERSIONS)
    )
    pg_session.commit()
    assert context.checkpoint_id == "ckpt-restart"
    assert context.execution_epoch == 1


def test_FR_AGENT_006_stale_executor_commit_rejected_after_takeover(
    pg_session, pg_url
):
    run_id, conversation_id = seed_run(pg_session, with_chunks=True)
    acquired = CTX.Event()
    release = CTX.Event()
    queue = CTX.Queue()
    child = CTX.Process(
        target=_child_stalled_holder,
        args=(pg_url, run_id, conversation_id, acquired, release, queue),
    )
    child.start()
    assert acquired.wait(timeout=DEADLINE_S)

    # Wait for the stalled holder's lease to really expire.
    def lease_expired():
        pg_session.expire_all()
        lease = pg_session.get(RunLease, run_id)
        expires = lease.expires_at
        if expires.tzinfo is None:
            from datetime import UTC

            expires = expires.replace(tzinfo=UTC)
        return expires < utc_now()

    wait_until(lease_expired, "stalled holder lease expiry")

    # The new executor takes over and commits its result.
    token = LeaseManager(pg_session).acquire(
        run_id, "executor-2", ttl=timedelta(minutes=5)
    )
    assert token.fencing_token == 2
    pg_session.commit()
    CommitmentUnitOfWork(pg_session).commit_result(
        run_id=run_id,
        candidate=candidate(new_id("run")),
        owner_id="user-1",
        conversation_id=conversation_id,
        fencing_token=token.fencing_token,
    )
    pg_session.commit()

    # The stalled executor wakes and tries to commit with token 1.
    # Rejection may come from the competing-result conflict gate,
    # the terminal gate, or the fencing gate; the invariant is that
    # it writes nothing.
    release.set()
    outcome = queue.get(timeout=DEADLINE_S)
    child.join(timeout=DEADLINE_S)
    assert outcome in {
        "IdempotencyConflictError",
        "LeaseNotHeldError",
        "LeaseViolationError",
        "RunAlreadyTerminalError",
    }
    assert pg_session.query(ResultCommit).count() == 1
