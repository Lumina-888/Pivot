"""Department administration: libraries, memberships, claims (ADR-016 D3, D10).

Power matrix, enforced here and nowhere else:

- Super admins (global role ``admin``) manage everything.
- Department admins manage only their own department, and only
  editor/reader memberships: appointing or removing a dept_admin is a
  super admin act, because dept_admin is itself a privilege grant.
- Cross-department attempts are answered as "not found" so one
  department's existence and membership are never leaked to another.
  Overreach inside a department the caller does administer (granting
  dept_admin, claiming to the public library) is a plain forbidden:
  the target is already known to the caller.
- Every change writes an ``authz.*`` audit event (critical under the
  tiered policy: a failed audit write refuses the operation). The
  mutation runs first and the audit second; if the audit write raises,
  the mutation is compensated back so no permission change ever lands
  without its trace. Denied attempts are audited best-effort: the
  denial stands even if that audit write fails.
- Appointment and removal take effect on the next request with no
  token action: authentication rebuilds the Principal from the live
  user directory on every request, and membership reads go to the live
  catalog on every call. Token versions are untouched by membership
  changes, so users are not logged out by an admin's routine edit.

Out of scope here (P1-3): upload-time library choice and moves between
two department libraries, both of which need the approval flow. The
claim endpoint only assigns unassigned documents to a library.
"""

from __future__ import annotations

import logging
import re
from dataclasses import replace

from pivot.audit.service import AuditService
from pivot.auth.errors import forbidden, not_found, resource_forbidden
from pivot.auth.ports import (
    Clock,
    DepartmentAdminStore,
    Library,
    Membership,
    Principal,
    UserDirectory,
)
from pivot.documents.ports import DocumentRecord, DocumentStore
from pivot.security.rbac import AccessControl

logger = logging.getLogger("pivot.auth.departments")

_DEPT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
_DEPT_ROLES = frozenset({"dept_admin", "editor", "reader"})
_ASSIGNABLE_BY_DEPT_ADMIN = frozenset({"editor", "reader"})


class DepartmentAdminService:
    def __init__(
        self,
        *,
        store: DepartmentAdminStore,
        documents: DocumentStore,
        users: UserDirectory,
        access: AccessControl,
        audits: AuditService,
        clock: Clock,
    ) -> None:
        self._store = store
        self._documents = documents
        self._users = users
        self._access = access
        self._audits = audits
        self._clock = clock

    # -- authorization helpers -------------------------------------------------

    def admin_departments(self, principal: Principal) -> frozenset[str]:
        """Departments the principal administers as dept_admin."""
        return self._access.admin_departments(principal)

    def _deny(
        self,
        principal: Principal,
        request_id: str,
        *,
        dept_id: str | None,
        target: str,
        error,
    ):
        """Audit a denied attempt best-effort, then raise the denial."""
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
            logger.exception("denied admin audit write failed; denial stands")
        raise error

    def _require_super_admin(
        self, principal: Principal, request_id: str, *, target: str
    ) -> None:
        if principal.role != "admin":
            self._deny(
                principal, request_id, dept_id=None, target=target,
                error=forbidden(request_id),
            )

    def _require_department_scope(
        self, principal: Principal, dept_id: str, request_id: str, *, target: str
    ) -> None:
        """Super admin anywhere; dept admin only inside their department."""
        if principal.role == "admin":
            return
        if self._access.is_department_admin(principal, dept_id):
            return
        self._deny(
            principal, request_id, dept_id=dept_id, target=target,
            error=not_found(request_id),
        )

    def _record_or_rollback(self, *, rollback, record_kwargs) -> None:
        """Record the audit event, compensating the mutation on failure."""
        try:
            self._audits.record(**record_kwargs)
        except Exception:
            try:
                rollback()
            except Exception:
                logger.exception("audit failure rollback failed")
            raise

    # -- departments ------------------------------------------------------------

    def create_department(
        self, principal: Principal, dept_id: str, name: str, request_id: str
    ) -> tuple[Library, bool]:
        self._require_super_admin(principal, request_id, target=dept_id)
        if not _DEPT_ID_PATTERN.match(dept_id):
            raise ValueError("dept_id must match [a-z0-9][a-z0-9_-]{0,127}")
        if not name or len(name) > 255:
            raise ValueError("department name must be 1-255 characters")
        existing = self._store.get_library(dept_id)
        if existing is not None:
            if existing.kind == "department":
                return existing, False
            raise resource_forbidden(request_id)
        library = Library(
            id=dept_id, name=name, kind="department", dept_id=dept_id
        )
        self._store.create_library(library)
        self._record_or_rollback(
            rollback=lambda: self._store.delete_library(dept_id),
            record_kwargs={
                "actor": principal.user_id,
                "action": "authz.department.create",
                "target": dept_id,
                "result": "ok",
                "request_id": request_id,
                "metadata": {"dept_id": dept_id, "name": name},
            },
        )
        return library, True

    def remove_department(
        self, principal: Principal, dept_id: str, request_id: str
    ) -> None:
        self._require_super_admin(principal, request_id, target=dept_id)
        library = self._store.get_library(dept_id)
        if library is None or library.kind != "department":
            raise not_found(request_id)
        members = self._store.get_department_members(dept_id)
        live_docs = tuple(
            document
            for document in self._documents.list_active()
            if document.library_id == dept_id and document.deleted_at is None
        )
        if members or live_docs:
            raise resource_forbidden(request_id)
        self._store.delete_library(dept_id)
        self._record_or_rollback(
            rollback=lambda: self._store.create_library(library),
            record_kwargs={
                "actor": principal.user_id,
                "action": "authz.department.remove",
                "target": dept_id,
                "result": "ok",
                "request_id": request_id,
                "metadata": {
                    "dept_id": dept_id,
                    "document_count": len(live_docs),
                    "member_count": len(members),
                },
            },
        )

    def list_departments(
        self, principal: Principal, request_id: str
    ) -> tuple[Library, ...]:
        if principal.role == "admin":
            return self._store.list_libraries()
        admin_depts = self._access.admin_departments(principal)
        if not admin_depts:
            self._deny(
                principal, request_id, dept_id=None, target="departments",
                error=forbidden(request_id),
            )
        return tuple(
            library
            for library in self._store.list_libraries()
            if library.id == "pub" or library.id in admin_depts
        )

    def get_department(
        self, principal: Principal, dept_id: str, request_id: str
    ) -> Library:
        if principal.role == "admin":
            library = self._store.get_library(dept_id)
            if library is None:
                raise not_found(request_id)
            return library
        if dept_id == "pub":
            library = self._store.get_library("pub")
            if library is None:
                raise not_found(request_id)
            return library
        self._require_department_scope(
            principal, dept_id, request_id, target=dept_id
        )
        library = self._store.get_library(dept_id)
        if library is None:
            raise not_found(request_id)
        return library

    # -- memberships ------------------------------------------------------------

    def _require_department_library(self, dept_id: str, request_id: str) -> Library:
        library = self._store.get_library(dept_id)
        if library is None or library.kind != "department":
            raise not_found(request_id)
        return library

    def list_members(
        self, principal: Principal, dept_id: str, request_id: str
    ) -> tuple[Membership, ...]:
        if principal.role != "admin":
            if not self._access.admin_departments(principal):
                self._deny(
                    principal, request_id, dept_id=dept_id, target=dept_id,
                    error=forbidden(request_id),
                )
            self._require_department_scope(
                principal, dept_id, request_id, target=dept_id
            )
        self._require_department_library(dept_id, request_id)
        return self._store.get_department_members(dept_id)

    def add_member(
        self, principal: Principal, dept_id: str, user_id: str,
        dept_role: str, request_id: str,
    ) -> tuple[Membership, bool]:
        if dept_role not in _DEPT_ROLES:
            raise ValueError("dept_role must be dept_admin, editor, or reader")
        if principal.role != "admin":
            if not self._access.admin_departments(principal):
                self._deny(
                    principal, request_id, dept_id=dept_id, target=dept_id,
                    error=forbidden(request_id),
                )
            self._require_department_scope(
                principal, dept_id, request_id, target=dept_id
            )
            if dept_role not in _ASSIGNABLE_BY_DEPT_ADMIN:
                self._deny(
                    principal, request_id, dept_id=dept_id, target=user_id,
                    error=forbidden(request_id),
                )
        self._require_department_library(dept_id, request_id)
        if self._users.get_by_id(user_id) is None:
            raise not_found(request_id)
        for member in self._store.get_department_members(dept_id):
            if member.user_id == user_id:
                return member, False
        membership = Membership(
            user_id=user_id,
            dept_id=dept_id,
            dept_role=dept_role,
            granted_by=principal.user_id,
            granted_at=self._clock.now(),
        )
        self._store.add_membership(membership)
        self._record_or_rollback(
            rollback=lambda: self._store.remove_membership(user_id, dept_id),
            record_kwargs={
                "actor": principal.user_id,
                "action": "authz.permission_change",
                "target": user_id,
                "result": "ok",
                "request_id": request_id,
                "metadata": {
                    "dept_id": dept_id,
                    "dept_role": dept_role,
                    "granted_by": principal.user_id,
                },
            },
        )
        return membership, True

    def remove_member(
        self, principal: Principal, dept_id: str, user_id: str, request_id: str
    ) -> None:
        if principal.role != "admin":
            if not self._access.admin_departments(principal):
                self._deny(
                    principal, request_id, dept_id=dept_id, target=user_id,
                    error=forbidden(request_id),
                )
            self._require_department_scope(
                principal, dept_id, request_id, target=user_id
            )
        self._require_department_library(dept_id, request_id)
        current = next(
            (
                member
                for member in self._store.get_department_members(dept_id)
                if member.user_id == user_id
            ),
            None,
        )
        if current is None:
            raise not_found(request_id)
        if (
            principal.role != "admin"
            and current.dept_role == "dept_admin"
        ):
            self._deny(
                principal, request_id, dept_id=dept_id, target=user_id,
                error=forbidden(request_id),
            )
        self._store.remove_membership(user_id, dept_id)
        self._record_or_rollback(
            rollback=lambda: self._store.add_membership(current),
            record_kwargs={
                "actor": principal.user_id,
                "action": "authz.permission_change",
                "target": user_id,
                "result": "ok",
                "request_id": request_id,
                "metadata": {
                    "dept_id": dept_id,
                    "removed_role": current.dept_role,
                },
            },
        )

    def set_member_role(
        self, principal: Principal, dept_id: str, user_id: str,
        dept_role: str, request_id: str,
    ) -> Membership:
        if dept_role not in _DEPT_ROLES:
            raise ValueError("dept_role must be dept_admin, editor, or reader")
        if principal.role != "admin":
            if not self._access.admin_departments(principal):
                self._deny(
                    principal, request_id, dept_id=dept_id, target=user_id,
                    error=forbidden(request_id),
                )
            self._require_department_scope(
                principal, dept_id, request_id, target=user_id
            )
            if dept_role not in _ASSIGNABLE_BY_DEPT_ADMIN:
                self._deny(
                    principal, request_id, dept_id=dept_id, target=user_id,
                    error=forbidden(request_id),
                )
        self._require_department_library(dept_id, request_id)
        current = next(
            (
                member
                for member in self._store.get_department_members(dept_id)
                if member.user_id == user_id
            ),
            None,
        )
        if current is None:
            raise not_found(request_id)
        updated = Membership(
            user_id=user_id,
            dept_id=dept_id,
            dept_role=dept_role,
            granted_by=principal.user_id,
            granted_at=self._clock.now(),
        )
        self._store.set_membership(updated)
        self._record_or_rollback(
            rollback=lambda: self._store.set_membership(current),
            record_kwargs={
                "actor": principal.user_id,
                "action": "authz.permission_change",
                "target": user_id,
                "result": "ok",
                "request_id": request_id,
                "metadata": {
                    "dept_id": dept_id,
                    "old_role": current.dept_role,
                    "new_role": dept_role,
                },
            },
        )
        return updated

    # -- claims ------------------------------------------------------------------

    def claim_document(
        self, principal: Principal, document_id: str, library_id: str,
        request_id: str,
    ) -> DocumentRecord:
        document = self._documents.get(document_id)
        if document is None or document.deleted_at is not None:
            raise not_found(request_id)
        if principal.role != "admin":
            if not self._access.admin_departments(principal):
                self._deny(
                    principal, request_id, dept_id=library_id,
                    target=document_id, error=forbidden(request_id),
                )
            if library_id == "pub":
                self._deny(
                    principal, request_id, dept_id=library_id,
                    target=document_id, error=forbidden(request_id),
                )
            if not self._access.is_department_admin(principal, library_id):
                self._deny(
                    principal, request_id, dept_id=library_id,
                    target=document_id, error=not_found(request_id),
                )
        target = self._store.get_library(library_id)
        if target is None:
            raise not_found(request_id)
        if library_id == "unassigned":
            raise resource_forbidden(request_id)
        if target.kind not in ("public", "department"):
            raise not_found(request_id)
        if document.library_id != "unassigned":
            if principal.role == "admin":
                raise resource_forbidden(request_id)
            raise not_found(request_id)
        claimed = replace(document, library_id=library_id)
        self._documents.save(claimed)
        self._record_or_rollback(
            rollback=lambda: self._documents.save(document),
            record_kwargs={
                "actor": principal.user_id,
                "action": "authz.library.claim",
                "target": document_id,
                "result": "ok",
                "request_id": request_id,
                "metadata": {
                    "dept_id": library_id,
                    "from_library": "unassigned",
                    "to_library": library_id,
                },
            },
        )
        return claimed
