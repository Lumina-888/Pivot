"""Fenced PostgreSQL Saver for LangGraph checkpoints.

Per 04-A §4.2: all framework writes must be protected by fencing.
Intercepts LangGraph Saver operations and validates lease + state_version.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from pivot.db.models import CheckpointBinding, RunExecution
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now

logger = logging.getLogger(__name__)


class LeaseViolationError(Exception):
    """Raised when a checkpoint write violates lease fencing."""

    pass


class StateVersionMismatchError(Exception):
    """Raised when state_version doesn't match expected value."""

    pass


class FencedCheckpointWriter:
    """
    Fenced checkpoint writer with lease and state_version validation.

    Per 04-A §4.2:
    - All framework writes must check lease token and state_version
    - Checkpoint success must be followed by binding update
    - Recovery only uses confirmed bindings
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def write_checkpoint(
        self,
        run_id: str,
        thread_id: str,
        checkpoint_id: str,
        checkpoint_data: dict[str, Any],
        fencing_token: int,
        expected_state_version: int,
    ) -> CheckpointBinding:
        """
        Write a checkpoint with fencing protection.

        Steps per 04-A:
        1. Lock RunExecution in PG transaction
        2. Verify fencing_token matches
        3. Verify state_version matches
        4. Write checkpoint data (TODO: integrate with LangGraph)
        5. Create unconfirmed CheckpointBinding
        6. Return binding for confirmation

        Args:
            run_id: The run to checkpoint
            thread_id: LangGraph thread ID
            checkpoint_id: Checkpoint identifier
            checkpoint_data: Serialized checkpoint (State after whitelist)
            fencing_token: Current lease token
            expected_state_version: Expected state version

        Returns:
            Unconfirmed CheckpointBinding

        Raises:
            LeaseViolationError: If fencing_token doesn't match
            StateVersionMismatchError: If state_version doesn't match
        """
        # Step 1: Lock RunExecution (SELECT ... FOR UPDATE)
        execution = (
            self.session.query(RunExecution)
            .filter(RunExecution.run_id == run_id)
            .with_for_update()
            .one_or_none()
        )

        if execution is None:
            raise ValueError(f"RunExecution not found for run {run_id}")

        # Step 2: Verify fencing token
        # TODO: Add lease table and verify token
        # For now, we'll add this in 04-D when implementing leases
        logger.debug(
            "Fencing check",
            extra={
                "run_id": run_id,
                "fencing_token": fencing_token,
            },
        )

        # Step 3: Verify state_version
        if execution.state_version != expected_state_version:
            raise StateVersionMismatchError(
                f"State version mismatch for run {run_id}: "
                f"expected {expected_state_version}, got {execution.state_version}"
            )

        # Step 4: Write checkpoint data
        # TODO: Integrate with actual LangGraph PostgresSaver
        # For now, this is a placeholder
        logger.info(
            "Writing checkpoint",
            extra={
                "run_id": run_id,
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "state_version": expected_state_version,
            },
        )

        # Step 5: Create unconfirmed CheckpointBinding
        binding = CheckpointBinding(
            id=new_id("checkpoint"),
            run_id=run_id,
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            state_version=execution.state_version,
            execution_epoch=execution.execution_epoch,
            fencing_token=fencing_token,
            graph_version=execution.graph_version,
            state_schema_version=execution.state_schema_version,
            budget_ledger_version=execution.budget_ledger_cursor,
            is_confirmed=False,  # Must be confirmed separately
            created_at=utc_now(),
        )

        self.session.add(binding)
        self.session.flush()

        return binding

    def confirm_checkpoint(self, binding_id: str) -> None:
        """
        Confirm a checkpoint binding after successful write.

        Per 04-A: only confirmed checkpoints are recoverable.
        Unconfirmed bindings are orphans kept for audit.

        Args:
            binding_id: The binding to confirm
        """
        binding = self.session.get(CheckpointBinding, binding_id)
        if binding is None:
            logger.warning(f"CheckpointBinding {binding_id} not found for confirmation")
            return

        binding.is_confirmed = True
        self.session.flush()

        # Update RunExecution current checkpoint reference
        execution = self.session.get(RunExecution, binding.run_id)
        if execution is not None:
            execution.current_checkpoint_id = binding.checkpoint_id
            execution.updated_at = utc_now()
            self.session.flush()

        logger.info(
            "Confirmed checkpoint",
            extra={
                "binding_id": binding_id,
                "run_id": binding.run_id,
                "checkpoint_id": binding.checkpoint_id,
            },
        )

    def get_latest_confirmed_binding(self, run_id: str) -> CheckpointBinding | None:
        """
        Get the latest confirmed checkpoint binding for recovery.

        Per 04-A: recovery only uses confirmed bindings.

        Args:
            run_id: The run to recover

        Returns:
            Latest confirmed binding, or None if no confirmed checkpoint exists
        """
        binding = (
            self.session.query(CheckpointBinding)
            .filter(
                CheckpointBinding.run_id == run_id,
                CheckpointBinding.is_confirmed == True,  # noqa: E712
            )
            .order_by(CheckpointBinding.state_version.desc())
            .first()
        )

        return binding


class StateWhitelist:
    """
    State field whitelist per 04-A §4.2.

    Removes sensitive fields before checkpoint:
    - credentials, tokens, connection objects
    - reasoning traces (per security requirement)
    - large transient data
    """

    ALLOWED_FIELDS = {
        # Core state
        "messages",
        "current_stage",
        "question",
        "scope",
        # Progress tracking
        "retrieval_results",
        "claims",
        "citations",
        # Budget and limits
        "budget_remaining",
        "steps_taken",
        # Public answer draft
        "answer_markdown",
    }

    FORBIDDEN_FIELDS = {
        # Security-sensitive
        "credentials",
        "tokens",
        "api_keys",
        "connections",
        # Privacy-sensitive
        "reasoning",
        "internal_thoughts",
        "debug_info",
    }

    @classmethod
    def sanitize(cls, state: dict[str, Any]) -> dict[str, Any]:
        """
        Sanitize state for checkpoint storage.

        Removes forbidden fields and only keeps allowed fields.

        Args:
            state: Raw agent state

        Returns:
            Sanitized state safe for persistence
        """
        sanitized = {}

        for key, value in state.items():
            if key in cls.FORBIDDEN_FIELDS:
                logger.debug(f"Removed forbidden field from checkpoint: {key}")
                continue

            if key in cls.ALLOWED_FIELDS:
                sanitized[key] = value

        return sanitized
