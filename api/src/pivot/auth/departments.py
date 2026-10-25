"""Department administration: libraries, memberships, claims, exceptions.

(ADR-016 D3, D10; ADR-017 D1, Q2, Q4.)

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
  tiered policy: a failed audit write refuses the operation). On the
  PostgreSQL path (ADR-017 D4) the mutation and its audit events share
  one transaction, so a failed audit write rolls the mutation back
  with it and no permission change ever lands without its trace. On
  the memory path there is no transaction, so the mutation is
  compensated back after a failed audit write instead. Denied attempts
  are audited best-effort: the denial stands even if that audit write
  fails.
- Document exceptions (ADR-017 D1) grant whole-document visibility to
  one user or one department. Super admins grant anywhere; department
  admins grant personal exceptions only for their own department's
  documents, never department-target ones, and never on a document
  they see only through an exception of their own.
- Folders (ADR-018 D3, D2) are single-level restricted folders inside
  one department library; the default folder has no row, it is the
  library itself. Folder management (create, delete, member
  add/remove/role) is a department admin act. Folder documents
  (rename, move in/out) are a full-member act, and department admins
  bypass folder roles entirely inside their own department: a
  read-only folder is still fully open to its department admin.
  Folder members come only from the department's live members, and
  moving a document checks both sides: the source folder's full
  member (or department admin) and the target folder's. Deletion
  mirrors remove_department: members or live documents refuse it,
  and an empty folder's retrieval collection is deleted with it.
  Project libraries and project folders are P1-4 S3/S4, not here.
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
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from pivot.audit.service import AuditService
from pivot.auth.errors import forbidden, not_found, resource_forbidden
from pivot.auth.ports import (
    Clock,
    DepartmentAdminStore,
    DocumentException,
    Folder,
    FolderMembership,
    Library,
    Membership,
    Principal,
    UserDirectory,
)
from pivot.documents.ports import DocumentRecord, DocumentStore
from pivot.security.rbac import AccessControl
from pivot.shared.ids import new_id

logger = logging.getLogger("pivot.auth.departments")

_DEPT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
_DEPT_ROLES = frozenset({"dept_admin", "editor", "reader"})
_ASSIGNABLE_BY_DEPT_ADMIN = frozenset({"editor", "reader"})
# ADR-018 D3: folder roles. full manages folder documents (add, remove,
# rename, move) but never folder members, so it is not called admin.
_FOLDER_ROLES = frozenset({"full", "editor", "reader"})
# Fixed system library ids: folders share the retrieval key namespace
# with libraries, so a folder id equal to one of these would collide
# with the system library collection even when no row exists yet.
_SYSTEM_LIBRARY_IDS = frozenset({"pub", "unassigned"})


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


def _folder_is_live(member: FolderMembership, now: datetime) -> bool:
    """True when a folder membership has not expired (ADR-018 D3).

    Same exclusive boundary as department memberships (ADR-017 D2):
    NULL expires_at means a long-term grant; at expires_at itself the
    membership is already gone. Checked in Python because the hot
    get_folder_memberships path never writes (no lazy purge there).
    """
    if member.expires_at is None:
        return True
    return _as_utc(member.expires_at) > _as_utc(now)


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
        transaction: Callable[[], AbstractContextManager[None]] | None = None,
        folder_collection_drop: Callable[[str, str], None] | None = None,
    ) -> None:
        """Build the service.

        ``transaction`` is the PostgreSQL path's per-operation scope
        (ADR-017 D4): bootstrap passes a factory that opens one shared
        session for the mutation and its audit writes, so a failed
        audit write rolls the mutation back. The memory path passes
        nothing and keeps the compensation behavior.
        ``folder_collection_drop`` (library_id, folder_id) deletes a
        folder's retrieval collection when an empty folder is removed
        (ADR-018 D3): bootstrap wires the library index set's drop;
        None means no retrieval backend is attached, so deletion only
        removes rows. The drop runs before the row delete, so a failed
        drop refuses the deletion with nothing changed.
        """
        self._store = store
        self._documents = documents
        self._users = users
        self._access = access
        self._audits = audits
        self._clock = clock
        self._transaction = transaction
        self._folder_collection_drop = folder_collection_drop

    @contextmanager
    def _atomic(self):
        """Scope one mutation and its audit writes, if PG-backed."""
        if self._transaction is not None:
            with self._transaction():
                yield
        else:
            yield

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

        On the PostgreSQL path (a transaction scope was supplied,
        ADR-017 D4) there is no compensation to run: the mutation and
        its events share one transaction owned by the enclosing scope,
        so a failed audit write propagates and the scope rolls
        everything back — including an event recorded before a later
        one fails. On the memory path both events are attempted before
        the rollback decision, and an event already recorded cannot be
        unwritten from the append-only audit.
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
        with self._atomic():
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
        with self._atomic():
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
        with self._atomic():
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
        with self._atomic():
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
        with self._atomic():
            self._store.set_membership(updated)
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
        with self._atomic():
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

    # -- document exceptions (ADR-017 D1, Q2, Q4) --------------------------

    def _require_exception_manager(
        self, principal: Principal, doc_library_id: str, request_id: str, *,
        target: str,
    ) -> None:
        """Super admin anywhere; dept admin only inside their department.

        Callers who administer no department at all get forbidden: they
        are not managers. Dept admins outside the document's department
        get not_found: the document is not theirs to manage.
        """
        if principal.role == "admin":
            return
        if not self._access.admin_departments(principal):
            self._deny(
                principal, request_id, dept_id=doc_library_id,
                target=target, error=forbidden(request_id),
            )
        if not self._access.is_department_admin(principal, doc_library_id):
            self._deny(
                principal, request_id, dept_id=doc_library_id,
                target=target, error=not_found(request_id),
            )

    def grant_exception(
        self, principal: Principal, document_id: str, request_id: str, *,
        target_user_id: str | None = None,
        target_dept_id: str | None = None,
        reason: str = "",
        expires_at: datetime | None = None,
    ) -> tuple[DocumentException, bool]:
        """Grant whole-document visibility to one user or one department.

        Returns (exception, created). Granting is an upsert by
        (document, target): a re-grant updates the stored row's terms
        instead of adding a duplicate, whether the old row is live or
        expired. Permanent grants use NULL expires_at (ADR-017 Q2);
        no duration cap applies to exceptions.
        """
        if (target_user_id is None) == (target_dept_id is None):
            raise ValueError(
                "exactly one of target_user_id / target_dept_id is required"
            )
        document = self._documents.get(document_id)
        if document is None or document.deleted_at is not None:
            raise not_found(request_id)
        if target_user_id is not None:
            if self._users.get_by_id(target_user_id) is None:
                raise not_found(request_id)
        else:
            target_library = self._store.get_library(target_dept_id)
            if target_library is None or target_library.kind != "department":
                raise not_found(request_id)
        if principal.role != "admin":
            # Department-target grants are super-admin-only. This check
            # runs before the scope check so a dept admin attempting one
            # gets forbidden (a privilege denial), not not_found.
            if target_dept_id is not None:
                self._deny(
                    principal, request_id, dept_id=document.library_id,
                    target=document_id, error=forbidden(request_id),
                )
            # Grantor visibility is judged by library scope alone, never
            # by exceptions: a grantor who sees a document only through
            # an exception of their own cannot pass that visibility on.
            self._require_exception_manager(
                principal, document.library_id, request_id, target=document_id,
            )
        existing = next(
            (
                exception
                for exception in self._access.document_exceptions(document_id)
                if exception.target_user_id == target_user_id
                and exception.target_dept_id == target_dept_id
            ),
            None,
        )
        if existing is not None:
            exception = replace(
                existing,
                granted_by=principal.user_id,
                reason=reason,
                expires_at=expires_at,
            )
            created = False
        else:
            exception = DocumentException(
                id=new_id("exception"),
                document_id=document_id,
                target_user_id=target_user_id,
                target_dept_id=target_dept_id,
                granted_by=principal.user_id,
                reason=reason,
                expires_at=expires_at,
                created_at=self._clock.now(),
            )
            created = True
        metadata: dict[str, object] = {
            # Department audit views key on the DOCUMENT's library, not
            # on the grant target, so the owning department sees the
            # change (ADR-017 D1).
            "dept_id": document.library_id,
            "exception_id": exception.id,
            "expires_at": _iso(expires_at),
        }
        if target_user_id is not None:
            metadata["target_user_id"] = target_user_id
        if target_dept_id is not None:
            metadata["target_dept_id"] = target_dept_id
        if existing is None:
            def rollback():
                return self._store.remove_exception(exception.id)
        else:
            def rollback():
                return self._store.add_exception(existing)
        with self._atomic():
            self._store.add_exception(exception)
            self._record_or_rollback(
                rollback=rollback,
                record_kwargs={
                    "actor": principal.user_id,
                    "action": "authz.document_exception_granted",
                    "target": document_id,
                    "result": "ok",
                    "request_id": request_id,
                    "metadata": metadata,
                },
            )
        return exception, created

    def revoke_exception(
        self, principal: Principal, exception_id: str, request_id: str, *,
        document_id: str | None = None,
    ) -> None:
        """Revoke one exception grant.

        When document_id is given (the router path), it must match the
        exception's document, so a grant cannot be revoked through a
        stranger document's URL. Revocation only shrinks visibility, so
        a dept admin may revoke any grant on their own department's
        documents, including super-admin grants.
        """
        exception = self._access.exception(exception_id)
        if exception is None:
            raise not_found(request_id)
        if document_id is not None and exception.document_id != document_id:
            raise not_found(request_id)
        document = self._documents.get(exception.document_id)
        if document is None or document.deleted_at is not None:
            # Orphaned rows (document gone) can only be cleaned up by a
            # super admin; a dept admin cannot establish scope for one.
            if principal.role != "admin":
                self._deny(
                    principal, request_id, dept_id=None,
                    target=exception_id, error=not_found(request_id),
                )
            doc_library_id: str | None = None
        else:
            doc_library_id = document.library_id
            self._require_exception_manager(
                principal, doc_library_id, request_id, target=exception_id,
            )
        metadata: dict[str, object] = {"exception_id": exception.id}
        if doc_library_id is not None:
            metadata["dept_id"] = doc_library_id
        if exception.target_user_id is not None:
            metadata["target_user_id"] = exception.target_user_id
        if exception.target_dept_id is not None:
            metadata["target_dept_id"] = exception.target_dept_id
        with self._atomic():
            self._store.remove_exception(exception_id)
            self._record_or_rollback(
                rollback=lambda: self._store.add_exception(exception),
                record_kwargs={
                    "actor": principal.user_id,
                    "action": "authz.document_exception_revoked",
                    "target": exception.document_id,
                    "result": "ok",
                    "request_id": request_id,
                    "metadata": metadata,
                },
            )

    def list_exceptions(
        self, principal: Principal, document_id: str, request_id: str, *,
        permanent_only: bool = False,
    ) -> tuple[DocumentException, ...]:
        """Stored exception rows for one document, for its managers.

        Rows are returned as-is, live and expired alike; expiry is
        enforced by the visibility computation, not by this list. The
        permanent filter (expires_at NULL) is the ADR-017 Q2 review
        list for super admins. Non-managers never see this list: it
        reveals who else may read the document.
        """
        document = self._documents.get(document_id)
        if document is None or document.deleted_at is not None:
            raise not_found(request_id)
        self._require_exception_manager(
            principal, document.library_id, request_id, target=document_id,
        )
        rows = self._access.document_exceptions(document_id)
        if permanent_only:
            rows = tuple(row for row in rows if row.expires_at is None)
        return rows

    # -- folders (ADR-018 D3, D2) -----------------------------------------
    #
    # Power matrix, enforced here and nowhere else:
    # - Folder management (create, delete, member add/remove/role) is a
    #   department admin act: super admins anywhere, department admins
    #   only inside their own department. Folder members never manage
    #   members, not even full members: full excludes member management.
    # - Folder documents (rename, move in/out) are a full-member act:
    #   super admins and the department's admins bypass folder roles
    #   entirely (D2: a read-only folder is still fully open to its
    #   department admin), full members act, editors and readers are
    #   refused. Folder membership alone never grants anything outside
    #   the folder: the document's library check runs first.
    # - Cross-department attempts are answered as "not found", same as
    #   departments above. A member refused inside a folder they belong
    #   to gets a plain forbidden: the folder is already known to them.
    # - The default folder has no row: it is the library itself. Moving
    #   into it clears folder_id; listing never includes it.
    # - Deletion mirrors remove_department: members or live documents
    #   refuse it, and an empty folder's retrieval collection is
    #   deleted with it. The collection drop runs before the row
    #   delete, so a failed drop refuses the deletion with nothing
    #   changed; the reverse residue (row restored, collection gone)
    #   self-heals on the next reconcile, and the folder is empty, so
    #   no document is affected.

    def _require_department_folder(
        self, dept_id: str, folder_id: str, request_id: str, *, target: str
    ) -> Folder:
        """A folder that exists inside this department's library.

        Folders live only in department libraries in S2; a folder from
        any other library (including a future project library) is
        answered as not found through this path, never leaked.
        """
        self._require_department_library(dept_id, request_id)
        folder = self._store.get_folder(folder_id)
        if folder is None or folder.library_id != dept_id:
            raise not_found(request_id)
        return folder

    def _folder_role_of(
        self, user_id: str, folder_id: str
    ) -> str | None:
        """The caller's live role inside one folder, or None.

        Reads the hot path (no purge) and applies the expiry boundary
        in Python, like AccessControl: an expired folder member holds
        no role here, and the row itself is purged only by the
        admin-side get_folder_members read.
        """
        now = self._clock.now()
        for member in self._store.get_folder_memberships(user_id):
            if member.folder_id == folder_id and _folder_is_live(member, now):
                return member.folder_role
        return None

    def _require_folder_document_act(
        self, principal: Principal, dept_id: str, folder_id: str,
        request_id: str, *, target: str,
    ) -> None:
        """Gate one side of a folder document act (rename, move).

        Super admins and the department's admins bypass folder roles
        (ADR-018 D2). A live full member passes. A member in another
        role gets forbidden (the folder is already known to them); a
        non-member gets not_found (the folder is not theirs to know).
        The default folder (folder_id None) never reaches this gate:
        it has no members and no role to check.
        """
        if principal.role == "admin":
            return
        if self._access.is_department_admin(principal, dept_id):
            return
        role = self._folder_role_of(principal.user_id, folder_id)
        if role is None:
            self._deny(
                principal, request_id, dept_id=dept_id, target=target,
                error=not_found(request_id),
            )
        if role != "full":
            self._deny(
                principal, request_id, dept_id=dept_id, target=target,
                error=forbidden(request_id),
            )

    def create_folder(
        self, principal: Principal, dept_id: str, folder_id: str, name: str,
        request_id: str,
    ) -> tuple[Folder, bool]:
        self._require_department_scope(
            principal, dept_id, request_id, target=folder_id
        )
        self._require_department_library(dept_id, request_id)
        if not _DEPT_ID_PATTERN.match(folder_id):
            raise ValueError("folder_id must match [a-z0-9][a-z0-9_-]{0,127}")
        if folder_id in _SYSTEM_LIBRARY_IDS:
            raise ValueError("folder_id collides with a system library id")
        if not name or len(name) > 255:
            raise ValueError("folder name must be 1-255 characters")
        # Folder ids share the retrieval key namespace with library
        # ids: a folder id equal to a library id would make the
        # library and folder collections indistinguishable at
        # selection time, so the collision is refused at creation.
        if self._store.get_library(folder_id) is not None:
            raise ValueError("folder_id collides with a library id")
        existing = self._store.get_folder(folder_id)
        if existing is not None:
            if existing.library_id == dept_id:
                return existing, False
            raise resource_forbidden(request_id)
        folder = Folder(
            id=folder_id,
            library_id=dept_id,
            name=name,
            created_at=self._clock.now(),
        )
        with self._atomic():
            self._store.create_folder(folder)
            self._record_or_rollback(
                rollback=lambda: self._store.delete_folder(folder_id),
                record_kwargs={
                    "actor": principal.user_id,
                    "action": "authz.folder.created",
                    "target": folder_id,
                    "result": "ok",
                    "request_id": request_id,
                    "metadata": {
                        "dept_id": dept_id,
                        "folder_id": folder_id,
                        "name": name,
                    },
                },
            )
        return folder, True

    def delete_folder(
        self, principal: Principal, dept_id: str, folder_id: str,
        request_id: str,
    ) -> None:
        self._require_department_scope(
            principal, dept_id, request_id, target=folder_id
        )
        folder = self._require_department_folder(
            dept_id, folder_id, request_id, target=folder_id
        )
        members = self._store.get_folder_members(folder_id)
        live_docs = tuple(
            document
            for document in self._documents.list_active()
            if document.folder_id == folder_id and document.deleted_at is None
        )
        if members or live_docs:
            raise resource_forbidden(request_id)
        with self._atomic():
            # Collection first: a failed drop refuses the deletion with
            # nothing changed, and the folder is empty, so the reverse
            # residue (row restored, collection gone) affects no
            # document and heals on the next reconcile.
            if self._folder_collection_drop is not None:
                self._folder_collection_drop(dept_id, folder_id)
            self._store.delete_folder(folder_id)
            self._record_or_rollback(
                rollback=lambda: self._store.create_folder(folder),
                record_kwargs={
                    "actor": principal.user_id,
                    "action": "authz.folder.deleted",
                    "target": folder_id,
                    "result": "ok",
                    "request_id": request_id,
                    "metadata": {
                        "dept_id": dept_id,
                        "folder_id": folder_id,
                        "document_count": len(live_docs),
                        "member_count": len(members),
                    },
                },
            )

    def list_folders(
        self, principal: Principal, dept_id: str, request_id: str
    ) -> tuple[Folder, ...]:
        if principal.role == "admin":
            self._require_department_library(dept_id, request_id)
            return self._store.list_folders(dept_id)
        if self._access.is_department_admin(principal, dept_id):
            self._require_department_library(dept_id, request_id)
            return self._store.list_folders(dept_id)
        # A plain member sees only their own folders, and only inside a
        # department they still belong to: folder membership in a
        # department the caller left grants nothing (visible_folder_ids
        # intersects libraries the same way).
        if dept_id not in self._access.visible_libraries(principal):
            self._deny(
                principal, request_id, dept_id=dept_id, target=dept_id,
                error=not_found(request_id),
            )
        self._require_department_library(dept_id, request_id)
        visible = self._access.visible_folder_ids(principal)
        return tuple(
            folder
            for folder in self._store.list_folders(dept_id)
            if folder.id in visible
        )

    def get_folder(
        self, principal: Principal, dept_id: str, folder_id: str,
        request_id: str,
    ) -> Folder:
        if principal.role == "admin":
            return self._require_department_folder(
                dept_id, folder_id, request_id, target=folder_id
            )
        if self._access.is_department_admin(principal, dept_id):
            return self._require_department_folder(
                dept_id, folder_id, request_id, target=folder_id
            )
        if dept_id not in self._access.visible_libraries(principal):
            self._deny(
                principal, request_id, dept_id=dept_id, target=folder_id,
                error=not_found(request_id),
            )
        folder = self._require_department_folder(
            dept_id, folder_id, request_id, target=folder_id
        )
        if folder.id not in self._access.visible_folder_ids(principal):
            raise not_found(request_id)
        return folder

    def rename_folder(
        self, principal: Principal, dept_id: str, folder_id: str, name: str,
        request_id: str,
    ) -> Folder:
        if not name or len(name) > 255:
            raise ValueError("folder name must be 1-255 characters")
        folder = self._require_department_folder(
            dept_id, folder_id, request_id, target=folder_id
        )
        self._require_folder_document_act(
            principal, dept_id, folder_id, request_id, target=folder_id
        )
        renamed = replace(folder, name=name)
        with self._atomic():
            self._store.set_folder(renamed)
            self._record_or_rollback(
                rollback=lambda: self._store.set_folder(folder),
                record_kwargs={
                    "actor": principal.user_id,
                    "action": "authz.folder.renamed",
                    "target": folder_id,
                    "result": "ok",
                    "request_id": request_id,
                    "metadata": {
                        "dept_id": dept_id,
                        "folder_id": folder_id,
                        "name": name,
                    },
                },
            )
        return renamed

    # -- folder members ---------------------------------------------------

    def list_folder_members(
        self, principal: Principal, dept_id: str, folder_id: str,
        request_id: str,
    ) -> tuple[FolderMembership, ...]:
        """Members of one folder, for its managers only.

        The member list reveals who else may read the folder, so folder
        members themselves do not get it: only super admins and the
        department's admins, who manage the list.
        """
        if principal.role != "admin":
            if not self._access.admin_departments(principal):
                self._deny(
                    principal, request_id, dept_id=dept_id, target=folder_id,
                    error=forbidden(request_id),
                )
            self._require_department_scope(
                principal, dept_id, request_id, target=folder_id
            )
        self._require_department_folder(
            dept_id, folder_id, request_id, target=folder_id
        )
        return self._store.get_folder_members(folder_id)

    def add_folder_member(
        self, principal: Principal, dept_id: str, folder_id: str,
        user_id: str, folder_role: str, request_id: str,
        *, expires_at: datetime | None = None,
    ) -> tuple[FolderMembership, bool]:
        """Add a user to a folder, or return the existing row.

        Folder members come only from the department's live members:
        a user from another department (or a former member) cannot be
        added, so folder visibility never escapes the department. All
        three folder roles are assignable by department admins; full
        excludes member management, but a department admin assigning
        it is not a member-management act by the assignee.
        """
        if folder_role not in _FOLDER_ROLES:
            raise ValueError("folder_role must be full, editor, or reader")
        if principal.role != "admin":
            if not self._access.admin_departments(principal):
                self._deny(
                    principal, request_id, dept_id=dept_id, target=user_id,
                    error=forbidden(request_id),
                )
            self._require_department_scope(
                principal, dept_id, request_id, target=user_id
            )
        self._require_department_folder(
            dept_id, folder_id, request_id, target=user_id
        )
        if self._users.get_by_id(user_id) is None:
            raise not_found(request_id)
        dept_member_ids = {
            member.user_id
            for member in self._store.get_department_members(dept_id)
        }
        if user_id not in dept_member_ids:
            self._deny(
                principal, request_id, dept_id=dept_id, target=user_id,
                error=forbidden(request_id),
            )
        for member in self._store.get_folder_members(folder_id):
            if member.user_id == user_id:
                return member, False
        _check_grant_expiry(
            _grantor_kind(principal), expires_at, self._clock.now()
        )
        member = FolderMembership(
            folder_id=folder_id,
            user_id=user_id,
            folder_role=folder_role,
            granted_by=principal.user_id,
            granted_at=self._clock.now(),
            expires_at=expires_at,
        )
        with self._atomic():
            self._store.add_folder_member(member)
            self._record_or_rollback(
                rollback=lambda: self._store.remove_folder_member(
                    folder_id, user_id
                ),
                record_kwargs={
                    "actor": principal.user_id,
                    "action": "authz.folder.member_added",
                    "target": user_id,
                    "result": "ok",
                    "request_id": request_id,
                    "metadata": {
                        "dept_id": dept_id,
                        "folder_id": folder_id,
                        "folder_role": folder_role,
                        "granted_by": principal.user_id,
                        "expires_at": _iso(expires_at),
                    },
                },
            )
        return member, True

    def remove_folder_member(
        self, principal: Principal, dept_id: str, folder_id: str,
        user_id: str, request_id: str,
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
        self._require_department_folder(
            dept_id, folder_id, request_id, target=user_id
        )
        current = next(
            (
                member
                for member in self._store.get_folder_members(folder_id)
                if member.user_id == user_id
            ),
            None,
        )
        if current is None:
            raise not_found(request_id)
        with self._atomic():
            self._store.remove_folder_member(folder_id, user_id)
            self._record_or_rollback(
                rollback=lambda: self._store.add_folder_member(current),
                record_kwargs={
                    "actor": principal.user_id,
                    "action": "authz.folder.member_removed",
                    "target": user_id,
                    "result": "ok",
                    "request_id": request_id,
                    "metadata": {
                        "dept_id": dept_id,
                        "folder_id": folder_id,
                        "removed_role": current.folder_role,
                    },
                },
            )

    def set_folder_member_role(
        self, principal: Principal, dept_id: str, folder_id: str,
        user_id: str, folder_role: str, request_id: str,
        *, expires_at: datetime | None | _UnsetType = _UNSET,
    ) -> FolderMembership:
        """Change a folder member's role and optionally its expiry.

        Same tri-state expiry rule as set_member_role (ADR-017 D2):
        omitted keeps the stored value, explicit None clears it to a
        long-term grant, and an extension before expiry writes its own
        renewal audit event. An expired row is already purged by the
        folder-member read above, so it cannot be renewed, only
        re-granted through add_folder_member.
        """
        if folder_role not in _FOLDER_ROLES:
            raise ValueError("folder_role must be full, editor, or reader")
        if principal.role != "admin":
            if not self._access.admin_departments(principal):
                self._deny(
                    principal, request_id, dept_id=dept_id, target=user_id,
                    error=forbidden(request_id),
                )
            self._require_department_scope(
                principal, dept_id, request_id, target=user_id
            )
        self._require_department_folder(
            dept_id, folder_id, request_id, target=user_id
        )
        current = next(
            (
                member
                for member in self._store.get_folder_members(folder_id)
                if member.user_id == user_id
            ),
            None,
        )
        if current is None:
            raise not_found(request_id)
        explicit = not isinstance(expires_at, _UnsetType)
        new_expires = current.expires_at if not explicit else expires_at
        if explicit:
            _check_grant_expiry(
                _grantor_kind(principal), new_expires, self._clock.now()
            )
        updated = FolderMembership(
            folder_id=folder_id,
            user_id=user_id,
            folder_role=folder_role,
            granted_by=principal.user_id,
            granted_at=self._clock.now(),
            expires_at=new_expires,
        )
        records = [
            {
                "actor": principal.user_id,
                "action": "authz.folder.member_role_changed",
                "target": user_id,
                "result": "ok",
                "request_id": request_id,
                "metadata": {
                    "dept_id": dept_id,
                    "folder_id": folder_id,
                    "old_role": current.folder_role,
                    "new_role": folder_role,
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
                    "action": "authz.folder.member_renewed",
                    "target": user_id,
                    "result": "ok",
                    "request_id": request_id,
                    "metadata": {
                        "dept_id": dept_id,
                        "folder_id": folder_id,
                        "old_expires_at": _iso(current.expires_at),
                        "new_expires_at": _iso(new_expires),
                    },
                }
            )
        with self._atomic():
            self._store.set_folder_member(updated)
            self._record_all_or_rollback(
                rollback=lambda: self._store.set_folder_member(current),
                records=records,
            )
        return updated

    # -- folder documents ---------------------------------------------------

    def move_document_to_folder(
        self, principal: Principal, dept_id: str, document_id: str,
        folder_id: str | None, request_id: str,
    ) -> tuple[DocumentRecord, bool]:
        """Move a document into a folder, or into the default folder.

        folder_id None means the default folder (the library itself):
        the move clears folder_id. Returns (document, moved): a move
        to the folder the document already sits in is a no-op, but
        only after the permission checks, so probing a document's
        current folder through a no-op answer is impossible.
        Permission is checked on both sides: the source folder needs
        its full member (or a department admin), and so does the
        target folder. The default folder has no members, so moving
        out of it is gated by the target side alone, and moving into
        it by the source side alone: that is what lets a full member
        add documents to their own folder from the default folder.
        The retrieval reconcile after a successful move is the
        router's job, reusing the claim-sync dispatch (ADR-017 D3):
        until it runs, retrieval may lag, but never over-serves,
        because the authorization hook rechecks live folder facts.
        """
        document = self._documents.get(document_id)
        if document is None or document.deleted_at is not None:
            raise not_found(request_id)
        if document.library_id != dept_id:
            if principal.role == "admin":
                raise resource_forbidden(request_id)
            raise not_found(request_id)
        self._require_department_library(dept_id, request_id)
        if folder_id is not None:
            self._require_department_folder(
                dept_id, folder_id, request_id, target=document_id
            )
        if document.folder_id is not None:
            self._require_folder_document_act(
                principal, dept_id, document.folder_id,
                request_id, target=document_id,
            )
        if folder_id is not None:
            self._require_folder_document_act(
                principal, dept_id, folder_id,
                request_id, target=document_id,
            )
        if document.folder_id == folder_id:
            return document, False
        moved = replace(document, folder_id=folder_id)
        records = []
        if document.folder_id is not None:
            records.append(
                {
                    "actor": principal.user_id,
                    "action": "authz.folder.document_removed",
                    "target": document_id,
                    "result": "ok",
                    "request_id": request_id,
                    "metadata": {
                        "dept_id": dept_id,
                        "folder_id": document.folder_id,
                        "from_folder": document.folder_id,
                        "to_folder": folder_id,
                    },
                }
            )
        if folder_id is not None:
            records.append(
                {
                    "actor": principal.user_id,
                    "action": "authz.folder.document_added",
                    "target": document_id,
                    "result": "ok",
                    "request_id": request_id,
                    "metadata": {
                        "dept_id": dept_id,
                        "folder_id": folder_id,
                        "from_folder": document.folder_id,
                        "to_folder": folder_id,
                    },
                }
            )
        with self._atomic():
            self._documents.save(moved)
            self._record_all_or_rollback(
                rollback=lambda: self._documents.save(document),
                records=records,
            )
        return moved, True
