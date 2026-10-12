"""Unit tests for ResultCommitRepository."""

import pytest
from sqlalchemy.exc import IntegrityError

from pivot.db.models import ResultCommit, Run
from pivot.db.repositories.result_commits import ResultCommitRepository
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now


def test_get_by_run_id_returns_none_when_not_exists(db_session):
    """Should return None when result commit doesn't exist."""
    repo = ResultCommitRepository(db_session)
    result = repo.get_by_run_id("nonexistent")
    assert result is None


def test_exists_returns_false_when_not_exists(db_session):
    """Should return False when result commit doesn't exist."""
    repo = ResultCommitRepository(db_session)
    assert repo.exists("nonexistent") is False


def test_create_inserts_new_commit(db_session, sample_run):
    """Should create a new result commit."""
    repo = ResultCommitRepository(db_session)

    commit = ResultCommit(
        run_id=sample_run.id,
        result_id=new_id("run"),
        message_id=new_id("run"),
        terminal_state="answered",
        verification_version="0.1.0",
        committed_at=utc_now(),
    )

    result = repo.create(commit)
    db_session.commit()

    assert result.run_id == sample_run.id
    assert repo.exists(sample_run.id) is True


def test_create_raises_on_duplicate_run_id(db_session, sample_run):
    """Should raise IntegrityError when run_id already has a commit."""
    repo = ResultCommitRepository(db_session)

    commit1 = ResultCommit(
        run_id=sample_run.id,
        result_id=new_id("run"),
        message_id=new_id("run"),
        terminal_state="answered",
        verification_version="0.1.0",
        committed_at=utc_now(),
    )
    repo.create(commit1)
    db_session.commit()

    # Try to create another commit for same run
    commit2 = ResultCommit(
        run_id=sample_run.id,
        result_id=new_id("run"),
        message_id=new_id("run"),
        terminal_state="answered",
        verification_version="0.1.0",
        committed_at=utc_now(),
    )

    with pytest.raises(IntegrityError):
        repo.create(commit2)
        db_session.commit()


def test_get_by_run_id_returns_existing_commit(db_session, sample_run):
    """Should retrieve existing result commit."""
    repo = ResultCommitRepository(db_session)

    result_id = new_id("run")
    commit = ResultCommit(
        run_id=sample_run.id,
        result_id=result_id,
        message_id=new_id("run"),
        terminal_state="answered",
        verification_version="0.1.0",
        committed_at=utc_now(),
    )
    repo.create(commit)
    db_session.commit()

    retrieved = repo.get_by_run_id(sample_run.id)
    assert retrieved is not None
    assert retrieved.result_id == result_id
    assert retrieved.terminal_state == "answered"


@pytest.fixture
def sample_run(db_session):
    """Create a sample run for testing."""
    from pivot.db.models import Conversation

    # Create conversation first
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
        state="planning",
        created_at=utc_now(),
    )
    db_session.add(run)
    db_session.commit()
    return run
