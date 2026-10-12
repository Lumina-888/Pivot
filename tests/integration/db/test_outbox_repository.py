"""Unit tests for OutboxRepository."""

import pytest

from pivot.db.models import PublicEventOutbox, Run
from pivot.db.repositories.outbox import OutboxRepository
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now


def test_get_by_run_id_returns_empty_when_no_events(db_session):
    """Should return empty list when no events exist."""
    repo = OutboxRepository(db_session)
    events = repo.get_by_run_id("nonexistent")
    assert events == []


def test_get_by_run_id_returns_ordered_by_seq(db_session, sample_run):
    """Should return events ordered by seq."""
    repo = OutboxRepository(db_session)

    # Create events in random order
    event2 = PublicEventOutbox(
        event_id=new_id("event"),
        run_id=sample_run.id,
        seq=2,
        publication_key="key-2",
        event_name="retrieving",
        envelope='{"event": "retrieving"}',
        projection_version="0.1.0",
        created_at=utc_now(),
    )
    event1 = PublicEventOutbox(
        event_id=new_id("event"),
        run_id=sample_run.id,
        seq=1,
        publication_key="key-1",
        event_name="planning",
        envelope='{"event": "planning"}',
        projection_version="0.1.0",
        created_at=utc_now(),
    )

    db_session.add(event2)
    db_session.add(event1)
    db_session.commit()

    events = repo.get_by_run_id(sample_run.id)
    assert len(events) == 2
    assert events[0].seq == 1
    assert events[1].seq == 2


def test_get_undispatched_returns_only_undispatched(db_session, sample_run):
    """Should return only undispatched events."""
    repo = OutboxRepository(db_session)

    dispatched = PublicEventOutbox(
        event_id=new_id("event"),
        run_id=sample_run.id,
        seq=1,
        publication_key="key-1",
        event_name="planning",
        envelope='{"event": "planning"}',
        projection_version="0.1.0",
        created_at=utc_now(),
        dispatched_at=utc_now(),
    )
    undispatched = PublicEventOutbox(
        event_id=new_id("event"),
        run_id=sample_run.id,
        seq=2,
        publication_key="key-2",
        event_name="retrieving",
        envelope='{"event": "retrieving"}',
        projection_version="0.1.0",
        created_at=utc_now(),
    )

    db_session.add(dispatched)
    db_session.add(undispatched)
    db_session.commit()

    events = repo.get_undispatched()
    assert len(events) == 1
    assert events[0].seq == 2


def test_append_event_inserts_new_event(db_session, sample_run):
    """Should append a new event to outbox."""
    repo = OutboxRepository(db_session)

    event = PublicEventOutbox(
        event_id=new_id("event"),
        run_id=sample_run.id,
        seq=1,
        publication_key="key-1",
        event_name="planning",
        envelope='{"event": "planning"}',
        projection_version="0.1.0",
        created_at=utc_now(),
    )

    result = repo.append_event(event)
    db_session.commit()

    assert result.event_id == event.event_id
    events = repo.get_by_run_id(sample_run.id)
    assert len(events) == 1


def test_append_event_rejects_duplicate_seq(db_session, sample_run):
    """Should reject duplicate (run_id, seq)."""
    repo = OutboxRepository(db_session)

    event1 = PublicEventOutbox(
        event_id=new_id("event"),
        run_id=sample_run.id,
        seq=1,
        publication_key="key-1",
        event_name="planning",
        envelope='{"event": "planning"}',
        projection_version="0.1.0",
        created_at=utc_now(),
    )
    repo.append_event(event1)
    db_session.commit()

    # Try to append another event with same seq
    event2 = PublicEventOutbox(
        event_id=new_id("event"),
        run_id=sample_run.id,
        seq=1,  # Same seq
        publication_key="key-2",
        event_name="retrieving",
        envelope='{"event": "retrieving"}',
        projection_version="0.1.0",
        created_at=utc_now(),
    )

    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        repo.append_event(event2)
        db_session.commit()


def test_mark_dispatched_updates_timestamp(db_session, sample_run):
    """Should mark event as dispatched."""
    repo = OutboxRepository(db_session)

    event = PublicEventOutbox(
        event_id=new_id("event"),
        run_id=sample_run.id,
        seq=1,
        publication_key="key-1",
        event_name="planning",
        envelope='{"event": "planning"}',
        projection_version="0.1.0",
        created_at=utc_now(),
    )
    repo.append_event(event)
    db_session.commit()

    # Mark as dispatched
    repo.mark_dispatched(event.event_id)
    db_session.commit()

    # Verify it's no longer in undispatched
    undispatched = repo.get_undispatched()
    assert len(undispatched) == 0

    # Verify dispatched_at is set
    retrieved = db_session.get(PublicEventOutbox, event.event_id)
    assert retrieved.dispatched_at is not None


def test_get_next_seq_returns_zero_for_empty_run(db_session, sample_run):
    """Should return 0 when run has no events."""
    repo = OutboxRepository(db_session)
    seq = repo.get_next_seq(sample_run.id)
    assert seq == 0


def test_get_next_seq_returns_incremented_value(db_session, sample_run):
    """Should return max_seq + 1."""
    repo = OutboxRepository(db_session)

    event = PublicEventOutbox(
        event_id=new_id("event"),
        run_id=sample_run.id,
        seq=5,
        publication_key="key-1",
        event_name="planning",
        envelope='{"event": "planning"}',
        projection_version="0.1.0",
        created_at=utc_now(),
    )
    repo.append_event(event)
    db_session.commit()

    next_seq = repo.get_next_seq(sample_run.id)
    assert next_seq == 6


@pytest.fixture
def sample_run(db_session):
    """Create a sample run for testing."""
    from pivot.db.models import Conversation

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
