"""Repository ports for persistence consumers."""

from pivot.db.repositories.outbox import OutboxRepository
from pivot.db.repositories.result_commits import ResultCommitRepository

__all__ = ["OutboxRepository", "ResultCommitRepository"]
