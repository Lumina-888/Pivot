"""SQLite proof for S4 cross-library moves (FR-RBAC-004, ADR-019 D3/D6).

Proves the move service through the real SQLAlchemy stores on
SQLite: the approve decision rewrites the document library, clears
the folder (O7), dispatches reconcile, and writes the move audit
event; and an audit-write failure rolls the decision, the library
rewrite, and the folder clear back together (the ADR-017 D4
same-transaction rule, mirrored on PostgreSQL in the db_pg group).
Seeding commits in order: users, then library and membership rows,
then documents.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from tests.unit.documents.fakes import MemoryObjects

from pivot.audit.service import AuditService
from pivot.auth.approvals import ApprovalService
from pivot.auth.moves import MoveService
from pivot.auth.ports import Principal
from pivot.db.audit import SqlAlchemyAuditStore
from pivot.db.base import Base
from pivot.db.documents import SqlAlchemyDocumentStore, SqlAlchemyVersionStore
from pivot.db.libraries import SqlAlchemyLibraryCatalog
from pivot.db.models.documents import Document as DocumentRow
from pivot.db.models.identity import Library as LibraryRow
from pivot.db.models.identity import Membership as MembershipRow
from pivot.db.models.identity import User as UserRow
from pivot.db.scoped import shared_session
from pivot.db.session import session_factory
from pivot.security.rbac import AccessControl

T0 = datetime(2026, 10, 26, 8, 0, tzinfo=UTC)
ADMIN = Principal("usr_admin", "admin", "admin", 0)
ALICE = Principal("usr_alice", "alice", "user", 1)
CAROL = Principal("usr_carol", "carol", "user", 1)


class _Clock:
    def now(self) -> datetime:
        return T0


@pytest.fixture
def assembly():
    engine = create_engine("sqlite://")
    for table in (
        "users",
        "libraries",
        "memberships",
        "documents",
        "move_requests",
        "audit_events",
    ):
        Base.metadata.tables[table].create(engine)
    sessions = session_factory(engine)
    with sessions() as session:
        for user_id, username, role in (
            ("usr_admin", "admin", "admin"),
            ("usr_alice", "alice", "user"),
            ("usr_carol", "carol", "user"),
            ("usr_frank", "frank", "user"),
        ):
            session.add(
                UserRow(
                    id=user_id, username=username, password_hash="hash",
                    role=role, status="active",
                )
            )
        session.commit()
        session.add(
            LibraryRow(
                id="dept_eng", name="技术部", kind="department",
                dept_id="dept_eng",
            )
        )
        session.add(
            LibraryRow(
                id="dept_art", name="美术部", kind="department",
                dept_id="dept_art",
            )
        )
        session.add(
            MembershipRow(
                user_id="usr_alice", dept_id="dept_eng",
                dept_role="dept_admin", granted_by="usr_admin",
            )
        )
        session.add(
            MembershipRow(
                user_id="usr_carol", dept_id="dept_art",
                dept_role="dept_admin", granted_by="usr_admin",
            )
        )
        session.commit()
        session.add(
            DocumentRow(
                id="doc_a", title="t", created_by="usr_frank",
                library_id="dept_eng", folder_id="fld_a",
            )
        )
        session.commit()
    catalog = SqlAlchemyLibraryCatalog(sessions)
    documents = SqlAlchemyDocumentStore(sessions)
    audit_store = SqlAlchemyAuditStore(sessions)
    audits = AuditService(audit_store, _Clock())
    access = AccessControl(catalog, clock=_Clock())
    approvals = ApprovalService(
        store=catalog,
        documents=documents,
        versions=SqlAlchemyVersionStore(sessions),
        objects=MemoryObjects(),
        access=access,
        audits=audits,
        clock=_Clock(),
    )
    dispatched: list = []
    service = MoveService(
        store=catalog,
        documents=documents,
        access=access,
        audits=audits,
        clock=_Clock(),
        approvals=approvals,
        transaction=lambda: shared_session(sessions),
        reconcile=lambda did, lid, rid, actor: dispatched.append(
            (did, documents.get(did).library_id, actor)
        ),
    )
    return catalog, documents, audit_store, service, dispatched


def _events(audit_store, action: str) -> tuple:
    return tuple(
        event for event in audit_store.list() if event.action == action
    )


def test_FR_RBAC_004_p1_3_move_flow_db(assembly) -> None:
    catalog, documents, audit_store, service, dispatched = assembly
    proposed = service.propose(ADMIN, "doc_a", "dept_art", "req_p1")
    assert proposed.status == "pending"
    decided = service.approve(CAROL, proposed.id, "req_a1")
    assert decided.status == "approved"
    assert decided.decided_by == "usr_carol"
    assert documents.get("doc_a").library_id == "dept_art"
    assert documents.get("doc_a").folder_id is None
    assert dispatched == [("doc_a", "dept_art", "usr_carol")]
    moved = _events(audit_store, "authz.library.move")
    assert len(moved) == 1
    assert moved[0].metadata["source_library_id"] == "dept_eng"
    assert moved[0].metadata["target_library_id"] == "dept_art"


def test_FR_RBAC_004_p1_3_move_audit_failure_rolls_back_db(
    assembly, monkeypatch
) -> None:
    catalog, documents, audit_store, service, dispatched = assembly
    proposed = service.propose(ADMIN, "doc_a", "dept_art", "req_p1")

    def _boom(*args, **kwargs) -> None:
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(SqlAlchemyAuditStore, "append", _boom)
    with pytest.raises(RuntimeError):
        service.approve(CAROL, proposed.id, "req_a1")
    # ADR-017 D4 same-transaction: the decision, the library
    # rewrite, and the folder clear all roll back together, and no
    # reconcile is dispatched for a refused move.
    assert catalog.get_move_request(proposed.id).status == "pending"
    assert documents.get("doc_a").library_id == "dept_eng"
    assert documents.get("doc_a").folder_id == "fld_a"
    assert dispatched == []
