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
    auth: AuthService, departments: DepartmentAdminService
) -> APIRouter:
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
        return {
            "document_id": claimed.id,
            "library_id": claimed.library_id,
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
