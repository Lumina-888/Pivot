"""HTTP adapter for department administration. No business logic lives here."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from pivot.auth.departments import DepartmentAdminService
from pivot.auth.errors import invalid_credentials
from pivot.auth.http import resolve_request_id
from pivot.auth.ports import Principal
from pivot.auth.service import AuthService

_DEPT_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,127}$"


class CreateDepartmentBody(BaseModel):
    dept_id: str = Field(pattern=_DEPT_ID_PATTERN)
    name: str = Field(min_length=1, max_length=255)


class AddMemberBody(BaseModel):
    user_id: str = Field(min_length=1)
    dept_role: str = Field(pattern=r"^(dept_admin|editor|reader)$")
    expires_at: datetime | None = None


class SetRoleBody(BaseModel):
    dept_role: str = Field(pattern=r"^(dept_admin|editor|reader)$")
    expires_at: datetime | None = None


class ClaimBody(BaseModel):
    library_id: str = Field(min_length=1)


class CreateFolderBody(BaseModel):
    folder_id: str = Field(pattern=_DEPT_ID_PATTERN)
    name: str = Field(min_length=1, max_length=255)


class RenameFolderBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class AddFolderMemberBody(BaseModel):
    user_id: str = Field(min_length=1)
    folder_role: str = Field(pattern=r"^(full|editor|reader)$")
    expires_at: datetime | None = None


class SetFolderRoleBody(BaseModel):
    folder_role: str = Field(pattern=r"^(full|editor|reader)$")
    expires_at: datetime | None = None


class MoveDocumentBody(BaseModel):
    # None means the default folder (the library itself): the move
    # clears folder_id. An explicit folder id moves into that folder.
    folder_id: str | None = None


class GrantExceptionBody(BaseModel):
    target_user_id: str | None = None
    target_dept_id: str | None = None
    reason: str = ""
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self):
        if (self.target_user_id is None) == (self.target_dept_id is None):
            raise ValueError(
                "exactly one of target_user_id / target_dept_id is required"
            )
        return self


def _bearer_token(request: Request, request_id: str) -> str:
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        raise invalid_credentials(request_id)
    token = header.removeprefix("Bearer ").strip()
    if not token:
        raise invalid_credentials(request_id)
    return token


def _principal(request: Request, auth: AuthService) -> tuple[str, Principal]:
    request_id = resolve_request_id(request)
    principal = auth.authenticate(_bearer_token(request, request_id), request_id)
    return request_id, principal


def _library_view(library) -> dict[str, object]:
    return {
        "library_id": library.id,
        "name": library.name,
        "kind": library.kind,
        "dept_id": library.dept_id,
    }


def _member_view(member) -> dict[str, object]:
    return {
        "user_id": member.user_id,
        "dept_id": member.dept_id,
        "dept_role": member.dept_role,
        "granted_by": member.granted_by,
        "granted_at": member.granted_at.isoformat().replace("+00:00", "Z")
        if member.granted_at is not None
        else None,
        "expires_at": member.expires_at.isoformat().replace("+00:00", "Z")
        if member.expires_at is not None
        else None,
    }


def _folder_view(folder) -> dict[str, object]:
    return {
        "folder_id": folder.id,
        "library_id": folder.library_id,
        "name": folder.name,
        "created_at": folder.created_at.isoformat().replace("+00:00", "Z")
        if folder.created_at is not None
        else None,
    }


def _folder_member_view(member) -> dict[str, object]:
    return {
        "folder_id": member.folder_id,
        "user_id": member.user_id,
        "folder_role": member.folder_role,
        "granted_by": member.granted_by,
        "granted_at": member.granted_at.isoformat().replace("+00:00", "Z")
        if member.granted_at is not None
        else None,
        "expires_at": member.expires_at.isoformat().replace("+00:00", "Z")
        if member.expires_at is not None
        else None,
    }


def _exception_view(exception) -> dict[str, object]:
    return {
        "id": exception.id,
        "document_id": exception.document_id,
        "target_user_id": exception.target_user_id,
        "target_dept_id": exception.target_dept_id,
        "granted_by": exception.granted_by,
        "reason": exception.reason,
        "expires_at": exception.expires_at.isoformat().replace("+00:00", "Z")
        if exception.expires_at is not None
        else None,
        "created_at": exception.created_at.isoformat().replace("+00:00", "Z")
        if exception.created_at is not None
        else None,
    }


def build_departments_router(
    auth: AuthService, departments: DepartmentAdminService, claim_sync=None
) -> APIRouter:
    """Department admin routes. ``claim_sync`` is the post-claim
    reconcile dispatcher (ADR-017 D3): called after a successful claim
    with (document_id, library_id, request_id, actor_id); None means
    there is nothing to reconcile (no llama backend) and the claim
    simply lands without a dispatch. Folder moves (ADR-018 D3) reuse
    the same dispatcher after a move that actually changed the folder.
    """
    router = APIRouter()

    @router.post("/admin/departments")
    def create_department(body: CreateDepartmentBody, request: Request):
        request_id, principal = _principal(request, auth)
        library, created = departments.create_department(
            principal, body.dept_id, body.name, request_id
        )
        return JSONResponse(
            _library_view(library), status_code=201 if created else 200
        )

    @router.get("/admin/departments")
    def list_departments(request: Request) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        items = departments.list_departments(principal, request_id)
        return {
            "items": [_library_view(item) for item in items],
            "pagination": None,
        }

    @router.get("/admin/departments/{dept_id}")
    def get_department(dept_id: str, request: Request) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        return _library_view(departments.get_department(principal, dept_id, request_id))

    @router.delete("/admin/departments/{dept_id}", status_code=204)
    def remove_department(dept_id: str, request: Request) -> JSONResponse:
        request_id, principal = _principal(request, auth)
        departments.remove_department(principal, dept_id, request_id)
        return JSONResponse(None, status_code=204)

    @router.get("/admin/departments/{dept_id}/members")
    def list_members(dept_id: str, request: Request) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        items = departments.list_members(principal, dept_id, request_id)
        return {
            "items": [_member_view(item) for item in items],
            "pagination": None,
        }

    @router.post("/admin/departments/{dept_id}/members")
    def add_member(dept_id: str, body: AddMemberBody, request: Request):
        request_id, principal = _principal(request, auth)
        member, created = departments.add_member(
            principal, dept_id, body.user_id, body.dept_role, request_id,
            expires_at=body.expires_at,
        )
        return JSONResponse(
            _member_view(member), status_code=201 if created else 200
        )

    @router.patch("/admin/departments/{dept_id}/members/{user_id}")
    def set_member_role(
        dept_id: str, user_id: str, body: SetRoleBody, request: Request
    ) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        # PATCH tri-state: an omitted expires_at keeps the stored value,
        # an explicit null clears it to a long-term grant. The service
        # default is keep, so only pass the field when the client sent it.
        kwargs: dict[str, object] = {}
        if "expires_at" in body.model_fields_set:
            kwargs["expires_at"] = body.expires_at
        member = departments.set_member_role(
            principal, dept_id, user_id, body.dept_role, request_id, **kwargs
        )
        return _member_view(member)

    @router.delete(
        "/admin/departments/{dept_id}/members/{user_id}", status_code=204
    )
    def remove_member(dept_id: str, user_id: str, request: Request) -> JSONResponse:
        request_id, principal = _principal(request, auth)
        departments.remove_member(principal, dept_id, user_id, request_id)
        return JSONResponse(None, status_code=204)

    @router.post("/admin/documents/{document_id}/claim")
    def claim_document(
        document_id: str, body: ClaimBody, request: Request
    ) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        claimed = departments.claim_document(
            principal, document_id, body.library_id, request_id
        )
        if claim_sync is not None:
            claim_sync(claimed.id, claimed.library_id, request_id, principal.user_id)
        return {
            "document_id": claimed.id,
            "library_id": claimed.library_id,
        }

    # -- folders (ADR-018 D3) ------------------------------------------
    #
    # Folder management is a department admin act; folder documents
    # (rename, move) are a full-member act, with department admins
    # bypassing folder roles. The move endpoint reuses the claim-sync
    # dispatcher: a successful move reconciles the document into its
    # new collection, exactly like a claim, and a no-op move (same
    # folder) dispatches nothing.

    @router.post("/admin/departments/{dept_id}/folders")
    def create_folder(dept_id: str, body: CreateFolderBody, request: Request):
        request_id, principal = _principal(request, auth)
        folder, created = departments.create_folder(
            principal, dept_id, body.folder_id, body.name, request_id
        )
        return JSONResponse(
            _folder_view(folder), status_code=201 if created else 200
        )

    @router.get("/admin/departments/{dept_id}/folders")
    def list_folders(dept_id: str, request: Request) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        items = departments.list_folders(principal, dept_id, request_id)
        return {
            "items": [_folder_view(item) for item in items],
            "pagination": None,
        }

    @router.get("/admin/departments/{dept_id}/folders/{folder_id}")
    def get_folder(dept_id: str, folder_id: str, request: Request) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        return _folder_view(
            departments.get_folder(principal, dept_id, folder_id, request_id)
        )

    @router.patch("/admin/departments/{dept_id}/folders/{folder_id}")
    def rename_folder(
        dept_id: str, folder_id: str, body: RenameFolderBody, request: Request
    ) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        folder = departments.rename_folder(
            principal, dept_id, folder_id, body.name, request_id
        )
        return _folder_view(folder)

    @router.delete(
        "/admin/departments/{dept_id}/folders/{folder_id}", status_code=204
    )
    def delete_folder(
        dept_id: str, folder_id: str, request: Request
    ) -> JSONResponse:
        request_id, principal = _principal(request, auth)
        departments.delete_folder(principal, dept_id, folder_id, request_id)
        return JSONResponse(None, status_code=204)

    @router.get("/admin/departments/{dept_id}/folders/{folder_id}/members")
    def list_folder_members(
        dept_id: str, folder_id: str, request: Request
    ) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        items = departments.list_folder_members(
            principal, dept_id, folder_id, request_id
        )
        return {
            "items": [_folder_member_view(item) for item in items],
            "pagination": None,
        }

    @router.post("/admin/departments/{dept_id}/folders/{folder_id}/members")
    def add_folder_member(
        dept_id: str, folder_id: str, body: AddFolderMemberBody, request: Request
    ):
        request_id, principal = _principal(request, auth)
        member, created = departments.add_folder_member(
            principal, dept_id, folder_id, body.user_id, body.folder_role,
            request_id, expires_at=body.expires_at,
        )
        return JSONResponse(
            _folder_member_view(member), status_code=201 if created else 200
        )

    @router.patch(
        "/admin/departments/{dept_id}/folders/{folder_id}/members/{user_id}"
    )
    def set_folder_member_role(
        dept_id: str, folder_id: str, user_id: str, body: SetFolderRoleBody,
        request: Request,
    ) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        # PATCH tri-state, same as set_member_role: an omitted
        # expires_at keeps the stored value, an explicit null clears it.
        kwargs: dict[str, object] = {}
        if "expires_at" in body.model_fields_set:
            kwargs["expires_at"] = body.expires_at
        member = departments.set_folder_member_role(
            principal, dept_id, folder_id, user_id, body.folder_role,
            request_id, **kwargs,
        )
        return _folder_member_view(member)

    @router.delete(
        "/admin/departments/{dept_id}/folders/{folder_id}/members/{user_id}",
        status_code=204,
    )
    def remove_folder_member(
        dept_id: str, folder_id: str, user_id: str, request: Request
    ) -> JSONResponse:
        request_id, principal = _principal(request, auth)
        departments.remove_folder_member(
            principal, dept_id, folder_id, user_id, request_id
        )
        return JSONResponse(None, status_code=204)

    @router.post("/admin/departments/{dept_id}/documents/{document_id}/folder")
    def move_document_to_folder(
        dept_id: str, document_id: str, body: MoveDocumentBody, request: Request
    ) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        moved, changed = departments.move_document_to_folder(
            principal, dept_id, document_id, body.folder_id, request_id
        )
        if changed and claim_sync is not None:
            # The library is unchanged by a folder move; the dispatcher
            # reconciles by document id against live facts, so it picks
            # up the new folder_id on its own.
            claim_sync(moved.id, dept_id, request_id, principal.user_id)
        return {
            "document_id": moved.id,
            "library_id": moved.library_id,
            "folder_id": moved.folder_id,
            "moved": changed,
        }

    @router.post("/admin/documents/{document_id}/exceptions")
    def grant_exception(
        document_id: str, body: GrantExceptionBody, request: Request
    ):
        request_id, principal = _principal(request, auth)
        exception, created = departments.grant_exception(
            principal, document_id, request_id,
            target_user_id=body.target_user_id,
            target_dept_id=body.target_dept_id,
            reason=body.reason,
            expires_at=body.expires_at,
        )
        return JSONResponse(
            _exception_view(exception), status_code=201 if created else 200
        )

    @router.get("/admin/documents/{document_id}/exceptions")
    def list_exceptions(
        document_id: str, request: Request, permanent_only: bool = False
    ) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        rows = departments.list_exceptions(
            principal, document_id, request_id,
            permanent_only=permanent_only,
        )
        return {"items": [_exception_view(row) for row in rows]}

    @router.delete(
        "/admin/documents/{document_id}/exceptions/{exception_id}",
        status_code=204,
    )
    def revoke_exception(
        document_id: str, exception_id: str, request: Request
    ) -> JSONResponse:
        request_id, principal = _principal(request, auth)
        departments.revoke_exception(
            principal, exception_id, request_id, document_id=document_id
        )
        return JSONResponse(None, status_code=204)

    return router
