"""Publish-approval service (ADR-019 D1, D6; P1-3 S2).

Owns the approval decision path for publish requests: approve, reject,
withdraw, resubmit, queue listing, and the dedicated review read. It
does NOT own request creation (S3's upload-with-target path creates
the request, then reuses approve() for the self-approval fast path) and
it does NOT own move requests (S4).

Scope rules, fixed by ADR-019 and the Owner-settled O2/O3:

- Approver by target library kind: department -> that department's
  admins, public -> super admins only, project -> that project's
  leads. A super admin acting on a department or project queue is a
  delegated action (authz.approval.delegated, O2); on the public queue
  the same super admin action is an ordinary approval.
- Queue visibility is wider than decision power: a department admin
  also sees pending requests targeting project libraries their
  department owns, but cannot decide them (only the lead can).
- Withdraw and resubmit belong to the proposer only.
- Review read is a dedicated path, never preview/download: proposer,
  target approver, or super admin, reading the version's stored bytes
  from the quarantine object (the upload path already writes
  quarantine/{document}/{version}; S2 only reads it, S3 owns the
  write contract). Each read is audited as doc.approval.review.

Atomicity mirrors DepartmentAdminService (ADR-017 D4): on the
PostgreSQL path the decision, the library rewrite, the version
transition, and the audit writes share one session scope, so a failed
critical audit write rolls everything back; on the memory path the
same writes are compensated by restoring the previous rows. Ingest
dispatch is deliberately OUTSIDE the scope: like the upload route, a
failed dispatch does not roll back a decision that already stands;
the version sits in uploaded and the existing retry path can pick it
up. Approve and withdraw both dispatch ingest (O3: withdraw triggers
ingest, so a withdrawn version reaches ready through the normal
pipeline instead of stalling in uploaded).
"""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from typing import Callable

from pivot.audit.service import AuditService
from pivot.auth.errors import forbidden, not_found
from pivot.auth.ports import (
    ApprovalRequest,
    Clock,
    DepartmentAdminStore,
    Library,
    Principal,
)
from pivot.documents.errors import illegal_state
from pivot.documents.ports import (
    DocumentRecord,
    DocumentStore,
    FileContent,
    ObjectStore,
    VersionRecord,
    VersionStore,
)
from pivot.domain.document_state import next_state
from pivot.security.rbac import AccessControl

logger = logging.getLogger("pivot.approvals")


class ApprovalService:
    """Decide publish-approval requests (ADR-019 D1)."""

    def __init__(
        self,
        *,
        store: DepartmentAdminStore,
        documents: DocumentStore,
        versions: VersionStore,
        objects: ObjectStore,
        access: AccessControl,
        audits: AuditService,
        clock: Clock,
        transaction: Callable[[], AbstractContextManager[None]] | None = None,
        ingest: Callable[[str, str, str], object] | None = None,
    ) -> None:
        """Build the service.

        ``transaction`` is the PostgreSQL path's per-operation scope
        (ADR-017 D4), exactly like DepartmentAdminService: bootstrap
        passes a factory opening one shared session for the mutation
        and its audit writes. The memory path passes nothing and keeps
        the compensation behavior. ``ingest`` is the upload route's
        ingest submitter shape (version_id, request_id, actor_id);
        None means approve/withdraw change state but dispatch nothing
        (tests and non-ingest assemblies).
        """
        self._store = store
        self._documents = documents
        self._versions = versions
        self._objects = objects
        self._access = access
        self._audits = audits
        self._clock = clock
        self._transaction = transaction
        self._ingest = ingest

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

        Same discipline as DepartmentAdminService: on the PostgreSQL
        path the enclosing scope rolls everything back on a failed
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
                logger.exception("approval audit failure rollback failed")
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
        """Audit an overreach attempt best-effort (ADR-019 D6: overreach
        attempts enter the record), then raise the denial."""
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
            logger.exception("denied approval audit write failed; denial stands")
        raise error

    # -- scope helpers ---------------------------------------------------

    def _is_approver(self, principal: Principal, library: Library) -> bool:
        """Decision power for this target library (ADR-019 D1)."""
        if principal.role == "admin":
            return True
        if library.kind == "department":
            return self._access.is_department_admin(
                principal, library.dept_id or library.id
            )
        if library.kind == "project":
            return self._access.is_project_lead(principal, library.id)
        # Public targets are decided by super admins only; department
        # admins and leads hold no power there. Unknown kinds decide
        # nobody (fail closed; S3 target validation never creates
        # requests for them).
        return False

    def _sees_queue(self, principal: Principal, library: Library) -> bool:
        """Queue visibility, wider than decision power (ADR-019 D6).

        A department admin sees pending requests targeting project
        libraries their department owns, in addition to their own
        department targets; they still cannot decide the project ones.
        """
        if self._is_approver(principal, library):
            return True
        return (
            library.kind == "project"
            and library.dept_id is not None
            and library.dept_id
            in self._access.admin_departments(principal)
        )

    def _is_delegated(self, principal: Principal, library: Library) -> bool:
        """O2: a super admin acting on a department or project queue
        acts by delegation; on the public queue the same action is an
        ordinary approval (the public queue already belongs to super
        admins)."""
        return principal.role == "admin" and library.kind != "public"

    def _meta(
        self, request: ApprovalRequest, library: Library
    ) -> dict[str, object]:
        """Audit metadata for approval events (ADR-019 D6).

        dept_id is the owning department so the department audit view
        picks the event up; project_id keys the lead audit view. For
        public targets dept_id is "pub" (S5 unifies the public-target
        convention across approval and move events; no department
        admin holds dept "pub", so the value leaks into no dept view).
        """
        if library.kind == "department":
            dept_id: str | None = library.dept_id or library.id
        elif library.kind == "project":
            dept_id = library.dept_id
        else:
            dept_id = "pub"
        return {
            "document_id": request.document_id,
            "version_id": request.version_id,
            "target_library_id": request.target_library_id,
            "proposer": request.proposer,
            "dept_id": dept_id,
            "project_id": library.id if library.kind == "project" else None,
        }

    def _require_request(
        self, request_id: str, http_request_id: str
    ) -> ApprovalRequest:
        request = self._store.get_approval_request(request_id)
        if request is None:
            raise not_found(http_request_id)
        return request

    def _require_target(
        self, request: ApprovalRequest, http_request_id: str
    ) -> Library:
        library = self._store.get_library(request.target_library_id)
        if library is None:
            raise not_found(http_request_id)
        return library

    def _dept_id(
        self, request: ApprovalRequest, library: Library
    ) -> str | None:
        """Owning-department value for denial audits (same rule as
        the decision metadata, without building the full dict)."""
        meta = self._meta(request, library)
        value = meta.get("dept_id")
        return value if isinstance(value, str) else None

    def _require_decider(
        self,
        principal: Principal,
        request: ApprovalRequest,
        library: Library,
        http_request_id: str,
    ) -> None:
        """Approve/reject power: approvers decide; the proposer knows
        the request exists so a proposer attempt is forbidden, while
        anyone else outside the queue sees not_found (no leak)."""
        if self._is_approver(principal, library):
            return
        if principal.user_id == request.proposer:
            self._deny(
                principal,
                http_request_id,
                dept_id=self._dept_id(request, library),
                target=request.id,
                error=forbidden(http_request_id),
            )
        self._deny(
            principal,
            http_request_id,
            dept_id=self._dept_id(request, library),
            target=request.id,
            error=not_found(http_request_id),
        )

    def _require_proposer(
        self,
        principal: Principal,
        request: ApprovalRequest,
        library: Library,
        http_request_id: str,
    ) -> None:
        """Withdraw/resubmit power: the proposer only. A queue-visible
        non-proposer gets forbidden (they can see the request); anyone
        else gets not_found."""
        if principal.user_id == request.proposer:
            return
        if principal.role == "admin" or self._sees_queue(principal, library):
            self._deny(
                principal,
                http_request_id,
                dept_id=self._dept_id(request, library),
                target=request.id,
                error=forbidden(http_request_id),
            )
        self._deny(
            principal,
            http_request_id,
            dept_id=self._dept_id(request, library),
            target=request.id,
            error=not_found(http_request_id),
        )

    def _require_pending(
        self, request: ApprovalRequest, http_request_id: str
    ) -> None:
        if request.status != "pending":
            raise illegal_state(
                http_request_id, f"request is {request.status}, not pending"
            )

    def _require_version(
        self, request: ApprovalRequest, http_request_id: str
    ) -> VersionRecord:
        version = self._versions.get(request.version_id)
        if version is None:
            raise not_found(http_request_id)
        return version

    def _require_document(
        self, request: ApprovalRequest, http_request_id: str
    ) -> DocumentRecord:
        document = self._documents.get(request.document_id)
        if document is None or document.deleted_at is not None:
            raise not_found(http_request_id)
        return document

    def _decision_records(
        self,
        *,
        principal: Principal,
        request: ApprovalRequest,
        library: Library,
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
                "metadata": self._meta(request, library),
            }
        ]
        if self._is_delegated(principal, library):
            records.append(
                {
                    "actor": principal.user_id,
                    "action": "authz.approval.delegated",
                    "target": request.id,
                    "result": "ok",
                    "request_id": http_request_id,
                    "metadata": self._meta(request, library),
                }
            )
        return records

    def _dispatch_ingest(
        self, version_id: str, http_request_id: str, actor_id: str
    ) -> None:
        """Trigger the normal pipeline for an uploaded version.

        Called AFTER the atomic decision block, mirroring the upload
        route: a dispatch failure propagates but does not roll back a
        decision that already stands (the version sits in uploaded and
        the existing retry path can pick it up).
        """
        if self._ingest is not None:
            self._ingest(version_id, http_request_id, actor_id)

    # -- decisions ---------------------------------------------------------

    def approve(
        self, principal: Principal, request_id: str, http_request_id: str
    ) -> ApprovalRequest:
        """Approve a pending request (ADR-019 D1).

        Order is load-bearing and must not be rearranged: close the
        request, rewrite the document's library to the target, move
        the version pending_approval -> uploaded, and only then
        dispatch ingest, so the pipeline indexes into the target
        library's collection, never the old one. S3's self-approval
        fast path reuses this method unchanged: it creates the
        request, then calls approve() as the target approver.
        """
        request = self._require_request(request_id, http_request_id)
        library = self._require_target(request, http_request_id)
        self._require_decider(principal, request, library, http_request_id)
        self._require_pending(request, http_request_id)
        version = self._require_version(request, http_request_id)
        document = self._require_document(request, http_request_id)
        if document.library_id != "unassigned":
            # Pending documents stay unassigned by construction (D1);
            # anything else means the request and the document drifted
            # apart, and approving would publish into the wrong scope.
            raise illegal_state(
                http_request_id, "pending document is not unassigned"
            )
        new_state = next_state(version.state, "approve", http_request_id)
        now = self._clock.now()
        decided = replace(
            request, status="approved", decided_at=now, decided_by=principal.user_id
        )
        old_library_id = document.library_id
        old_state = version.state

        def rollback() -> None:
            self._store.set_approval_request(request)
            document.library_id = old_library_id
            self._documents.save(document)
            version.state = old_state
            self._versions.save(version)

        with self._atomic():
            self._store.set_approval_request(decided)
            document.library_id = library.id
            self._documents.save(document)
            version.state = new_state
            self._versions.save(version)
            self._record_all_or_rollback(
                rollback=rollback,
                records=self._decision_records(
                    principal=principal,
                    request=decided,
                    library=library,
                    action="authz.approval.approved",
                    http_request_id=http_request_id,
                ),
            )
        self._dispatch_ingest(version.id, http_request_id, principal.user_id)
        return decided

    def reject(
        self,
        principal: Principal,
        request_id: str,
        http_request_id: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """Reject a pending request (ADR-019 D1): the version goes to
        rejected, the document stays unassigned, the request closes
        with the (optional, Q2) reason. No ingest is dispatched."""
        request = self._require_request(request_id, http_request_id)
        library = self._require_target(request, http_request_id)
        self._require_decider(principal, request, library, http_request_id)
        self._require_pending(request, http_request_id)
        version = self._require_version(request, http_request_id)
        new_state = next_state(version.state, "reject", http_request_id)
        now = self._clock.now()
        decided = replace(
            request,
            status="rejected",
            reason=reason,
            decided_at=now,
            decided_by=principal.user_id,
        )
        old_state = version.state

        def rollback() -> None:
            self._store.set_approval_request(request)
            version.state = old_state
            self._versions.save(version)

        with self._atomic():
            self._store.set_approval_request(decided)
            version.state = new_state
            self._versions.save(version)
            self._record_all_or_rollback(
                rollback=rollback,
                records=self._decision_records(
                    principal=principal,
                    request=decided,
                    library=library,
                    action="authz.approval.rejected",
                    http_request_id=http_request_id,
                ),
            )
        return decided

    def withdraw(
        self, principal: Principal, request_id: str, http_request_id: str
    ) -> ApprovalRequest:
        """Withdraw a pending request (ADR-019 D1/D6): proposer only,
        version back to uploaded, request closed as withdrawn. O3:
        withdraw dispatches ingest, so the version proceeds through
        the normal pipeline (and then the claim path) instead of
        stalling in uploaded, which would make withdraw a disguised
        rejection."""
        request = self._require_request(request_id, http_request_id)
        library = self._require_target(request, http_request_id)
        self._require_proposer(principal, request, library, http_request_id)
        self._require_pending(request, http_request_id)
        version = self._require_version(request, http_request_id)
        new_state = next_state(version.state, "withdraw", http_request_id)
        now = self._clock.now()
        withdrawn = replace(
            request, status="withdrawn", decided_at=now, decided_by=principal.user_id
        )
        old_state = version.state

        def rollback() -> None:
            self._store.set_approval_request(request)
            version.state = old_state
            self._versions.save(version)

        with self._atomic():
            self._store.set_approval_request(withdrawn)
            version.state = new_state
            self._versions.save(version)
            self._record_all_or_rollback(
                rollback=rollback,
                records=[
                    {
                        "actor": principal.user_id,
                        "action": "doc.approval.withdrawn",
                        "target": request.id,
                        "result": "ok",
                        "request_id": http_request_id,
                        "metadata": self._meta(request, library),
                    }
                ],
            )
        self._dispatch_ingest(version.id, http_request_id, principal.user_id)
        return withdrawn

    def resubmit(
        self,
        principal: Principal,
        request_id: str,
        http_request_id: str,
        target_library_id: str | None = None,
    ) -> ApprovalRequest:
        """Resubmit a rejected request (ADR-019 D1): proposer only,
        version rejected -> pending_approval, optionally retargeted
        (a new target re-scopes the approver on the next decision;
        target-permission validation is S3's upload-path job, S2 only
        checks the target exists). The new pending round is audited
        as a fresh doc.approval.requested: there is no separate
        resubmit event in the 8+1 set."""
        request = self._require_request(request_id, http_request_id)
        library = self._require_target(request, http_request_id)
        self._require_proposer(principal, request, library, http_request_id)
        if request.status != "rejected":
            raise illegal_state(
                http_request_id, f"request is {request.status}, not rejected"
            )
        if target_library_id is not None and target_library_id != request.target_library_id:
            new_library = self._store.get_library(target_library_id)
            if new_library is None:
                raise not_found(http_request_id)
            library = new_library
        version = self._require_version(request, http_request_id)
        new_state = next_state(version.state, "resubmit", http_request_id)
        reopened = replace(
            request,
            status="pending",
            target_library_id=library.id,
            reason="",
            decided_at=None,
            decided_by=None,
        )
        old_state = version.state

        def rollback() -> None:
            self._store.set_approval_request(request)
            version.state = old_state
            self._versions.save(version)

        with self._atomic():
            self._store.set_approval_request(reopened)
            version.state = new_state
            self._versions.save(version)
            self._record_all_or_rollback(
                rollback=rollback,
                records=[
                    {
                        "actor": principal.user_id,
                        "action": "doc.approval.requested",
                        "target": request.id,
                        "result": "ok",
                        "request_id": http_request_id,
                        "metadata": self._meta(reopened, library),
                    }
                ],
            )
        return reopened

    # -- queue and review --------------------------------------------------

    def list_pending(self, principal: Principal) -> tuple[ApprovalRequest, ...]:
        """Pending requests in the caller's scope (ADR-019 D1/D6).

        Super admins see the global queue; department admins see
        their department targets plus project targets their department
        owns; project leads see their own project targets; proposers
        see their own submissions. Decided requests are not queue
        items: proposers and approvers reach them via get_request.
        """
        visible: list[ApprovalRequest] = []
        for document_id in self._pending_document_ids():
            for request in self._store.list_approval_requests(document_id):
                if request.status != "pending":
                    continue
                library = self._store.get_library(request.target_library_id)
                if library is None:
                    continue
                if (
                    principal.role == "admin"
                    or request.proposer == principal.user_id
                    or self._sees_queue(principal, library)
                ):
                    visible.append(request)
        visible.sort(
            key=lambda item: (item.created_at is None, item.created_at, item.id)
        )
        return tuple(visible)

    def _pending_document_ids(self) -> frozenset[str]:
        """Document ids with at least one approval request, derived
        from the catalog's document set. The store protocol lists
        requests per document, so the service walks the documents it
        knows; the PG catalog backs the same walk."""
        return frozenset(
            document.id for document in self._documents_list()
        )

    def _documents_list(self):
        """All documents known to the document store, if it lists
        them; the memory and SQL document stores both do."""
        listing = getattr(self._documents, "list_active", None)
        if listing is None:
            return ()
        return listing()

    def get_request(
        self, principal: Principal, request_id: str, http_request_id: str
    ) -> ApprovalRequest:
        """One request: super admins, the proposer, and queue-visible
        approvers may see it (including decided ones: proposers see
        their own submissions and results). Anyone else gets
        not_found, never a leak about the request."""
        request = self._require_request(request_id, http_request_id)
        library = self._require_target(request, http_request_id)
        if (
            principal.role == "admin"
            or request.proposer == principal.user_id
            or self._sees_queue(principal, library)
        ):
            return request
        raise not_found(http_request_id)

    def review_read(
        self, principal: Principal, request_id: str, http_request_id: str
    ) -> FileContent:
        """Dedicated review read (ADR-019 D1): never preview/download.

        Allowed for the proposer, the target approver, or a super
        admin, and only while the request is pending (once decided,
        the normal preview/download paths own the document again).
        Reads the version's stored bytes from its quarantine object
        and audits doc.approval.review on every read. The review
        audit is a doc.* event, so under the tiered failure policy it
        is best-effort rather than critical; the scope check itself
        never depends on the audit write.
        """
        request = self._require_request(request_id, http_request_id)
        library = self._require_target(request, http_request_id)
        if (
            principal.role != "admin"
            and request.proposer != principal.user_id
            and not self._is_approver(principal, library)
        ):
            self._deny(
                principal,
                http_request_id,
                dept_id=self._dept_id(request, library),
                target=request.id,
                error=not_found(http_request_id),
            )
        if request.status != "pending":
            raise illegal_state(
                http_request_id, f"request is {request.status}, not pending"
            )
        version = self._require_version(request, http_request_id)
        document = self._require_document(request, http_request_id)
        body = self._objects.get(version.storage_key)
        if body is None:
            raise not_found(http_request_id)
        self._audits.record(
            actor=principal.user_id,
            action="doc.approval.review",
            target=request.id,
            result="ok",
            request_id=http_request_id,
            metadata=self._meta(request, library),
        )
        return FileContent(
            body=body,
            filename=document.title or document.id,
            media_type="application/octet-stream",
            disposition="inline",
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "ApprovalService()"
