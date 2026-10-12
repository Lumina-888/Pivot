"""Repository for ResultCommit persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pivot.db.models import ResultCommit


class ResultCommitRepository:
    """Repository for managing immutable result commitments."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_run_id(self, run_id: str) -> ResultCommit | None:
        """Get result commit by run_id."""
        return self.session.get(ResultCommit, run_id)

    def exists(self, run_id: str) -> bool:
        """Check if result commit exists for a run."""
        stmt = select(ResultCommit.run_id).where(ResultCommit.run_id == run_id)
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def create(self, commit: ResultCommit) -> ResultCommit:
        """
        Create a new result commit.

        Raises:
            IntegrityError: If a commit already exists for this run_id.
        """
        self.session.add(commit)
        self.session.flush()
        return commit
