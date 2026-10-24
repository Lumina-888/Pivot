"""Server-side RBAC and per-resource authorization (FR-RBAC-001~004)."""

from __future__ import annotations

from pivot.auth.errors import not_found, resource_forbidden
from pivot.auth.ports import Principal, ResourceCatalog


class AccessControl:
    def __init__(self, catalog: ResourceCatalog) -> None:
        self._catalog = catalog

    def require_admin(self, principal: Principal) -> bool:
        return principal.role == "admin"

    def visible_libraries(self, principal: Principal) -> frozenset[str]:
        """Libraries a principal may see (ADR-016 D2-D3).

        Every user sees the public library plus their own department
        libraries (union, never intersection). Super admins see every
        library the catalog knows, plus the two fixed system libraries
        (pub and unassigned, seeded by S1), so they can always find and
        claim unassigned documents.
        """
        if principal.role == "admin":
            known = {library.id for library in self._catalog.list_libraries()}
            return frozenset({"pub", "unassigned"} | known)
        dept_ids = {
            membership.dept_id
            for membership in self._catalog.get_memberships(principal.user_id)
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
        """
        if principal.role == "admin":
            return frozenset()
        return frozenset(
            membership.dept_id
            for membership in self._catalog.get_memberships(principal.user_id)
            if membership.dept_role == "dept_admin"
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
