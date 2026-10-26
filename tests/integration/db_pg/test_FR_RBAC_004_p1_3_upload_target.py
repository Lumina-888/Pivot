"""Real PostgreSQL proof for S3 upload-with-target (FR-RBAC-004,
ADR-019 D1/D2).

Targeted uploads and the self-approval fast path against the
production stores whose schema comes from the Alembic migrations.
Skipped without PIVOT_TEST_PG_URL. Seeding commits in the CI #240/#256
order: users first, then library rows, then membership rows, then
documents, versions, and requests, so every foreign-key target exists
before its referrer is inserted.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pivot.audit.service import AuditService
from pivot.auth.approvals import ApprovalService
from pivot.auth.errors import AuthError
from pivot.auth.ports import Principal
from pivot.db.audit import SqlAlchemyAuditStore
from pivot.db.documents import (
    SqlAlchemyChunkStore,
    SqlAlchemyDocumentStore,
    SqlAlchemyTaskStore,
    SqlAlchemyVersionStore,
)
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import Membership as MembershipRow
from pivot.db.models.identity import User as UserRow
from pivot.db.scoped import shared_session
from pivot.db.session import session_factory
from pivot.documents.service import DocumentService
from pivot.security.rbac import AccessControl

from tests.unit.documents.fakes import MemoryAudits, MemoryObjects, pdf_bytes

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
ADMIN = Principal("usr_admin", "admin", "admin", 0)
ALICE = Principal("usr_alice", "alice", "user", 1)
FRANK = Principal("usr_frank", "frank", "user", 1)


class _Clock:
    def now(self) -> datetime:
        return NOW


def _seed(pg_session) -> None:
    for user_id, username, role in (
        ("usr_admin", "admin", "admin"),
        ("usr_alice", "alice", "user"),
        ("usr_frank", "frank", "user"),
    ):
        pg_session.add(
            UserRow(
                id=user_id, username=username, password_hash="hash",
                role=role, status="active",
            )
        )
    pg_session.commit()
    for library_id, name, kind, dept_id in (
        ("pub", "公共库", "public", None),
        ("dept_eng", "技术部", "department", "dept_eng"),
    ):
        pg_session.add(
            LibraryRow(
                id=library_id, name=name, kind=kind, dept_id=dept_id,
            )
        )
    pg_session.commit()
    pg_session.add(
        MembershipRow(
            user_id="usr_alice", dept_id="dept_eng",
            dept_role="dept_admin", granted_by="usr_admin",
        )
    )
    pg_session.add(
        MembershipRow(
            user_id="usr_frank", dept_id="dept_eng",
            dept_role="editor", granted_by="usr_admin",
        )
    )
    pg_session.commit()


def _assembly(pg_engine):
    sessions = session_factory(pg_engine)
    catalog = SqlAlchemyLibraryCatalog(sessions)
    documents = SqlAlchemyDocumentStore(sessions)
    versions = SqlAlchemyVersionStore(sessions)
    audit_store = SqlAlchemyAuditStore(sessions)
    audits = AuditService(audit_store, _Clock())
    access = AccessControl(catalog, clock=_Clock())
    dispatched: list = []
    objects = MemoryObjects()
    approvals = ApprovalService(
        store=catalog,
        documents=documents,
        versions=versions,
        objects=objects,
        access=access,
        audits=audits,
        clock=_Clock(),
        transaction=lambda: shared_session(sessions),
        ingest=lambda vid, rid, actor: dispatched.append((vid, actor)),
    )
    doc_service = DocumentService(
        documents=documents,
        versions=versions,
        chunks=SqlAlchemyChunkStore(sessions),
        tasks=SqlAlchemyTaskStore(sessions),
        objects=objects,
        audits=MemoryAudits(),
    )
    return catalog, documents, versions, audit_store, approvals, doc_service, dispatched


def _events(audit_store, action: str) -> tuple:
    return tuple(
        event for event in audit_store.list() if event.action == action
    )


def test_FR_RBAC_004_p1_3_upload_target_pending_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    _, documents, versions, audit_store, approvals, doc_service, dispatched = _assembly(
        pg_engine
    )
    library = approvals.validate_upload_target(FRANK, "dept_eng", "req_tgt")
    version = doc_service.upload(
        filename="handbook.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes() + b"pg-target",
        title="handbook",
        actor_id="usr_frank",
        request_id="req_up",
        target_library_id="dept_eng",
    )
    assert version.state == "pending_approval"
    request = approvals.create_upload_request(
        principal=FRANK,
        document_id=version.document_id,
        version_id=version.id,
        library=library,
        http_request_id="req_create",
    )
    assert request.status == "pending"
    doc = documents.get(version.document_id)
    assert doc.library_id == "unassigned"
    assert dispatched == []
    assert len(_events(audit_store, "doc.approval.requested")) == 1


def test_FR_RBAC_004_p1_3_upload_self_approve_pg(
    pg_session, pg_engine
) -> None:
    _seed(pg_session)
    _, documents, versions, audit_store, approvals, doc_service, dispatched = _assembly(
        pg_engine
    )
    library = approvals.validate_upload_target(ALICE, "dept_eng", "req_tgt")
    version = doc_service.upload(
        filename="handbook.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes() + b"pg-self",
        title="handbook",
        actor_id="usr_alice",
        request_id="req_up",
        target_library_id="dept_eng",
    )
    assert version.state == "pending_approval"
    request = approvals.create_upload_request(
        principal=ALICE,
        document_id=version.document_id,
        version_id=version.id,
        library=library,
        http_request_id="req_create",
    )
    assert approvals.is_approver(ALICE, library) is True
    decided = approvals.approve(ALICE, request.id, "req_approve")
    assert decided.status == "approved"
    assert versions.get(version.id).state == "uploaded"
    assert documents.get(version.document_id).library_id == "dept_eng"
    assert len(_events(audit_store, "authz.approval.approved")) == 1
    assert len(dispatched) == 1
    # The route-level gate still refuses cross-department targets.
    with pytest.raises(AuthError) as excinfo:
        approvals.validate_upload_target(FRANK, "missing_lib", "req_no")
    assert excinfo.value.code == "RESOURCE_NOT_FOUND"
