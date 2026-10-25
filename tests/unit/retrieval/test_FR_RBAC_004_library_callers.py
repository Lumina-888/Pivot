"""Caller wiring for FR-RBAC-004: library scope comes from the Principal.

Neither the search endpoint nor the agent retriever accepts a library scope
from the request or the model. Both derive it server-side from the
authenticated user, so a caller cannot widen its own visibility.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pivot.auth.ports import Principal
from pivot.retrieval.http import build_search_router
from pivot.retrieval.models import RetrievalQuery


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
