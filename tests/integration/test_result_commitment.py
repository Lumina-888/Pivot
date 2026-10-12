"""Integration tests for ResultCommitmentUnitOfWork.

Tests the atomic commit_result transaction per 04-A contract.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from pivot.db.models import Claim, Citation, Conversation, Message, Run
from pivot.db.result_commit_uow import (
    CitationData,
    ClaimData,
    CommitmentUnitOfWork,
    IdempotencyConflictError,
    ResultCandidate,
    RunAlreadyTerminalError,
)
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now


def test_commit_result_creates_all_records_atomically(db_session):
    """Should create Claims/Citations/Message/ResultCommit/Outbox atomically."""
    conversation, run = create_test_run(db_session)
    uow = CommitmentUnitOfWork(db_session)

    candidate = ResultCandidate(
        result_id=new_id("run"),
        terminal_state="answered",
        claims=[
            ClaimData(text="Claim 1", support="supported", confidence=0.9),
            ClaimData(text="Claim 2", support="supported", confidence=0.8),
        ],
        citations=[
            CitationData(
                claim_index=0,
                document_id="doc-1",
                version_id="ver-1",
                chunk_id="chunk-1",
                locator="page 1",
                snippet="evidence",
            ),
            CitationData(
                claim_index=1,
                document_id="doc-1",
                version_id="ver-1",
                chunk_id="chunk-2",
                locator="page 2",
                snippet="evidence 2",
            ),
        ],
        final_markdown="# Answer\n\nClaim 1. Claim 2.",
        verification_version="0.1.0",
    )

    receipt = uow.commit_result(
        run_id=run.id,
        candidate=candidate,
        owner_id="user-1",
        conversation_id=conversation.id,
    )
    db_session.commit()

    # Verify all records created
    assert receipt.run_id == run.id
    assert receipt.is_idempotent_replay is False

    # Check Claims
    claims = db_session.query(Claim).filter_by(run_id=run.id).all()
    assert len(claims) == 2
    assert claims[0].text == "Claim 1"
    assert claims[1].text == "Claim 2"

    # Check Citations
    citations = db_session.query(Citation).filter_by(run_id=run.id).all()
    assert len(citations) == 2
    assert citations[0].claim_id == claims[0].id
    assert citations[1].claim_id == claims[1].id

    # Check Message
    message = db_session.get(Message, receipt.message_id)
    assert message is not None
    assert message.content == "# Answer\n\nClaim 1. Claim 2."
    assert message.sender == "assistant"

    # Check Run updated
    db_session.refresh(run)
    assert run.state == "answered"
    assert run.message_id == receipt.message_id
    assert run.completed_at is not None

    # Check ResultCommit
    from pivot.db.repositories.result_commits import ResultCommitRepository

    commit_repo = ResultCommitRepository(db_session)
    commit = commit_repo.get_by_run_id(run.id)
    assert commit is not None
    assert commit.result_id == candidate.result_id

    # Check Outbox event
    from pivot.db.repositories.outbox import OutboxRepository

    outbox_repo = OutboxRepository(db_session)
    events = outbox_repo.get_by_run_id(run.id)
    assert len(events) >= 1
    terminal_event = events[-1]
    assert terminal_event.event_name == "completed"


def test_commit_result_idempotent_same_result_id(db_session):
    """Should return existing receipt for same result_id."""
    conversation, run = create_test_run(db_session)
    uow = CommitmentUnitOfWork(db_session)

    result_id = new_id("run")
    candidate = ResultCandidate(
        result_id=result_id,
        terminal_state="answered",
        claims=[ClaimData(text="Claim 1", support="supported")],
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
        final_markdown="Answer",
        verification_version="0.1.0",
    )

    # First commit
    receipt1 = uow.commit_result(
        run_id=run.id,
        candidate=candidate,
        owner_id="user-1",
        conversation_id=conversation.id,
    )
    db_session.commit()

    # Second commit with same result_id
    receipt2 = uow.commit_result(
        run_id=run.id,
        candidate=candidate,
        owner_id="user-1",
        conversation_id=conversation.id,
    )

    assert receipt2.is_idempotent_replay is True
    assert receipt2.result_id == receipt1.result_id
    assert receipt2.message_id == receipt1.message_id

    # Should not create duplicate records
    claims = db_session.query(Claim).filter_by(run_id=run.id).all()
    assert len(claims) == 1  # Only one claim from first commit


def test_commit_result_rejects_different_result_id(db_session):
    """Should raise IdempotencyConflictError for different result_id."""
    conversation, run = create_test_run(db_session)
    uow = CommitmentUnitOfWork(db_session)

    candidate1 = ResultCandidate(
        result_id=new_id("run"),
        terminal_state="answered",
        claims=[ClaimData(text="Claim 1", support="supported")],
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
        final_markdown="Answer 1",
        verification_version="0.1.0",
    )

    # First commit
    uow.commit_result(
        run_id=run.id,
        candidate=candidate1,
        owner_id="user-1",
        conversation_id=conversation.id,
    )
    db_session.commit()

    # Try second commit with different result_id
    candidate2 = ResultCandidate(
        result_id=new_id("run"),  # Different result_id
        terminal_state="answered",
        claims=[ClaimData(text="Claim 2", support="supported")],
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
        final_markdown="Answer 2",
        verification_version="0.1.0",
    )

    with pytest.raises(IdempotencyConflictError):
        uow.commit_result(
            run_id=run.id,
            candidate=candidate2,
            owner_id="user-1",
            conversation_id=conversation.id,
        )


def test_commit_result_rejects_already_terminal_run(db_session):
    """Should raise RunAlreadyTerminalError if run is terminal."""
    conversation, run = create_test_run(db_session, initial_state="answered")
    uow = CommitmentUnitOfWork(db_session)

    candidate = ResultCandidate(
        result_id=new_id("run"),
        terminal_state="answered",
        claims=[ClaimData(text="Claim", support="supported")],
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
        final_markdown="Answer",
        verification_version="0.1.0",
    )

    with pytest.raises(RunAlreadyTerminalError):
        uow.commit_result(
            run_id=run.id,
            candidate=candidate,
            owner_id="user-1",
            conversation_id=conversation.id,
        )


def test_commit_result_transaction_rollback_on_failure(db_session):
    """Should rollback all changes if any step fails."""
    conversation, run = create_test_run(db_session)
    uow = CommitmentUnitOfWork(db_session)

    # Create candidate with invalid citation (non-existent chunk)
    candidate = ResultCandidate(
        result_id=new_id("run"),
        terminal_state="answered",
        claims=[ClaimData(text="Claim", support="supported")],
        citations=[
            CitationData(
                claim_index=0,
                document_id="nonexistent",
                version_id="nonexistent",
                chunk_id="nonexistent",  # Will fail FK constraint
                locator="page 1",
                snippet="evidence",
            )
        ],
        final_markdown="Answer",
        verification_version="0.1.0",
    )

    # Attempt commit - should fail on FK constraint
    with pytest.raises(IntegrityError):
        uow.commit_result(
            run_id=run.id,
            candidate=candidate,
            owner_id="user-1",
            conversation_id=conversation.id,
        )
        db_session.commit()

    db_session.rollback()

    # Verify nothing was committed
    claims = db_session.query(Claim).filter_by(run_id=run.id).all()
    assert len(claims) == 0

    messages = db_session.query(Message).filter_by(run_id=run.id).all()
    assert len(messages) == 0

    from pivot.db.repositories.result_commits import ResultCommitRepository

    commit_repo = ResultCommitRepository(db_session)
    assert commit_repo.exists(run.id) is False


def create_test_run(db_session, initial_state="planning"):
    """Helper to create a test conversation and run."""
    conversation = Conversation(
        id=new_id("run"),
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
