"""S1: P1-3 approval/move request storage on the memory path
(FR-RBAC-004, ADR-019 D1/D3).

The memory catalog mirrors the PostgreSQL partial unique index in
Python: a second pending request for the same document raises
ValueError (PostgreSQL raises IntegrityError; the S2/S4 service
pre-checks and maps either to a clean rejection).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pivot.auth.ports import ApprovalRequest, MoveRequest
from pivot.http.memory import InMemoryResources

T0 = datetime(2026, 10, 26, 8, 0, tzinfo=UTC)


def _approval(request_id: str, status: str) -> ApprovalRequest:
    return ApprovalRequest(
        id=request_id, document_id="doc_a", version_id="ver_a",
        target_library_id="dept_eng", proposer="usr_admin",
        status=status, created_at=T0,
    )


def _move(request_id: str, status: str) -> MoveRequest:
    return MoveRequest(
        id=request_id, document_id="doc_a",
        source_library_id="dept_eng", target_library_id="dept_eng",
        proposer="usr_admin", status=status, created_at=T0,
    )


def test_FR_RBAC_004_p1_3_memory_approval_request_crud() -> None:
    store = InMemoryResources()
    assert store.get_approval_request("ap_1") is None
    store.add_approval_request(_approval("ap_1", "pending"))
    row = store.get_approval_request("ap_1")
    assert row is not None and row.status == "pending"
    assert [item.id for item in store.list_approval_requests("doc_a")] == [
        "ap_1"
    ]
    store.set_approval_request(_approval("ap_1", "approved"))
    assert store.get_approval_request("ap_1").status == "approved"


def test_FR_RBAC_004_p1_3_memory_approval_request_pending_unique() -> None:
    store = InMemoryResources()
    store.add_approval_request(_approval("ap_1", "pending"))
    with pytest.raises(ValueError):
        store.add_approval_request(_approval("ap_2", "pending"))
    store.add_approval_request(_approval("ap_3", "approved"))
    with pytest.raises(ValueError):
        store.set_approval_request(_approval("ap_3", "pending"))


def test_FR_RBAC_004_p1_3_memory_move_request_crud() -> None:
    store = InMemoryResources()
    store.add_move_request(_move("mv_1", "pending"))
    row = store.get_move_request("mv_1")
    assert row is not None
    assert row.reconcile_status == "pending"
    assert row.reconcile_attempts == 0
    store.set_move_request(
        MoveRequest(
            id="mv_1", document_id="doc_a",
            source_library_id="dept_eng", target_library_id="dept_eng",
            proposer="usr_admin", status="approved", created_at=T0,
            reconcile_status="ok", reconcile_attempts=1,
        )
    )
    row = store.get_move_request("mv_1")
    assert row is not None and row.reconcile_status == "ok"
    assert row.reconcile_attempts == 1
    assert [item.id for item in store.list_move_requests("doc_a")] == [
        "mv_1"
    ]


def test_FR_RBAC_004_p1_3_memory_move_request_pending_unique() -> None:
    store = InMemoryResources()
    store.add_move_request(_move("mv_1", "pending"))
    with pytest.raises(ValueError):
        store.add_move_request(_move("mv_2", "pending"))
