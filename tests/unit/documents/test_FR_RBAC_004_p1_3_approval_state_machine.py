"""S1: P1-3 approval state machine (FR-RBAC-004, ADR-019 D1).

The four new transitions, the illegal ones around them, and the
fail-closed fact that neither new state is searchable and neither
is accepted by prepare_ingest's uploaded/queued whitelist (proved
here at the state-machine level; the pipeline layer is S2/S3).
"""

from __future__ import annotations

import pytest

from pivot.documents.errors import DocumentError
from pivot.domain.document_state import (
    STATES,
    is_searchable,
    next_state,
)


def test_FR_RBAC_004_p1_3_approval_states_exist() -> None:
    assert "pending_approval" in STATES
    assert "rejected" in STATES


def test_FR_RBAC_004_p1_3_approval_approve_transition() -> None:
    assert (
        next_state("pending_approval", "approve", "req_1") == "uploaded"
    )


def test_FR_RBAC_004_p1_3_approval_reject_transition() -> None:
    assert (
        next_state("pending_approval", "reject", "req_1") == "rejected"
    )


def test_FR_RBAC_004_p1_3_approval_withdraw_transition() -> None:
    assert (
        next_state("pending_approval", "withdraw", "req_1") == "uploaded"
    )


def test_FR_RBAC_004_p1_3_approval_resubmit_transition() -> None:
    assert (
        next_state("rejected", "resubmit", "req_1") == "pending_approval"
    )


def test_FR_RBAC_004_p1_3_approval_illegal_transitions() -> None:
    # A pending version cannot enter the pipeline or be decided twice.
    with pytest.raises(DocumentError):
        next_state("pending_approval", "enqueue", "req_1")
    with pytest.raises(DocumentError):
        next_state("pending_approval", "resubmit", "req_1")
    # A rejected version cannot be approved directly; it resubmits.
    with pytest.raises(DocumentError):
        next_state("rejected", "approve", "req_1")
    # An ordinary uploaded version has no approval event to answer.
    with pytest.raises(DocumentError):
        next_state("uploaded", "approve", "req_1")


def test_FR_RBAC_004_p1_3_approval_states_not_searchable() -> None:
    assert is_searchable("pending_approval", True, False) is False
    assert is_searchable("rejected", True, False) is False
    assert is_searchable("ready", True, False) is True
