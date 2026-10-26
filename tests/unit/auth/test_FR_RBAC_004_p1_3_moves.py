"""S4: cross-library move approvals for FR-RBAC-004 (ADR-019 D3, D6).

Single-sided target approval (Q3), one pending move per document,
approve order (close, rewrite library, clear folder per O7, then
dispatch reconcile), exceptions following the document, and the
scope-before-state order from the S2 fix applied to every move
decision path.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fakes import FakeClock
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.approvals import ApprovalService
from pivot.auth.errors import AuthError
from pivot.auth.moves import MoveService
from pivot.auth.ports import (
    DocumentAuthz,
    DocumentException,
    FolderMembership,
    Library,
    Membership,
    Principal,
)
from pivot.documents.errors import DocumentError
from pivot.documents.ports import DocumentRecord
from pivot.http.memory import (
    InMemoryResources,
    MemoryDocuments,
    MemoryVersions,
)
from pivot.security.rbac import AccessControl
from tests.unit.documents.fakes import MemoryObjects

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
ENG_ADMIN = Principal(user_id="usr_alice", username="alice", role="user", token_version=1)
ART_ADMIN = Principal(user_id="usr_carol", username="carol", role="user", token_version=1)
LEAD = Principal(user_id="usr_bob", username="bob", role="user", token_version=1)
EDITOR = Principal(user_id="usr_frank", username="frank", role="user", token_version=1)
PX_EDITOR = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
OUTSIDER = Principal(user_id="usr_ghost", username="ghost", role="user", token_version=1)

T0 = datetime(2026, 10, 26, 8, 0, tzinfo=UTC)


def _seed(*, reconcile=None):
    clock = FakeClock(T0)
    resources = InMemoryResources()
    resources.libraries = {
        "pub": Library(id="pub", name="公共库", kind="public"),
        "dept_eng": Library(
            id="dept_eng", name="技术部", kind="department", dept_id="dept_eng"
        ),
        "dept_art": Library(
            id="dept_art", name="美术部", kind="department", dept_id="dept_art"
        ),
        "proj_x": Library(
            id="proj_x", name="跨部门项目", kind="project", dept_id="dept_eng"
        ),
        "unassigned": Library(id="unassigned", name="未分配", kind="system"),
    }
    resources.memberships = {
        "usr_alice": (
            Membership(
                user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
                granted_by="usr_admin",
            ),
        ),
        "usr_carol": (
            Membership(
                user_id="usr_carol", dept_id="dept_art", dept_role="dept_admin",
                granted_by="usr_admin",
            ),
        ),
        "usr_bob": (
            Membership(
                user_id="usr_bob", dept_id="proj_x", dept_role="project_lead",
                granted_by="usr_alice",
            ),
        ),
        "usr_frank": (
            Membership(
                user_id="usr_frank", dept_id="dept_eng", dept_role="editor",
                granted_by="usr_admin",
            ),
        ),
        "usr_dave": (
            Membership(
                user_id="usr_dave", dept_id="proj_x", dept_role="editor",
                granted_by="usr_bob",
            ),
        ),
    }
    documents = MemoryDocuments()
    # The authorization catalog reads DocumentAuthz rows, a separate
    # object from the service's document store; production keeps them
    # in sync via the library-backed catalog, so tests that judge
    # authorize_document mirror the library rewrite by hand.
    resources.documents = {}
    for doc_id, library_id, folder_id in (
        ("doc_eng", "dept_eng", "fld_eng"),
        ("doc_px", "proj_x", None),
        ("doc_pub", "pub", None),
        ("doc_art", "dept_art", None),
        ("doc_un", "unassigned", None),
    ):
        documents.save(
            DocumentRecord(
                id=doc_id, title=doc_id, space="shared",
                created_by="usr_frank", library_id=library_id,
                folder_id=folder_id,
            )
        )
        resources.documents[doc_id] = DocumentAuthz(
            id=doc_id, deleted=False, shared_visible=False,
            export_allowed=False, library_id=library_id,
            folder_id=folder_id,
        )
    resources.exceptions = {
        "exc_1": DocumentException(
            id="exc_1", document_id="doc_eng",
            target_user_id="usr_ghost", granted_by="usr_admin",
        ),
    }
    # The restricted source folder's reader: without a folder
    # membership the folder channel would refuse even a department
    # member, which is folder semantics, not move semantics.
    resources.folder_memberships = {
        "usr_frank": (
            FolderMembership(
                folder_id="fld_eng", user_id="usr_frank",
                folder_role="reader", granted_by="usr_alice",
            ),
        ),
    }
    audits = AuditService(AppendOnlyAuditStore(), clock)
    access = AccessControl(resources, clock=clock)
    approvals = ApprovalService(
        store=resources,
        documents=documents,
        versions=MemoryVersions(),
        objects=MemoryObjects(),
        access=access,
        audits=audits,
        clock=clock,
    )
    service = MoveService(
        store=resources,
        documents=documents,
        access=access,
        audits=audits,
        clock=clock,
        approvals=approvals,
        reconcile=reconcile,
    )
    return service, resources, documents, access, audits


def _actions(audits) -> list[dict]:
    return [event.to_info() for event in audits.events()]


def _of(actions, action: str) -> list[dict]:
    return [event for event in actions if event["action"] == action]


def _code(excinfo) -> str:
    return excinfo.value.code


def _mirror(resources, documents, doc_id: str) -> None:
    """Mirror a service-side library rewrite into the authz catalog."""
    row = documents.get(doc_id)
    resources.documents[doc_id] = DocumentAuthz(
        id=doc_id, deleted=False, shared_visible=False,
        export_allowed=False, library_id=row.library_id,
        folder_id=row.folder_id,
    )


def test_FR_RBAC_004_p1_3_move_propose_matrices() -> None:
    service, _, documents, _, audits = _seed()
    # Department admin proposes their own department's document out
    # to the public library (a department admin cannot target
    # another department's library: S3's rule reads it as not_found).
    proposed = service.propose(ENG_ADMIN, "doc_eng", "pub", "req_p1")
    assert proposed.source_library_id == "dept_eng"
    assert proposed.target_library_id == "pub"
    assert proposed.proposer == "usr_alice"
    assert proposed.status == "pending"
    assert proposed.reconcile_status == "pending"
    events = _of(_actions(audits), "doc.move.proposed")
    assert len(events) == 1
    assert events[0]["metadata"]["source_library_id"] == "dept_eng"
    assert events[0]["metadata"]["target_library_id"] == "pub"
    assert events[0]["metadata"]["proposer"] == "usr_alice"
    assert events[0]["metadata"]["dept_id"] == "pub"
    assert events[0]["metadata"]["project_id"] is None
    # Second proposal for the same document is refused, not duplicated.
    with pytest.raises(DocumentError) as excinfo:
        service.propose(ENG_ADMIN, "doc_eng", "pub", "req_p2")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    assert service.pending_request_for("doc_eng").id == proposed.id
    # After withdrawal the document can be proposed again.
    service.withdraw(ENG_ADMIN, proposed.id, "req_w1")
    reproposed = service.propose(ENG_ADMIN, "doc_eng", "pub", "req_p3")
    assert reproposed.status == "pending"
    assert reproposed.id != proposed.id
    assert documents.get("doc_eng").library_id == "dept_eng"
    # A department-target move event carries the target department.
    dept_move = service.propose(ADMIN, "doc_art", "dept_eng", "req_p4")
    service.approve(ENG_ADMIN, dept_move.id, "req_a1")
    move_events = _of(_actions(audits), "authz.library.move")
    assert move_events[0]["metadata"]["dept_id"] == "dept_eng"
    assert move_events[0]["metadata"]["approver"] == "usr_alice"


def test_FR_RBAC_004_p1_3_move_propose_scope_matrix() -> None:
    service, _, _, _, _ = _seed()
    # Project lead proposes their own project's document out.
    assert service.propose(LEAD, "doc_px", "pub", "req_px").status == "pending"
    # Super admin proposes any document out.
    assert service.propose(ADMIN, "doc_art", "pub", "req_art").status == "pending"
    # A visible-but-unpowered editor hears forbidden.
    with pytest.raises(AuthError) as excinfo:
        service.propose(EDITOR, "doc_eng", "pub", "req_no")
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    # An outsider sees nothing.
    with pytest.raises(AuthError) as excinfo:
        service.propose(OUTSIDER, "doc_eng", "pub", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # A department admin of another department sees nothing there.
    with pytest.raises(AuthError) as excinfo:
        service.propose(ENG_ADMIN, "doc_art", "pub", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # A project lead holds no propose power over department documents.
    with pytest.raises(AuthError) as excinfo:
        service.propose(LEAD, "doc_eng", "pub", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # An owning-department admin holds no propose power over a
    # project library's documents (leads propose those out).
    with pytest.raises(AuthError) as excinfo:
        service.propose(ENG_ADMIN, "doc_px", "pub", "req_no")
    assert _code(excinfo) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_p1_3_move_propose_target_matrix() -> None:
    service, _, _, _, _ = _seed()
    # Unassigned documents have no move: they travel the claim path.
    with pytest.raises(AuthError) as excinfo:
        service.propose(ENG_ADMIN, "doc_un", "pub", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # Missing and deleted documents read as not_found.
    with pytest.raises(AuthError) as excinfo:
        service.propose(ENG_ADMIN, "doc_nope", "pub", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # Invisible targets read as not_found (no existence leak): a
    # department admin cannot target another department's library.
    with pytest.raises(AuthError) as excinfo:
        service.propose(ENG_ADMIN, "doc_eng", "dept_art", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # System targets and unknown targets are not targets at all.
    with pytest.raises(AuthError) as excinfo:
        service.propose(ENG_ADMIN, "doc_eng", "unassigned", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.propose(ENG_ADMIN, "doc_eng", "dept_nope", "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # Moving to the library the document already sits in is refused.
    # (A super admin passes target validation, so the same-library
    # refusal itself is what fires.)
    with pytest.raises(DocumentError) as excinfo:
        service.propose(ADMIN, "doc_eng", "dept_eng", "req_no")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"


def test_FR_RBAC_004_p1_3_move_approve_flow() -> None:
    dispatched: list = []

    def _reconcile(document_id, library_id, request_id, actor_id):
        # Snapshot the library at dispatch time: approve() must have
        # already rewritten it to the target, never the old library.
        dispatched.append((document_id, library_id, actor_id))

    service, resources, documents, _, audits = _seed(reconcile=_reconcile)
    proposed = service.propose(ADMIN, "doc_eng", "dept_art", "req_p1")
    decided = service.approve(ART_ADMIN, proposed.id, "req_a1")
    assert decided.status == "approved"
    assert decided.decided_by == "usr_carol"
    assert decided.reconcile_status == "pending"
    assert decided.reconcile_attempts == 0
    # O7: the restricted source folder does not follow; the document
    # lands in the target library's default folder.
    row = documents.get("doc_eng")
    assert row.library_id == "dept_art"
    assert row.folder_id is None
    assert dispatched == [("doc_eng", "dept_art", "usr_carol")]
    events = _of(_actions(audits), "authz.library.move")
    assert len(events) == 1
    assert events[0]["metadata"]["source_library_id"] == "dept_eng"
    assert events[0]["metadata"]["target_library_id"] == "dept_art"
    assert events[0]["metadata"]["proposer"] == "usr_admin"
    assert events[0]["metadata"]["approver"] == "usr_carol"
    assert events[0]["metadata"]["dept_id"] == "dept_art"
    # A non-admin target approver records no delegation marker.
    assert _of(_actions(audits), "authz.approval.delegated") == []


def test_FR_RBAC_004_p1_3_move_approve_delegated_and_public() -> None:
    service, _, _, _, audits = _seed()
    # A super admin deciding a department queue acts by delegation.
    proposed = service.propose(ADMIN, "doc_eng", "dept_art", "req_p1")
    service.approve(ADMIN, proposed.id, "req_a1")
    assert len(_of(_actions(audits), "authz.library.move")) == 1
    delegated = _of(_actions(audits), "authz.approval.delegated")
    assert len(delegated) == 1
    assert delegated[0]["actor"] == "usr_admin"
    # On the public queue the same super admin action is ordinary.
    proposed_pub = service.propose(ADMIN, "doc_art", "pub", "req_p2")
    service.approve(ADMIN, proposed_pub.id, "req_a2")
    assert len(_of(_actions(audits), "authz.library.move")) == 2
    assert len(_of(_actions(audits), "authz.approval.delegated")) == 1


def test_FR_RBAC_004_p1_3_move_approve_decider_matrix() -> None:
    service, _, _, _, _ = _seed()
    proposed = service.propose(ADMIN, "doc_eng", "dept_art", "req_p1")
    # The source admin takes no part in the decision (Q3).
    with pytest.raises(AuthError) as excinfo:
        service.approve(ENG_ADMIN, proposed.id, "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # A non-proposer outsider sees nothing.
    with pytest.raises(AuthError) as excinfo:
        service.approve(OUTSIDER, proposed.id, "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # Proposer-decides-forbidden, decided-state scope-first: a
    # proposer-owned request decided by the target admin still
    # answers forbidden to the proposer, not illegal state.
    service2, _, _, _, _ = _seed()
    owned = service2.propose(ENG_ADMIN, "doc_eng", "pub", "req_p1")
    # Public target: only a super admin decides; the proposer hears
    # forbidden even after the decision lands.
    service2.approve(ADMIN, owned.id, "req_a1")
    with pytest.raises(AuthError) as excinfo:
        service2.approve(ENG_ADMIN, owned.id, "req_no")
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    # The target approver on a decided request hears illegal state
    # (scope passes, state fails) — scope-first changes nothing here.
    with pytest.raises(DocumentError) as excinfo:
        service2.approve(ADMIN, owned.id, "req_no")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"


def test_FR_RBAC_004_p1_3_move_approve_drift_is_illegal() -> None:
    service, _, documents, _, _ = _seed()
    proposed = service.propose(ADMIN, "doc_eng", "dept_art", "req_p1")
    # The document drifted away from the proposed source since
    # proposal; approving would move the wrong scope.
    row = documents.get("doc_eng")
    row.library_id = "pub"
    documents.save(row)
    with pytest.raises(DocumentError) as excinfo:
        service.approve(ART_ADMIN, proposed.id, "req_no")
    assert _code(excinfo) == "RESOURCE_FORBIDDEN"
    assert service.pending_request_for("doc_eng").id == proposed.id


def test_FR_RBAC_004_p1_3_move_reconcile_states() -> None:
    # No reconcile callable (no llama backend): nothing to reconcile,
    # so approval records ok directly.
    service, _, documents, _, _ = _seed(reconcile=None)
    proposed = service.propose(ADMIN, "doc_eng", "dept_art", "req_p1")
    decided = service.approve(ART_ADMIN, proposed.id, "req_a1")
    assert decided.reconcile_status == "ok"
    assert documents.get("doc_eng").library_id == "dept_art"

    # A dispatch failure never rolls the move back: the request
    # marks failed with attempts=1 and the loss is audited for the
    # target department's view.
    def _boom(document_id, library_id, request_id, actor_id):
        raise RuntimeError("broker down")

    service2, _, documents2, _, audits2 = _seed(reconcile=_boom)
    proposed2 = service2.propose(ADMIN, "doc_eng", "dept_art", "req_p1")
    failed = service2.approve(ART_ADMIN, proposed2.id, "req_a1")
    assert failed.status == "approved"
    assert failed.reconcile_status == "failed"
    assert failed.reconcile_attempts == 1
    assert documents2.get("doc_eng").library_id == "dept_art"
    sync_failed = _of(_actions(audits2), "authz.library.sync_failed")
    assert len(sync_failed) == 1
    assert sync_failed[0]["metadata"]["from_library"] == "dept_eng"
    assert sync_failed[0]["metadata"]["to_library"] == "dept_art"
    assert sync_failed[0]["metadata"]["dept_id"] == "dept_art"
    assert sync_failed[0]["metadata"]["attempts"] == 1


def test_FR_RBAC_004_p1_3_move_reject_and_withdraw() -> None:
    dispatched: list = []
    service, _, documents, _, audits = _seed(
        reconcile=lambda *args: dispatched.append(args)
    )
    proposed = service.propose(ADMIN, "doc_eng", "dept_art", "req_p1")
    rejected = service.reject(ART_ADMIN, proposed.id, "req_r1", reason="敏感")
    assert rejected.status == "rejected"
    assert rejected.reason == "敏感"
    row = documents.get("doc_eng")
    assert row.library_id == "dept_eng"
    assert row.folder_id == "fld_eng"
    assert dispatched == []
    events = _of(_actions(audits), "authz.approval.rejected")
    assert len(events) == 1
    assert events[0]["metadata"]["approver"] == "usr_carol"
    # A rejected document can be proposed again as a new request.
    reproposed = service.propose(ADMIN, "doc_eng", "dept_art", "req_p2")
    assert reproposed.id != proposed.id
    # Withdraw belongs to the proposer only; the document stays put.
    withdrawn = service.withdraw(ADMIN, reproposed.id, "req_w1")
    assert withdrawn.status == "withdrawn"
    assert documents.get("doc_eng").library_id == "dept_eng"
    assert len(_of(_actions(audits), "doc.move.cancelled")) == 1
    # A queue-visible non-proposer hears forbidden on withdraw.
    proposed2 = service.propose(ADMIN, "doc_eng", "dept_art", "req_p3")
    with pytest.raises(AuthError) as excinfo:
        service.withdraw(ART_ADMIN, proposed2.id, "req_no")
    assert _code(excinfo) == "AUTH_FORBIDDEN"
    with pytest.raises(AuthError) as excinfo:
        service.withdraw(OUTSIDER, proposed2.id, "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_move_queue_scope() -> None:
    service, _, _, _, _ = _seed()
    by_admin = service.propose(ADMIN, "doc_eng", "dept_art", "req_p1")
    by_lead = service.propose(LEAD, "doc_px", "pub", "req_p2")
    # Target approver, super admin, and proposer see their queues.
    assert [item.id for item in service.list_pending(ART_ADMIN)] == [by_admin.id]
    assert {item.id for item in service.list_pending(ADMIN)} == {
        by_admin.id, by_lead.id,
    }
    assert [item.id for item in service.list_pending(LEAD)] == [by_lead.id]
    # The source admin (non-proposer) sees nothing of the outgoing
    # move; neither does an unrelated editor or an outsider.
    assert service.list_pending(ENG_ADMIN) == ()
    assert service.list_pending(OUTSIDER) == ()
    # History reads follow the same scope: decided requests stay
    # reachable to proposer and approvers, not to outsiders.
    service.approve(ART_ADMIN, by_admin.id, "req_a1")
    assert service.get_request(ADMIN, by_admin.id, "req_g1").status == "approved"
    assert service.get_request(ART_ADMIN, by_admin.id, "req_g2").status == "approved"
    with pytest.raises(AuthError) as excinfo:
        service.get_request(OUTSIDER, by_admin.id, "req_no")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_move_visibility_and_exceptions_follow() -> None:
    service, resources, documents, access, _ = _seed()
    # Before approval the source member authorizes; the exception
    # grantee authorizes through the exception channel.
    access.authorize_document(EDITOR, "doc_eng", "req_v1")
    access.authorize_document(OUTSIDER, "doc_eng", "req_v2")
    with pytest.raises(AuthError):
        access.authorize_document(PX_EDITOR, "doc_eng", "req_v3")
    proposed = service.propose(ADMIN, "doc_eng", "dept_art", "req_p1")
    # While pending, the source library still serves the document:
    # proposing changes nothing but the request row.
    access.authorize_document(EDITOR, "doc_eng", "req_v4")
    service.approve(ART_ADMIN, proposed.id, "req_a1")
    _mirror(resources, documents, "doc_eng")
    # After approval the source member loses it, the target member
    # gains it, and the exception grant follows the document.
    with pytest.raises(AuthError):
        access.authorize_document(EDITOR, "doc_eng", "req_v5")
    access.authorize_document(ART_ADMIN, "doc_eng", "req_v6")
    assert "doc_eng" in access.exception_document_ids(OUTSIDER)
    access.authorize_document(OUTSIDER, "doc_eng", "req_v7")
    with pytest.raises(AuthError):
        access.authorize_document(PX_EDITOR, "doc_eng", "req_v8")


def test_FR_RBAC_004_p1_3_move_rollback_reapprove() -> None:
    service, _, documents, _, audits = _seed()
    first = service.propose(ADMIN, "doc_eng", "dept_art", "req_p1")
    service.approve(ART_ADMIN, first.id, "req_a1")
    assert documents.get("doc_eng").library_id == "dept_art"
    # Rollback is a symmetric re-approved move: reason names the
    # rollback, rollback_of links the original execution in audit.
    back = service.propose(
        ADMIN, "doc_eng", "dept_eng", "req_p2",
        reason="回滚", rollback_of=first.id,
    )
    service.approve(ENG_ADMIN, back.id, "req_a2")
    assert documents.get("doc_eng").library_id == "dept_eng"
    proposed_events = _of(_actions(audits), "doc.move.proposed")
    assert proposed_events[1]["metadata"]["rollback_of"] == first.id
    assert back.reason == "回滚"
