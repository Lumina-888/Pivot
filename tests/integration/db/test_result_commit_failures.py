"""Failure-scenario tests for ResultCommitmentUnitOfWork (04-B task 1.3).

Covers the four failure scenarios from the ND-AGENT-04 next-steps list:
mid-write crash rollback, reentry after a post-commit crash, competing
commits, and foreign-key constraint failure rollback.

Like test_result_commitment.py, this module enables SQLite foreign key
enforcement locally for PostgreSQL parity. True multi-process racing
against real PostgreSQL belongs to 04-F; the competing-commit scenario
here uses two sequential sessions on one engine.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pivot.db.base import Base
from pivot.db.models import (
    Chunk,
    Claim,
    Citation,
    Conversation,
    Document,
    DocumentVersion,
    Message,
    PublicEventOutbox,
    Run,
    User,
)
from pivot.db.repositories.outbox import OutboxRepository
from pivot.db.repositories.result_commits import ResultCommitRepository
from pivot.db.result_commit_uow import (
    CitationData,
    ClaimData,
    CommitmentUnitOfWork,
    IdempotencyConflictError,
    ResultCandidate,
)
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now


@pytest.fixture
def db_session() -> Iterator[Session]:
    """SQLite session with foreign key enforcement (PostgreSQL parity)."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def seed_fk_parents(db_session):
    """Seed the User/Document/Version/Chunk rows citations reference."""
    db_session.add(
        User(
            id="user-1",
            username="user-1",
            password_hash="hash",
            role="user",
            status="active",
        )
    )
    db_session.add(Document(id="doc-1", title="Doc 1", created_by="user-1"))
    db_session.add(
        DocumentVersion(
            id="ver-1",
            document_id="doc-1",
            content_sha256="0" * 64,
            storage_key="doc-1/ver-1",
        )
    )
    db_session.add(
        Chunk(id="chunk-1", version_id="ver-1", text="evidence", text_hash="hash-1")
    )
    db_session.commit()


def create_test_run(db_session, initial_state="planning"):
    """Helper to create a test conversation and run."""
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
        state=initial_state,
        created_at=utc_now(),
    )
    db_session.add(run)
    db_session.commit()

    return conversation, run


def make_candidate(result_id, claim_text="Claim 1", chunk_id="chunk-1", claim_index=0):
    return ResultCandidate(
        result_id=result_id,
        terminal_state="answered",
        claims=[ClaimData(text=claim_text, support="supported", confidence=0.9)],
        citations=[
            CitationData(
                claim_index=claim_index,
                document_id="doc-1",
                version_id="ver-1",
                chunk_id=chunk_id,
                locator="page 1",
                snippet="evidence",
            )
        ],
        final_markdown="Answer",
        verification_version="0.1.0",
    )


def assert_nothing_committed(db_session, run_id):
    """Assert a failed commit left no records and the run is untouched."""
    db_session.expire_all()
    assert db_session.query(Claim).filter_by(run_id=run_id).count() == 0
    assert db_session.query(Citation).filter_by(run_id=run_id).count() == 0
    assert db_session.query(Message).filter_by(run_id=run_id).count() == 0
    assert db_session.query(PublicEventOutbox).filter_by(run_id=run_id).count() == 0
    assert ResultCommitRepository(db_session).exists(run_id) is False
    run = db_session.get(Run, run_id)
    assert run.state == "planning"
    assert run.message_id is None
    assert run.completed_at is None


def test_commit_failure_mid_write_rolls_back_everything(db_session):
    """Crash after claims are flushed: the whole transaction rolls back."""
    seed_fk_parents(db_session)
    conversation, run = create_test_run(db_session)
    uow = CommitmentUnitOfWork(db_session)

    # claim_index 3 does not exist: Step 4 raises IndexError after the
    # Step 3 claims have already been added and flushed.
    candidate = make_candidate(new_id("run"), claim_index=3)

    with pytest.raises(IndexError):
        uow.commit_result(
            run_id=run.id,
            candidate=candidate,
            owner_id="user-1",
            conversation_id=conversation.id,
        )
    db_session.rollback()

    assert_nothing_committed(db_session, run.id)


def test_commit_fk_violation_rolls_back_everything(db_session):
    """A citation pointing at a missing chunk fails the whole commit."""
    seed_fk_parents(db_session)
    conversation, run = create_test_run(db_session)
    uow = CommitmentUnitOfWork(db_session)

    candidate = make_candidate(new_id("run"), chunk_id="chunk-missing")

    with pytest.raises(IntegrityError):
        uow.commit_result(
            run_id=run.id,
            candidate=candidate,
            owner_id="user-1",
            conversation_id=conversation.id,
        )
    db_session.rollback()

    assert_nothing_committed(db_session, run.id)


def test_reentry_after_commit_returns_replay_without_duplicates(db_session):
    """Reentry with a fresh session replays the receipt, writes nothing."""
    seed_fk_parents(db_session)
    conversation, run = create_test_run(db_session)
    candidate = make_candidate(new_id("run"))

    receipt1 = CommitmentUnitOfWork(db_session).commit_result(
        run_id=run.id,
        candidate=candidate,
        owner_id="user-1",
        conversation_id=conversation.id,
    )
    db_session.commit()

    # Simulate a caller that crashed after the commit and retries with a
    # brand new session and unit of work.
    engine = db_session.get_bind()
    with Session(engine) as other_session:
        receipt2 = CommitmentUnitOfWork(other_session).commit_result(
            run_id=run.id,
            candidate=candidate,
            owner_id="user-1",
            conversation_id=conversation.id,
        )
        assert receipt2.is_idempotent_replay is True
        assert receipt2.result_id == receipt1.result_id
        assert receipt2.message_id == receipt1.message_id
        assert other_session.query(Claim).filter_by(run_id=run.id).count() == 1
        assert other_session.query(Citation).filter_by(run_id=run.id).count() == 1
        assert other_session.query(Message).filter_by(run_id=run.id).count() == 1
        events = OutboxRepository(other_session).get_by_run_id(run.id)
        assert len(events) == 1


def test_competing_commit_with_different_result_is_rejected(db_session):
    """A second commit with a different result_id writes nothing."""
    seed_fk_parents(db_session)
    conversation, run = create_test_run(db_session)

    winner = make_candidate(new_id("run"), claim_text="Winner claim")
    CommitmentUnitOfWork(db_session).commit_result(
        run_id=run.id,
        candidate=winner,
        owner_id="user-1",
        conversation_id=conversation.id,
    )
    db_session.commit()

    engine = db_session.get_bind()
    with Session(engine) as other_session:
        loser = make_candidate(new_id("run"), claim_text="Loser claim")
        with pytest.raises(IdempotencyConflictError):
            CommitmentUnitOfWork(other_session).commit_result(
                run_id=run.id,
                candidate=loser,
                owner_id="user-1",
                conversation_id=conversation.id,
            )
        other_session.rollback()

        claims = other_session.query(Claim).filter_by(run_id=run.id).all()
        assert len(claims) == 1
        assert claims[0].text == "Winner claim"
        commit = ResultCommitRepository(other_session).get_by_run_id(run.id)
        assert commit.result_id == winner.result_id
