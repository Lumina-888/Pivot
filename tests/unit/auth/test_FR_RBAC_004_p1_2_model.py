"""S1: P1-2 model for FR-RBAC-004 (ADR-017 D1/D2).

Covers the port dataclasses (Membership.expires_at and the new
DocumentException) and the exception read/write methods on both
in-memory implementations. Expiry semantics, department expansion,
and visibility are S2/S3 concerns and are intentionally untouched:
reads return stored rows as-is, and a department-target grant is
never returned by get_exceptions_for_user.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fakes import InMemoryResources as FakeResources
from pivot.auth.ports import DocumentException, Membership
from pivot.http.memory import InMemoryResources as MemoryResources


def test_FR_RBAC_004_membership_expires_at_defaults_to_long_term() -> None:
    membership = Membership(
        user_id="usr_alice",
        dept_id="dept_tech",
        dept_role="editor",
        granted_by="usr_admin",
    )
    assert membership.expires_at is None


def test_FR_RBAC_004_membership_expires_at_round_trip() -> None:
    expires_at = datetime(2026, 12, 24, tzinfo=timezone.utc)
    membership = Membership(
        user_id="usr_alice",
        dept_id="dept_tech",
        dept_role="editor",
        granted_by="usr_admin",
        expires_at=expires_at,
    )
    assert membership.expires_at == expires_at


def test_FR_RBAC_004_exception_dataclass_defaults() -> None:
    exception = DocumentException(id="exc_1", document_id="doc_a")
    assert exception.target_user_id is None
    assert exception.target_dept_id is None
    assert exception.granted_by == ""
    assert exception.reason == ""
    assert exception.expires_at is None
    assert exception.created_at is None


def test_FR_RBAC_004_exception_crud_on_memory_implementations() -> None:
    personal = DocumentException(
        id="exc_personal",
        document_id="doc_a",
        target_user_id="usr_alice",
        granted_by="usr_admin",
        reason="cross-team review",
    )
    dept_grant = DocumentException(
        id="exc_dept",
        document_id="doc_a",
        target_dept_id="dept_art",
        granted_by="usr_admin",
        reason="joint project",
    )
    other_doc = DocumentException(
        id="exc_other",
        document_id="doc_b",
        target_user_id="usr_alice",
        granted_by="usr_admin",
    )
    for catalog in (FakeResources(), MemoryResources()):
        catalog.add_exception(personal)
        catalog.add_exception(dept_grant)
        catalog.add_exception(other_doc)
        by_doc = catalog.get_document_exceptions("doc_a")
        assert [item.id for item in by_doc] == ["exc_dept", "exc_personal"]
        assert catalog.get_document_exceptions("doc_missing") == ()
        # Department-target grants are stored, not expanded, in S1.
        by_user = catalog.get_exceptions_for_user("usr_alice")
        assert [item.id for item in by_user] == ["exc_other", "exc_personal"]
        assert catalog.get_exceptions_for_user("usr_ghost") == ()
        catalog.remove_exception("exc_personal")
        assert [item.id for item in catalog.get_document_exceptions("doc_a")] == [
            "exc_dept"
        ]
        catalog.remove_exception("exc_missing")  # no-op, no raise


def test_FR_RBAC_004_membership_expires_at_on_memory_implementations() -> None:
    expires_at = datetime(2026, 12, 24, tzinfo=timezone.utc)
    membership = Membership(
        user_id="usr_alice",
        dept_id="dept_tech",
        dept_role="reader",
        granted_by="usr_admin",
        expires_at=expires_at,
    )
    for catalog in (FakeResources(), MemoryResources()):
        catalog.add_membership(membership)
        stored = catalog.get_memberships("usr_alice")
        assert len(stored) == 1
        assert stored[0].expires_at == expires_at
