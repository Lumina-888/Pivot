"""S1: library model for FR-RBAC-004 (ADR-016 D1/D2).

Covers the port dataclasses, the ResourceCatalog extensions
(get_memberships / get_library) on both in-memory implementations,
and the DocumentRecord library_id default. authorize_document
behavior is intentionally untouched in S1 (S2 owns it).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fakes import InMemoryResources as FakeResources
from pivot.auth.ports import Library, Membership
from pivot.documents.ports import DocumentRecord
from pivot.http.memory import InMemoryResources as MemoryResources


def test_FR_RBAC_004_library_dataclass_defaults() -> None:
    library = Library(id="dept_tech", name="技术部", kind="department", dept_id="dept_tech")
    assert library.dept_id == "dept_tech"
    public = Library(id="pub", name="公共库", kind="public")
    assert public.dept_id is None


def test_FR_RBAC_004_membership_dataclass_fields() -> None:
    granted_at = datetime(2026, 10, 24, tzinfo=timezone.utc)
    membership = Membership(
        user_id="usr_alice",
        dept_id="dept_tech",
        dept_role="editor",
        granted_by="usr_admin",
        granted_at=granted_at,
    )
    assert membership.dept_role == "editor"
    assert membership.granted_by == "usr_admin"
    assert membership.granted_at == granted_at


def test_FR_RBAC_004_catalog_get_library_hit_and_miss() -> None:
    for catalog in (FakeResources(), MemoryResources()):
        catalog.libraries["pub"] = Library(id="pub", name="公共库", kind="public")
        assert catalog.get_library("pub") is not None
        assert catalog.get_library("pub").kind == "public"
        assert catalog.get_library("missing") is None


def test_FR_RBAC_004_catalog_get_memberships_multi_department() -> None:
    for catalog in (FakeResources(), MemoryResources()):
        catalog.memberships["usr_alice"] = (
            Membership(
                user_id="usr_alice",
                dept_id="dept_tech",
                dept_role="editor",
                granted_by="usr_admin",
            ),
            Membership(
                user_id="usr_alice",
                dept_id="dept_art",
                dept_role="reader",
                granted_by="usr_admin",
            ),
        )
        found = catalog.get_memberships("usr_alice")
        assert {item.dept_id for item in found} == {"dept_tech", "dept_art"}
        assert catalog.get_memberships("usr_nobody") == ()


def test_FR_RBAC_004_document_record_library_defaults_to_unassigned() -> None:
    document = DocumentRecord(
        id="doc_1", title="t", space="shared", created_by="usr_admin"
    )
    assert document.library_id == "unassigned"
    explicit = DocumentRecord(
        id="doc_2",
        title="t",
        space="shared",
        created_by="usr_admin",
        library_id="pub",
    )
    assert explicit.library_id == "pub"
