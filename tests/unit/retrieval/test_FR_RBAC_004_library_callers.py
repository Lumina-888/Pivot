"""Caller wiring for FR-RBAC-004: library scope comes from the Principal.

Neither the search endpoint nor the agent bridge accepts a library scope
from the request or the model. Both derive it server-side from the
authenticated user, so a caller cannot widen its own visibility.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pivot.auth.ports import Principal
from pivot.http.bootstrap import _RetrievalBridge
from pivot.qa.ports import RetrievalResult
from pivot.retrieval.http import build_search_router
from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.service import RetrievalOutcome


class _StubAuth:
    def __init__(self, visible: frozenset[str]) -> None:
        self._visible = visible

    def authenticate(self, token: str, request_id: str) -> Principal:
        assert token == "token_alice"
        return Principal(
            user_id="usr_alice", username="alice", role="user", token_version=1
        )

    def visible_libraries(self, principal: Principal) -> frozenset[str]:
        assert principal.user_id == "usr_alice"
        return self._visible


class _StubSearchService:
    def __init__(self) -> None:
        self.seen: RetrievalQuery | None = None

    def search_documents(self, query: RetrievalQuery, limit=None):
        self.seen = query
        return ()


class _StubRetrievalService:
    def __init__(self) -> None:
        self.seen: RetrievalQuery | None = None

    def retrieve(self, query: RetrievalQuery) -> RetrievalOutcome:
        self.seen = query
        return RetrievalOutcome(status="empty", evidence=(), warnings=())


def test_FR_RBAC_004_search_endpoint_derives_libraries_from_principal():
    service = _StubSearchService()
    auth = _StubAuth(frozenset({"pub", "dept_eng"}))
    app = FastAPI()
    app.include_router(build_search_router(service, auth), prefix="/api/v1")
    client = TestClient(app)
    response = client.get(
        "/api/v1/search", params={"q": "手册"}, headers={"Authorization": "Bearer token_alice"}
    )
    assert response.status_code == 200
    assert service.seen is not None
    assert service.seen.library_ids == ("dept_eng", "pub")


def test_FR_RBAC_004_agent_bridge_derives_libraries_from_resolver():
    service = _StubRetrievalService()
    bridge = _RetrievalBridge(
        service, None, library_ids_for=lambda user_id: ("pub", "dept_eng")
    )
    result = bridge.retrieve(
        "手册",
        scope_type="global",
        scope_document_id=None,
        principal_id="usr_alice",
    )
    assert isinstance(result, RetrievalResult)
    assert service.seen is not None
    assert service.seen.library_ids == ("pub", "dept_eng")


def test_FR_RBAC_004_agent_bridge_without_resolver_keeps_legacy_query():
    service = _StubRetrievalService()
    bridge = _RetrievalBridge(service, None)
    bridge.retrieve(
        "手册",
        scope_type="global",
        scope_document_id=None,
        principal_id="usr_alice",
    )
    assert service.seen is not None
    assert service.seen.library_ids is None
