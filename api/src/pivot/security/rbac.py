"""Server-side RBAC and per-resource authorization (FR-RBAC-001~004)."""

from __future__ import annotations

from pivot.auth.errors import not_found, resource_forbidden
from pivot.auth.ports import Principal, ResourceCatalog


class AccessControl:
    def __init__(self, catalog: ResourceCatalog) -> None:
        self._catalog = catalog

    def require_admin(self, principal: Principal) -> bool:
        return principal.role == "admin"

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
        if principal.role == "admin" and action == "manage":
            return
        if document.shared_visible:
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
        if principal.role == "admin":
            raise resource_forbidden(request_id)
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
