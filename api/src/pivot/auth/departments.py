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
from datetime import datetime, timedelta, timezone

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


class _UnsetType:
    """Sentinel for 'argument omitted' on set_member_role."""


_UNSET = _UnsetType()

# ADR-017 Q1: the 60-day cap binds only the project-lead level. Project
# leads do not exist until P1-4, so no live grantor is capped today; the
# cap lives here as a grantor-kind parameter so P1-4 wires it in without
# touching this validation again. Super admins and department admins
# are unlimited, including long-term grants.
_MAX_GRANT_DAYS: dict[str, int] = {"project_lead": 60}


def _grantor_kind(principal: Principal) -> str:
    if principal.role == "admin":
        return "admin"
    return "dept_admin"


def _check_grant_expiry(
    grantor_kind: str, expires_at: datetime | None, now: datetime
) -> None:
    cap = _MAX_GRANT_DAYS.get(grantor_kind)
    if cap is None:
        return
    if expires_at is None:
        # ADR-017 Q1: a capped grantor (project lead) cannot grant
        # permanent membership; long-term is reserved for uncapped roles.
        raise ValueError(f"{grantor_kind} grants cannot be permanent")
    if _as_utc(expires_at) > _as_utc(now) + timedelta(days=cap):
        raise ValueError(f"{grantor_kind} grants last at most {cap} days")


def _as_utc(value: datetime) -> datetime:
    # SQLite reads DateTime(timezone=True) back naive; stored values are
    # UTC, so a naive value reads as UTC rather than local time.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_utc(value).isoformat().replace("+00:00", "Z")


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

    def _record_all_or_rollback(self, *, rollback, records) -> None:
        """Record audit events, compensating the mutation on any failure.

        With two events (a role change plus its renewal event) both are
        attempted before the rollback decision, so a failure in either
        restores the old membership. The append-only audit cannot unwrite
        an event recorded before a later one fails; S4 (ADR-017 D4) makes
        the mutation and its events atomic on the PostgreSQL path.
        """
        try:
            for record_kwargs in records:
                self._audits.record(**record_kwargs)
        except Exception:
            try:
                rollback()
            except Exception:
                logger.exception("audit failure rollback failed")
            raise

    def _record_or_rollback(self, *, rollback, record_kwargs) -> None:
        """Record the audit event, compensating the mutation on failure."""
        self._record_all_or_rollback(rollback=rollback, records=[record_kwargs])

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
        *, expires_at: datetime | None = None,
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
        _check_grant_expiry(
            _grantor_kind(principal), expires_at, self._clock.now()
        )
        membership = Membership(
            user_id=user_id,
            dept_id=dept_id,
            dept_role=dept_role,
            granted_by=principal.user_id,
            granted_at=self._clock.now(),
            expires_at=expires_at,
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
                    "expires_at": _iso(expires_at),
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
        *, expires_at: datetime | None | _UnsetType = _UNSET,
    ) -> Membership:
        """Change a member's role and optionally its expiry (ADR-017 D2).

        Omitted expires_at keeps the stored value: the role-change path
        rebuilds the Membership (and resets grantor/granted_at, as before)
        but must not drop the expiry. Explicit None clears it to a
        long-term grant. A renewal is an explicit expiry change before
        expiry that extends it (later finite value, or to long-term);
        it writes its own renewal audit event. Shortening an expiry or
        restricting a long-term grant is not a renewal.
        """
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
            # Expired rows are purged by the department-member read above,
            # so an expired membership is already gone: it cannot be
            # renewed, only re-granted through add_member (ADR-017 Q3).
            raise not_found(request_id)
        explicit = not isinstance(expires_at, _UnsetType)
        new_expires = current.expires_at if not explicit else expires_at
        if explicit:
            _check_grant_expiry(
                _grantor_kind(principal), new_expires, self._clock.now()
            )
        updated = Membership(
            user_id=user_id,
            dept_id=dept_id,
            dept_role=dept_role,
            granted_by=principal.user_id,
            granted_at=self._clock.now(),
            expires_at=new_expires,
        )
        self._store.set_membership(updated)
        records = [
            {
                "actor": principal.user_id,
                "action": "authz.permission_change",
                "target": user_id,
                "result": "ok",
                "request_id": request_id,
                "metadata": {
                    "dept_id": dept_id,
                    "old_role": current.dept_role,
                    "new_role": dept_role,
                    "expires_at": _iso(new_expires),
                },
            },
        ]
        if (
            explicit
            and new_expires != current.expires_at
            and current.expires_at is not None
            and (
                new_expires is None
                or _as_utc(new_expires) > _as_utc(current.expires_at)
            )
        ):
            records.append(
                {
                    "actor": principal.user_id,
                    "action": "authz.permission_renewed",
                    "target": user_id,
                    "result": "ok",
                    "request_id": request_id,
                    "metadata": {
                        "dept_id": dept_id,
                        "old_expires_at": _iso(current.expires_at),
                        "new_expires_at": _iso(new_expires),
                    },
                }
            )
        self._record_all_or_rollback(
            rollback=lambda: self._store.set_membership(current),
            records=records,
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
