"""Run execution metadata and checkpoint binding models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pivot.db.base import Base
from pivot.shared.time import utc_now


class RunExecution(Base):
    """
    Execution metadata for a Run.

    Tracks version bindings, budget cursor, and execution epoch.
    Per 04-A §4: version-locked recovery requires all components match.
    """

    __tablename__ = "run_executions"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id"), primary_key=True, nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    graph_version: Mapped[str] = mapped_column(String(64), nullable=False)
    state_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    tools_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    dependencies_lock_version: Mapped[str] = mapped_column(String(64), nullable=False)
    budget_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)

    # Fencing and versioning
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Current checkpoint reference
    current_checkpoint_id: Mapped[str | None] = mapped_column(String(255))

    # Budget tracking
    budget_ledger_cursor: Mapped[str | None] = mapped_column(String(255))

    # Deadline from original request
    original_deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    run: Mapped["Run"] = relationship(back_populates="execution")


class CheckpointBinding(Base):
    """
    Binding between a Run and a confirmed checkpoint.

    Per 04-A §4.2: only confirmed checkpoints are recoverable.
    Unconfirmed writes are orphans, kept for audit but not for recovery.
    """

    __tablename__ = "checkpoint_bindings"
    __table_args__ = (
        UniqueConstraint("run_id", "state_version", name="uq_checkpoint_run_version"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Version tracking
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)

    # Version lock - must match RunExecution versions
    graph_version: Mapped[str] = mapped_column(String(64), nullable=False)
    state_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    budget_ledger_version: Mapped[str | None] = mapped_column(String(64))

    # Confirmation flag
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run: Mapped["Run"] = relationship()


if TYPE_CHECKING:
    from pivot.db.models.conversations import Run
