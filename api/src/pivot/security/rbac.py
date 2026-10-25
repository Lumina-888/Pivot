"""Server-side RBAC and per-resource authorization (FR-RBAC-001~004)."""

from __future__ import annotations

from datetime import datetime, timezone

from pivot.auth.errors import not_found, resource_forbidden
from pivot.auth.ports import Clock, Membership, Principal, ResourceCatalog
from pivot.shared.time import utc_now


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_live(membership: Membership, now: datetime) -> bool:
    """True when a membership has not expired (ADR-017 D2).

    NULL expires_at means a long-term grant. An expiry timestamp is
    exclusive: at expires_at itself the membership is already gone, so
    one second before the deadline is visible and at the deadline it is
    not. Naive stored timestamps (SQLite) read as UTC.
    """
    if membership.expires_at is None:
        return True
    return _as_utc(membership.expires_at) > now


class AccessControl:
    def __init__(
        self, catalog: ResourceCatalog, clock: Clock | None = None
    ) -> None:
        self._catalog = catalog
        self._clock = clock

    def _now(self) -> datetime:
        if self._clock is not None:
            return _as_utc(self._clock.now())
        return utc_now()

    def require_admin(self, principal: Principal) -> bool:
        return principal.role == "admin"

    def visible_libraries(self, principal: Principal) -> frozenset[str]:
        """Libraries a principal may see (ADR-016 D2-D3, ADR-017 D2).

        Every user sees the public library plus their own department
        libraries (union, never intersection). Expired memberships are
        excluded at read time, so expiry takes effect on the next
        request with no sweeper. Super admins see every library the
        catalog knows, plus the two fixed system libraries (pub and
        unassigned, seeded by S1), so they can always find and claim
        unassigned documents.
        """
        if principal.role == "admin":
            known = {library.id for library in self._catalog.list_libraries()}
            return frozenset({"pub", "unassigned"} | known)
        now = self._now()
        dept_ids = {
            membership.dept_id
            for membership in self._catalog.get_memberships(principal.user_id)
            if _is_live(membership, now)
        }
        return frozenset({"pub"} | dept_ids)

    def is_department_admin(self, principal: Principal, dept_id: str) -> bool:
        """True when the principal administers this department (ADR-016 D3).

        Super admins are not department admins: they use the global path,
        so this stays False for them and callers check the global role
        separately. The check is the (user, department) pair, never a
        bare "is admin" flag, so admin status cannot leak across departments.
        """
        return dept_id in self.admin_departments(principal)

    def admin_departments(self, principal: Principal) -> frozenset[str]:
        """Departments the principal administers as dept_admin.

        Read live from the catalog on every call, so appointment and
        removal take effect on the next request without any token action.
        Expired dept_admin memberships are excluded at read time, so an
        expired department admin loses scope on the next request.
        """
        if principal.role == "admin":
            return frozenset()
        now = self._now()
        return frozenset(
            membership.dept_id
            for membership in self._catalog.get_memberships(principal.user_id)
            if membership.dept_role == "dept_admin"
            and _is_live(membership, now)
        )

    def authorize_conversation(
        self, principal: Principal, conversation_id: str, request_id: str
    ) -> None:
        owner_id = self._catalog.get_conversation_owner(conversation_id)
        if owner_id is None:
            raise not_found(request_id)
        if owner_id == principal.user_id:
            return
        if principal.role == "admin":
            raise resource_forbidden(request_id)
        raise not_found(request_id)

    def ensure_conversation_owner(
        self, principal: Principal, conversation_id: str, request_id: str
    ) -> None:
        claim = getattr(self._catalog, "claim_conversation", None)
        if callable(claim):
            owner = claim(conversation_id, principal.user_id)
            if owner == principal.user_id:
                return
        self.authorize_conversation(principal, conversation_id, request_id)

    def authorize_document(
        self,
        principal: Principal,
        document_id: str,
        request_id: str,
        action: str = "read",
    ) -> None:
        document = self._catalog.get_document(document_id)
        if document is None or document.deleted:
            raise not_found(request_id)
        # Super admins see every library (ADR-016 D3). Department-internal
        # role enforcement (dept_admin vs editor vs reader) belongs to the
        # admin APIs and publish approval, not to this visibility check.
        if principal.role == "admin":
            return
        if document.library_id in self.visible_libraries(principal):
            return
        raise not_found(request_id)

    def authorize_chunk(self, principal: Principal, chunk_id: str, request_id: str) -> None:
        chunk = self._catalog.get_chunk(chunk_id)
        if chunk is None or not chunk.published:
            raise not_found(request_id)
        self.authorize_document(principal, chunk.document_id, request_id)

    def authorize_citation(self, principal: Principal, citation_id: str, request_id: str) -> None:
        citation = self._catalog.get_citation(citation_id)
        if citation is None:
            raise not_found(request_id)
        self.authorize_document(principal, citation.document_id, request_id)

    def authorize_export(self, principal: Principal, export_id: str, request_id: str) -> None:
        export = self._catalog.get_export(export_id)
        if export is None:
            raise not_found(request_id)
        if export.owner_id == principal.user_id:
            return
        # ADR-012 (ND-GAP-04): admins may access and download exports for
        # operations support; other non-owners still cannot see them.
        if principal.role == "admin":
            return
        raise not_found(request_id)

    def authorize_resource(
        self,
        principal: Principal,
        kind: str,
        identifier: str,
        request_id: str,
        action: str = "read",
    ) -> None:
        if kind == "document":
            self.authorize_document(principal, identifier, request_id, action=action)
        elif kind == "chunk":
            self.authorize_chunk(principal, identifier, request_id)
        elif kind == "citation":
            self.authorize_citation(principal, identifier, request_id)
        elif kind == "export":
            self.authorize_export(principal, identifier, request_id)
        elif kind == "conversation":
            self.authorize_conversation(principal, identifier, request_id)
        else:
            raise not_found(request_id)
