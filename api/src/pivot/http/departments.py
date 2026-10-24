"""HTTP adapter for department administration. No business logic lives here."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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


class SetRoleBody(BaseModel):
    dept_role: str = Field(pattern=r"^(dept_admin|editor|reader)$")


class ClaimBody(BaseModel):
    library_id: str = Field(min_length=1)


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
            principal, dept_id, body.user_id, body.dept_role, request_id
        )
        return JSONResponse(
            _member_view(member), status_code=201 if created else 200
        )

    @router.patch("/admin/departments/{dept_id}/members/{user_id}")
    def set_member_role(
        dept_id: str, user_id: str, body: SetRoleBody, request: Request
    ) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        member = departments.set_member_role(
            principal, dept_id, user_id, body.dept_role, request_id
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

    return router
