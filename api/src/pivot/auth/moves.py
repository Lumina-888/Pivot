"""Cross-library move approvals (ADR-019 D3, D6; P1-3 S4).

Owns the move-request path: propose, approve, reject, withdraw, queue
listing, and single-request history reads. It does NOT own publish
requests (S2/S3) or claim interlock (S5).

Rules, fixed by ADR-019 and the Owner-settled Q3/O2/O7:

- Proposer by source library scope: department admins propose their
  own department's documents out, project leads propose their own
  project's documents out, super admins propose any document out.
  Ordinary members and folder-full members cannot propose a move:
  a move is a library-level management action, not a folder action.
- Approver is the TARGET library's admin, single-sided (Q3): the
  source admin takes no part in the decision. The risk sits with the
  gaining side, whose members newly see the document; the source side
  losing a document is not a disclosure. Decision power reuses S2's
  rule (department -> that department's admins, public -> super
  admins only, project -> that project's leads) via
  ApprovalService.is_approver, never a second standard.
- Scope is checked before state on every decision path (the S2 fix):
  a proposer attempt is forbidden, anyone else outside the queue
  sees not_found, whatever the request's state.
- One pending move request per document: the service pre-check maps
  a second proposal to a clean refusal; the S1 partial unique index
  (PG) / pending check (memory) is the backstop for the race.
- Approve order is load-bearing and must not be rearranged: close
  the request, rewrite the document's library to the target, clear
  folder_id (O7: the document lands in the target library's default
  folder; a restricted source folder never follows), then dispatch
  reconcile OUTSIDE the atomic block. Before reconcile completes,
  retrieval may lag but never over-serves: the authorize hook judges
  live library facts, so the source collection's stale nodes stay
  invisible and the target's members simply cannot find the document
  yet (the P1-2 D3 "lag ok, over-visibility never" semantics).
- Exceptions follow the document (ADR-019 D3): a move never touches
  document_exceptions, so a grant stays valid across the move.
- Events (ADR-019 D6, no invented names): doc.move.proposed on
  propose, authz.library.move on approve, authz.approval.rejected on
  reject, doc.move.cancelled on withdraw. A super admin acting on a
  department or project queue additionally records
  authz.approval.delegated (O2), exactly like publish decisions.
  Rollback is a symmetric re-approved move (ADR-019 D3): propose
  back with a reason naming the rollback and rollback_of carrying
  the original request id in the proposed event's metadata; no
  special rollback path exists. A move request withdrawn by its
  proposer closes as "withdrawn" (the "cancelled" status is reserved
  for S5's delete-cancel).

Atomicity mirrors ApprovalService (ADR-017 D4): on the PostgreSQL
path the decision, the library rewrite, the folder clear, and the
audit writes share one session scope; on the memory path the same
writes are compensated by restoring the previous rows. Reconcile
dispatch is deliberately OUTSIDE the scope, mirroring ingest: a
dispatch failure never rolls back a move that already stands. It
marks the request reconcile_status=failed with attempts=1 and writes
authz.library.sync_failed (target department view), so the loss
stays visible to admins. Successful dispatch leaves
reconcile_status=pending: completion is asynchronous in broker mode
and the existing worker task (pivot.reconcile_claimed_document) has
no move-request handle, so the pending->ok and exhaustion->failed
transitions are NOT implemented here (S4 residual, recorded in
M01.md); the failed-dispatch path above is fully implemented and
tested. When no reconcile callable is wired (no llama backend, so
there is nothing to reconcile), approval records reconcile_status=ok
directly.
"""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from typing import Callable

from pivot.audit.service import AuditService
from pivot.auth.approvals import ApprovalService
from pivot.auth.errors import forbidden, not_found
from pivot.auth.ports import (
    Clock,
    DepartmentAdminStore,
    Library,
    MoveRequest,
    Principal,
)
from pivot.documents.errors import illegal_state
from pivot.documents.ports import DocumentRecord, DocumentStore
from pivot.security.rbac import AccessControl
from pivot.shared.ids import new_id

logger = logging.getLogger("pivot.moves")


class MoveService:
    """Decide cross-library move requests (ADR-019 D3)."""

    def __init__(
        self,
        *,
        store: DepartmentAdminStore,
        documents: DocumentStore,
        access: AccessControl,
        audits: AuditService,
        clock: Clock,
        approvals: ApprovalService,
        transaction: Callable[[], AbstractContextManager[None]] | None = None,
        reconcile: (
            Callable[[str, str, str, str], object] | None
        ) = None,
    ) -> None:
        """Build the service.

        ``approvals`` supplies the target validation rule (S3) and the
        approver rule (S2) so moves never grow a second standard.
        ``reconcile`` is the claim-sync submitter shape
        (document_id, library_id, request_id, actor_id); None means
        there is no llama backend to reconcile and approval records
        reconcile_status=ok directly.
        """
        self._store = store
        self._documents = documents
        self._access = access
        self._audits = audits
        self._clock = clock
        self._approvals = approvals
        self._transaction = transaction
        self._reconcile = reconcile

    @contextmanager
    def _atomic(self):
        """Scope one decision and its audit writes, if PG-backed."""
        if self._transaction is not None:
            with self._transaction():
                yield
        else:
            yield

    def _record_all_or_rollback(self, *, rollback, records) -> None:
        """Record audit events, compensating the mutation on failure.

        Same discipline as ApprovalService: on the PostgreSQL path
        the enclosing scope rolls everything back on a failed
        critical audit write; on the memory path a failure restores
        the previous rows (events already appended to the append-only
        audit cannot be unwritten, same accepted limitation).
        """
        if self._transaction is not None:
            for record_kwargs in records:
                self._audits.record(**record_kwargs)
            return
        try:
            for record_kwargs in records:
                self._audits.record(**record_kwargs)
        except Exception:
            try:
                rollback()
            except Exception:
                logger.exception("move audit failure rollback failed")
            raise

    def _deny(
        self,
        principal: Principal,
        request_id: str,
        *,
        dept_id: str | None,
        target: str,
        error,
    ):
        """Audit an overreach attempt best-effort (ADR-019 D6), then
        raise the denial."""
        try:
            self._audits.record(
                actor=principal.user_id,
                action="authz.admin_denied",
                target=target,
                result="denied",
                request_id=request_id,
                metadata={"dept_id": dept_id} if dept_id is not None else {},
            )
        except Exception:
            logger.exception("denied move audit write failed; denial stands")
        raise error

    # -- scope helpers ---------------------------------------------------

    def _is_move_proposer(self, principal: Principal, source: Library) -> bool:
        """Propose power by source library scope (ADR-019 D3).

        Super admins propose any document out. Department documents
        are proposed by that department's admins, project documents
        by that project's leads. Public documents have no department
        or lead owner, so only super admins propose them out.
        """
        if principal.role == "admin":
            return True
        if source.kind == "department":
            return self._access.is_department_admin(
                principal, source.dept_id or source.id
            )
        if source.kind == "project":
            return self._access.is_project_lead(principal, source.id)
        return False

    def _sees_move_queue(self, principal: Principal, target: Library) -> bool:
        """Queue visibility, wider than decision power (S2 rule).

        A department admin sees pending moves targeting project
        libraries their department owns, in addition to their own
        department targets; they still cannot decide the project ones.
        """
        if self._approvals.is_approver(principal, target):
            return True
        return (
            target.kind == "project"
            and target.dept_id is not None
            and target.dept_id
            in self._access.admin_departments(principal)
        )

    def _is_delegated(self, principal: Principal, target: Library) -> bool:
        """O2, same rule as publish decisions: a super admin acting
        on a department or project queue acts by delegation; on the
        public queue the same action is ordinary."""
        return principal.role == "admin" and target.kind != "public"

    def _meta(
        self,
        request: MoveRequest,
        source: Library,
        target: Library,
        *,
        approver: str | None = None,
    ) -> dict[str, object]:
        """Audit metadata for move events (ADR-019 D6, S5 closeout).

        dept_id is the TARGET library's owning department, so the
        target department's audit view picks the event up (public
        targets use "pub" per the S2 convention, pending S5
        unification). project_id keys the lead audit view whenever a
        project is involved on either side: the target project if the
        target is a project, else the source project. Cross-view
        completeness for moves touching two departments is an S5
        audit-closeout item, not a second dept_id field here.
        """
        if target.kind == "department":
            dept_id: str | None = target.dept_id or target.id
        elif target.kind == "project":
            dept_id = target.dept_id
        else:
            dept_id = "pub"
        if target.kind == "project":
            project_id: str | None = target.id
        elif source.kind == "project":
            project_id = source.id
        else:
            project_id = None
        metadata: dict[str, object] = {
            "document_id": request.document_id,
            "source_library_id": request.source_library_id,
            "target_library_id": request.target_library_id,
            "proposer": request.proposer,
            "dept_id": dept_id,
            "project_id": project_id,
        }
        if approver is not None:
            metadata["approver"] = approver
        return metadata

    def _require_request(
        self, request_id: str, http_request_id: str
    ) -> MoveRequest:
        request = self._store.get_move_request(request_id)
        if request is None:
            raise not_found(http_request_id)
        return request

    def _require_library(
        self, library_id: str, http_request_id: str
    ) -> Library:
        library = self._store.get_library(library_id)
        if library is None:
            raise not_found(http_request_id)
        return library

    def _dept_id(
        self, request: MoveRequest, source: Library, target: Library
    ) -> str | None:
        """Owning-department value for denial audits (same rule as
        the decision metadata, without building the full dict)."""
        meta = self._meta(request, source, target)
        value = meta.get("dept_id")
        return value if isinstance(value, str) else None

    def _require_move_proposer(
        self,
        principal: Principal,
        request_document_id: str,
        source: Library,
        http_request_id: str,
    ) -> None:
        """Propose power: owners propose; a principal who can see the
        source library but holds no propose power hears forbidden;
        anyone else hears not_found (no leak)."""
        if self._is_move_proposer(principal, source):
            return
        if source.id in self._access.visible_libraries(principal):
            self._deny(
                principal,
                http_request_id,
                dept_id=source.dept_id if source.kind != "public" else None,
                target=request_document_id,
                error=forbidden(http_request_id),
            )
        self._deny(
            principal,
            http_request_id,
            dept_id=source.dept_id if source.kind != "public" else None,
            target=request_document_id,
            error=not_found(http_request_id),
        )

    def _require_decider(
        self,
        principal: Principal,
        request: MoveRequest,
        source: Library,
        target: Library,
        http_request_id: str,
    ) -> None:
        """Approve/reject power: target approvers decide; the proposer
        knows the request exists so a proposer attempt is forbidden,
        while anyone else outside the queue sees not_found (no leak).
        The source admin is deliberately not a decider (Q3)."""
        if self._approvals.is_approver(principal, target):
            return
        if principal.user_id == request.proposer:
            self._deny(
                principal,
                http_request_id,
                dept_id=self._dept_id(request, source, target),
                target=request.id,
                error=forbidden(http_request_id),
            )
        self._deny(
            principal,
            http_request_id,
            dept_id=self._dept_id(request, source, target),
            target=request.id,
            error=not_found(http_request_id),
        )

    def _require_proposer(
        self,
        principal: Principal,
        request: MoveRequest,
        target: Library,
        http_request_id: str,
    ) -> None:
        """Withdraw power: the proposer only. A queue-visible
        non-proposer gets forbidden (they can see the request);
        anyone else gets not_found."""
        if principal.user_id == request.proposer:
            return
        if principal.role == "admin" or self._sees_move_queue(
            principal, target
        ):
            source = self._require_library(
                request.source_library_id, http_request_id
            )
            self._deny(
                principal,
                http_request_id,
                dept_id=self._dept_id(request, source, target),
                target=request.id,
                error=forbidden(http_request_id),
            )
        source = self._require_library(request.source_library_id, http_request_id)
        self._deny(
            principal,
            http_request_id,
            dept_id=self._dept_id(request, source, target),
            target=request.id,
            error=not_found(http_request_id),
        )

    def _require_pending(
        self, request: MoveRequest, http_request_id: str
    ) -> None:
        if request.status != "pending":
            raise illegal_state(
                http_request_id, f"request is {request.status}, not pending"
            )

    def _require_document(
        self, document_id: str, http_request_id: str
    ) -> DocumentRecord:
        document = self._documents.get(document_id)
        if document is None or document.deleted_at is not None:
            raise not_found(http_request_id)
        return document

    def _decision_records(
        self,
        *,
        principal: Principal,
        request: MoveRequest,
        source: Library,
        target: Library,
        action: str,
        http_request_id: str,
    ) -> list[dict]:
        """Decision audit records: the decision event, plus the
        delegation marker when a super admin acts on a department or
        project queue (O2). The actor on every record is the acting
        administrator, never the proposer."""
        records = [
            {
                "actor": principal.user_id,
                "action": action,
                "target": request.id,
                "result": "ok",
                "request_id": http_request_id,
                "metadata": self._meta(
                    request, source, target, approver=principal.user_id
                ),
            }
        ]
        if self._is_delegated(principal, target):
            records.append(
                {
                    "actor": principal.user_id,
                    "action": "authz.approval.delegated",
                    "target": request.id,
                    "result": "ok",
                    "request_id": http_request_id,
                    "metadata": self._meta(
                        request, source, target, approver=principal.user_id
                    ),
                }
            )
        return records

    def pending_request_for(self, document_id: str) -> MoveRequest | None:
        """The document's pending move request, if any."""
        for request in self._store.list_move_requests(document_id):
            if request.status == "pending":
                return request
        return None

    def document_title(self, document_id: str) -> str | None:
        """Todo-queue display title (P1-3 S5): the document's title,
        or None when the document is gone. The queue views carry the
        title so a todo item is actionable without a second lookup."""
        document = self._documents.get(document_id)
        return None if document is None else document.title

    def cancel_pending_for_document(
        self, document_id: str, actor_id: str, http_request_id: str
    ) -> MoveRequest | None:
        """Close the document's pending move request on delete
        (ADR-019 D4, P1-3 S5, decided O4): the request closes as
        cancelled and the cancellation is audited as
        doc.move.cancelled, the same event the proposer withdraw path
        already uses. Returns the cancelled request, or None when
        there is no pending request; decided requests are untouched.
        Called by the delete route after the tombstone lands, so a
        cancellation failure leaves the tombstone standing and the
        request inert (decisions on a deleted document fail
        not_found) rather than rolling the delete back.
        """
        request = self.pending_request_for(document_id)
        if request is None:
            return None
        # The target or source library may itself be gone; a missing
        # library must not block closing the dead request, so fall
        # back to stub libraries for metadata instead of not_found.
        target = self._store.get_library(request.target_library_id)
        if target is None:
            target = Library(
                id=request.target_library_id, name="", kind="unknown"
            )
        source = self._store.get_library(request.source_library_id)
        if source is None:
            source = Library(
                id=request.source_library_id, name="", kind="unknown"
            )
        now = self._clock.now()
        cancelled = replace(
            request, status="cancelled", decided_at=now, decided_by=actor_id
        )

        def rollback() -> None:
            self._store.set_move_request(request)

        with self._atomic():
            self._store.set_move_request(cancelled)
            self._record_all_or_rollback(
                rollback=rollback,
                records=[
                    {
                        "actor": actor_id,
                        "action": "doc.move.cancelled",
                        "target": request.id,
                        "result": "ok",
                        "request_id": http_request_id,
                        "metadata": self._meta(cancelled, source, target),
                    }
                ],
            )
        return cancelled

    # -- propose -----------------------------------------------------------

    def propose(
        self,
        principal: Principal,
        document_id: str,
        target_library_id: str,
        http_request_id: str,
        reason: str = "",
        rollback_of: str | None = None,
    ) -> MoveRequest:
        """Propose moving a published document (ADR-019 D3).

        Order: document exists, source exists, proposer scope,
        published (not unassigned), target validation (S3 rule,
        invisible reads as not_found), same-library refusal, then the
        one-pending pre-check. The document stays fully visible in
        the source library while the request is pending: proposing
        changes nothing but the request row.
        """
        document = self._require_document(document_id, http_request_id)
        source = self._require_library(document.library_id, http_request_id)
        self._require_move_proposer(
            principal, document_id, source, http_request_id
        )
        if document.library_id == "unassigned":
            # Unassigned documents have no move: they travel the
            # claim path, never the move queue.
            raise not_found(http_request_id)
        target = self._approvals.validate_upload_target(
            principal, target_library_id, http_request_id
        )
        if target.id == source.id:
            raise illegal_state(
                http_request_id, "document is already in the target library"
            )
        if self.pending_request_for(document_id) is not None:
            raise illegal_state(
                http_request_id, "document already has a pending move request"
            )
        request = MoveRequest(
            id=new_id("move"),
            document_id=document_id,
            source_library_id=source.id,
            target_library_id=target.id,
            proposer=principal.user_id,
            status="pending",
            reason=reason,
            created_at=self._clock.now(),
        )
        metadata = self._meta(request, source, target)
        if rollback_of is not None:
            # Opaque audit link to the original execution: rollback
            # is a symmetric re-approved move, not a special path.
            metadata["rollback_of"] = rollback_of
        with self._atomic():
            self._store.add_move_request(request)
            self._audits.record(
                actor=principal.user_id,
                action="doc.move.proposed",
                target=request.id,
                result="ok",
                request_id=http_request_id,
                metadata=metadata,
            )
        return request

    # -- decisions ---------------------------------------------------------

    def approve(
        self, principal: Principal, request_id: str, http_request_id: str
    ) -> MoveRequest:
        """Approve a pending move (ADR-019 D3).

        Order is load-bearing and must not be rearranged: close the
        request, rewrite the document's library to the target, clear
        folder_id (O7: the target library's default folder), and only
        then dispatch reconcile, so the worker rebuilds the target
        collection's nodes for a document that already belongs to
        the target. Exceptions are untouched by the move and stay
        valid. A reconcile dispatch failure never rolls the move
        back: it marks reconcile_status=failed with attempts=1 and
        writes authz.library.sync_failed for the target view.
        """
        request = self._require_request(request_id, http_request_id)
        target = self._require_library(
            request.target_library_id, http_request_id
        )
        source = self._require_library(
            request.source_library_id, http_request_id
        )
        self._require_decider(
            principal, request, source, target, http_request_id
        )
        self._require_pending(request, http_request_id)
        document = self._require_document(
            request.document_id, http_request_id
        )
        if document.library_id != request.source_library_id:
            # The document drifted away from the proposed source
            # since proposal; approving would move the wrong scope.
            raise illegal_state(
                http_request_id, "document is no longer in the source library"
            )
        now = self._clock.now()
        decided = replace(
            request,
            status="approved",
            decided_at=now,
            decided_by=principal.user_id,
            reconcile_status="ok" if self._reconcile is None else "pending",
            reconcile_attempts=0,
        )
        old_library_id = document.library_id
        old_folder_id = document.folder_id

        def rollback() -> None:
            self._store.set_move_request(request)
            document.library_id = old_library_id
            document.folder_id = old_folder_id
            self._documents.save(document)

        with self._atomic():
            self._store.set_move_request(decided)
            document.library_id = target.id
            document.folder_id = None
            self._documents.save(document)
            self._record_all_or_rollback(
                rollback=rollback,
                records=self._decision_records(
                    principal=principal,
                    request=decided,
                    source=source,
                    target=target,
                    action="authz.library.move",
                    http_request_id=http_request_id,
                ),
            )
        if self._reconcile is None:
            return decided
        try:
            self._reconcile(
                document.id, target.id, request_id, principal.user_id
            )
        except Exception:
            # Dispatch failed: the move stands, but the loss must
            # stay visible. Mark failed and audit it; never raise.
            failed = replace(
                decided, reconcile_status="failed", reconcile_attempts=1
            )
            try:
                self._store.set_move_request(failed)
                self._audits.record(
                    actor=principal.user_id,
                    action="authz.library.sync_failed",
                    target=document.id,
                    result="failed",
                    request_id=http_request_id,
                    metadata={
                        "dept_id": self._meta(
                            failed, source, target
                        )["dept_id"],
                        "from_library": source.id,
                        "to_library": target.id,
                        "attempts": 1,
                        "move_request_id": request.id,
                    },
                )
            except Exception:
                logger.exception(
                    "move reconcile failure record failed for document %s",
                    document.id,
                )
            return failed
        return decided

    def reject(
        self,
        principal: Principal,
        request_id: str,
        http_request_id: str,
        reason: str = "",
    ) -> MoveRequest:
        """Reject a pending move (ADR-019 D3): the document stays in
        the source library with visibility unchanged, the request
        closes with the (optional) reason, and no reconcile is
        dispatched. The proposer may propose again as a new request."""
        request = self._require_request(request_id, http_request_id)
        target = self._require_library(
            request.target_library_id, http_request_id
        )
        source = self._require_library(
            request.source_library_id, http_request_id
        )
        self._require_decider(
            principal, request, source, target, http_request_id
        )
        self._require_pending(request, http_request_id)
        now = self._clock.now()
        decided = replace(
            request,
            status="rejected",
            reason=reason,
            decided_at=now,
            decided_by=principal.user_id,
        )

        def rollback() -> None:
            self._store.set_move_request(request)

        with self._atomic():
            self._store.set_move_request(decided)
            self._record_all_or_rollback(
                rollback=rollback,
                records=self._decision_records(
                    principal=principal,
                    request=decided,
                    source=source,
                    target=target,
                    action="authz.approval.rejected",
                    http_request_id=http_request_id,
                ),
            )
        return decided

    def withdraw(
        self, principal: Principal, request_id: str, http_request_id: str
    ) -> MoveRequest:
        """Withdraw a pending move (ADR-019 D3): proposer only, the
        document stays in the source library, the request closes as
        withdrawn, and the cancellation is audited as
        doc.move.cancelled."""
        request = self._require_request(request_id, http_request_id)
        target = self._require_library(
            request.target_library_id, http_request_id
        )
        self._require_proposer(principal, request, target, http_request_id)
        self._require_pending(request, http_request_id)
        source = self._require_library(
            request.source_library_id, http_request_id
        )
        now = self._clock.now()
        withdrawn = replace(
            request, status="withdrawn", decided_at=now,
            decided_by=principal.user_id,
        )

        def rollback() -> None:
            self._store.set_move_request(request)

        with self._atomic():
            self._store.set_move_request(withdrawn)
            self._record_all_or_rollback(
                rollback=rollback,
                records=[
                    {
                        "actor": principal.user_id,
                        "action": "doc.move.cancelled",
                        "target": request.id,
                        "result": "ok",
                        "request_id": http_request_id,
                        "metadata": self._meta(withdrawn, source, target),
                    }
                ],
            )
        return withdrawn

    # -- queue and history -------------------------------------------------

    def list_pending(self, principal: Principal) -> tuple[MoveRequest, ...]:
        """Pending move requests in the caller's scope (ADR-019 D6).

        Super admins see the global queue; target approvers and
        owning-department admins of project targets see their queues;
        proposers see their own submissions. Decided requests are not
        queue items: proposers and approvers reach them via
        get_request."""
        visible: list[MoveRequest] = []
        for document in self._documents_list():
            for request in self._store.list_move_requests(document.id):
                if request.status != "pending":
                    continue
                target = self._store.get_library(request.target_library_id)
                if target is None:
                    continue
                if (
                    principal.role == "admin"
                    or request.proposer == principal.user_id
                    or self._sees_move_queue(principal, target)
                ):
                    visible.append(request)
        visible.sort(
            key=lambda item: (item.created_at is None, item.created_at, item.id)
        )
        return tuple(visible)

    def _documents_list(self):
        """All documents known to the document store, if it lists
        them; the memory and SQL document stores both do."""
        listing = getattr(self._documents, "list_active", None)
        if listing is None:
            return ()
        return listing()

    def get_request(
        self, principal: Principal, request_id: str, http_request_id: str
    ) -> MoveRequest:
        """One request: super admins, the proposer, and queue-visible
        approvers may see it (including decided ones). Anyone else
        gets not_found, never a leak about the request."""
        request = self._require_request(request_id, http_request_id)
        target = self._require_library(
            request.target_library_id, http_request_id
        )
        if (
            principal.role == "admin"
            or request.proposer == principal.user_id
            or self._sees_move_queue(principal, target)
        ):
            return request
        raise not_found(http_request_id)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "MoveService()"
