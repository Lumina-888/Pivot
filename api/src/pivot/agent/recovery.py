"""Recovery of a Run from its latest confirmed checkpoint.

Implements the persistence-layer half of the 04-A section 4.2 recovery
protocol and AGENT_SPEC section 8:

- A terminal Run is never recovered into the graph; it only replays
  committed business facts, which is the caller's job.
- Authorization is rechecked against live records: the conversation
  owner must match the caller and the user must still be active.
  Stored checkpoint context never authorizes anything by itself.
- The RunExecution version lock must match the current environment
  (fail closed, see version_check.py), and the original deadline must
  not have passed.
- Only the latest confirmed CheckpointBinding is a recovery source;
  unconfirmed orphan writes are ignored, and the binding must agree
  with the RunExecution record.
- execution_epoch is incremented before any new graph invocation, and
  the budget position comes from the persisted ledger cursor, never
  from a possibly stale checkpoint snapshot.

Out of scope at this layer: scope and document eligibility are
re-derived by the caller from the returned context against live
resource state before any model call, and lease verification joins
this flow in 04-D (no lease token is taken yet).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC

from pivot.agent.checkpoint import FencedCheckpointWriter
from pivot.agent.version_check import VersionChecker, VersionCheckResult
from pivot.db.models import Conversation, Run, RunExecution, User
from pivot.runs.machine import is_terminal
from pivot.shared.time import utc_now
from sqlalchemy.orm import Session


class RecoveryError(Exception):
    """Base exception for recovery failures."""


class NoConfirmedCheckpointError(RecoveryError):
    """Raised when a Run has no confirmed checkpoint to recover from."""


class RecoveryVersionMismatchError(RecoveryError):
    """Raised when the version lock does not match the environment."""

    def __init__(self, result: VersionCheckResult) -> None:
        self.result = result
        fields = ", ".join(m.field for m in result.mismatches)
        super().__init__(f"Version mismatch for recovery: {fields}")


class RecoveryNotAuthorizedError(RecoveryError):
    """Raised when the caller may not recover this Run."""


class RunTerminalRecoveryError(RecoveryError):
    """Raised when recovering a Run that is already terminal."""


class RecoveryDeadlineExceededError(RecoveryError):
    """Raised when the Run's original deadline has passed."""


@dataclass(frozen=True)
class RecoveredContext:
    """Trusted context for resuming a Run, rebuilt from live records."""

    run_id: str
    conversation_id: str
    owner_id: str
    thread_id: str
    checkpoint_id: str
    state_version: int
    execution_epoch: int
    budget_ledger_cursor: str | None
    versions: dict[str, str]


class RecoveryManager:
    """Rebuilds a recoverable context for a Run, or fails closed."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._writer = FencedCheckpointWriter(session)
        self._versions = VersionChecker()

    def recover_from_checkpoint(
        self,
        run_id: str,
        *,
        owner_id: str,
        current_versions: Mapping[str, str],
    ) -> RecoveredContext:
        """Recover ``run_id`` for ``owner_id`` under ``current_versions``.

        Raises a RecoveryError subclass on every refusal; on success the
        RunExecution epoch has already been incremented and flushed.
        """
        run = self.session.get(Run, run_id)
        if run is None:
            raise RecoveryError(f"Run {run_id} not found")
        if is_terminal(run.state):
            raise RunTerminalRecoveryError(
                f"Run {run_id} is terminal ({run.state}); replay only"
            )

        conversation = self.session.get(Conversation, run.conversation_id)
        if conversation is None or conversation.owner_id != owner_id:
            raise RecoveryNotAuthorizedError(
                f"Caller is not the owner of run {run_id}"
            )
        user = self.session.get(User, owner_id)
        if user is None or user.status != "active":
            raise RecoveryNotAuthorizedError(
                f"Owner {owner_id} is not an active user"
            )

        execution = self.session.get(RunExecution, run_id)
        if execution is None:
            raise RecoveryError(f"RunExecution not found for run {run_id}")

        result = self._versions.verify_compatibility(execution, current_versions)
        if not result.compatible:
            raise RecoveryVersionMismatchError(result)

        deadline = execution.original_deadline_at
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        if utc_now() > deadline:
            raise RecoveryDeadlineExceededError(
                f"Run {run_id} passed its original deadline {deadline.isoformat()}"
            )

        binding = self._writer.get_latest_confirmed_binding(run_id)
        if binding is None:
            raise NoConfirmedCheckpointError(
                f"Run {run_id} has no confirmed checkpoint"
            )
        if (
            binding.graph_version != execution.graph_version
            or binding.state_schema_version != execution.state_schema_version
            or binding.checkpoint_id != execution.current_checkpoint_id
        ):
            raise RecoveryError(
                f"Confirmed binding for run {run_id} is inconsistent "
                "with its RunExecution record"
            )

        execution.execution_epoch += 1
        execution.updated_at = utc_now()
        self.session.flush()

        return RecoveredContext(
            run_id=run_id,
            conversation_id=run.conversation_id,
            owner_id=owner_id,
            thread_id=execution.thread_id,
            checkpoint_id=binding.checkpoint_id,
            state_version=binding.state_version,
            execution_epoch=execution.execution_epoch,
            budget_ledger_cursor=execution.budget_ledger_cursor,
            versions=self._versions.locked_versions(execution),
        )
