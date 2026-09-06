from __future__ import annotations

import pytest
from fakes import (
    FakeClock,
    InMemoryAttempts,
    InMemoryAudit,
    InMemoryRefreshStore,
    InMemoryResources,
    InMemoryUserDirectory,
    TestPasswordHasher,
)
from pivot.auth.service import AuthService
from pivot.auth.tokens import TokenService
from pivot.security.rbac import AccessControl


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def hasher() -> TestPasswordHasher:
    return TestPasswordHasher()


@pytest.fixture
def users(hasher: TestPasswordHasher) -> InMemoryUserDirectory:
    from pivot.auth.ports import UserAccount

    return InMemoryUserDirectory(
        [
            UserAccount(
                id="usr_alice",
                username="alice",
                password_hash=hasher.hash("correct-password"),
                role="user",
                status="active",
                token_version=1,
            ),
            UserAccount(
                id="usr_admin",
                username="admin",
                password_hash=hasher.hash("admin-password"),
                role="admin",
                status="active",
                token_version=1,
            ),
            UserAccount(
                id="usr_bob",
                username="bob",
                password_hash=hasher.hash("bob-password"),
                role="user",
                status="active",
                token_version=1,
            ),
            UserAccount(
                id="usr_disabled",
                username="disabled",
                password_hash=hasher.hash("disabled-password"),
                role="user",
                status="disabled",
                token_version=4,
            ),
        ]
    )


@pytest.fixture
def audits() -> InMemoryAudit:
    return InMemoryAudit()


@pytest.fixture
def attempts() -> InMemoryAttempts:
    return InMemoryAttempts()


@pytest.fixture
def refresh_store() -> InMemoryRefreshStore:
    return InMemoryRefreshStore()


@pytest.fixture
def resources() -> InMemoryResources:
    from pivot.auth.ports import ChunkAuthz, CitationAuthz, DocumentAuthz, ExportAuthz

    catalog = InMemoryResources()
    catalog.documents["doc_shared"] = DocumentAuthz(
        id="doc_shared",
        deleted=False,
        shared_visible=True,
        export_allowed=True,
        owner_id="usr_admin",
    )
    catalog.documents["doc_secret"] = DocumentAuthz(
        id="doc_secret",
        deleted=False,
        shared_visible=False,
        export_allowed=False,
        owner_id="usr_admin",
    )
    catalog.documents["doc_deleted"] = DocumentAuthz(
        id="doc_deleted",
        deleted=True,
        shared_visible=True,
        export_allowed=True,
        owner_id="usr_admin",
    )
    catalog.chunks["chk_shared"] = ChunkAuthz(
        id="chk_shared", document_id="doc_shared", published=True
    )
    catalog.chunks["chk_secret"] = ChunkAuthz(
        id="chk_secret", document_id="doc_secret", published=True
    )
    catalog.citations["cit_shared"] = CitationAuthz(
        id="cit_shared", document_id="doc_shared", chunk_id="chk_shared"
    )
    catalog.exports["exp_alice"] = ExportAuthz(id="exp_alice", owner_id="usr_alice")
    catalog.exports["exp_bob"] = ExportAuthz(id="exp_bob", owner_id="usr_bob")
    catalog.conversations["conv_alice"] = "usr_alice"
    catalog.conversations["conv_bob"] = "usr_bob"
    return catalog


@pytest.fixture
def auth_service(
    users: InMemoryUserDirectory,
    hasher: TestPasswordHasher,
    clock: FakeClock,
    refresh_store: InMemoryRefreshStore,
    audits: InMemoryAudit,
    attempts: InMemoryAttempts,
    resources: InMemoryResources,
) -> AuthService:
    tokens = TokenService(secret="unit-test-secret", access_ttl=60, clock=clock)
    access = AccessControl(resources)
    return AuthService(
        users=users,
        hasher=hasher,
        tokens=tokens,
        refresh_tokens=refresh_store,
        audits=audits,
        attempts=attempts,
        access=access,
        clock=clock,
        access_ttl=60,
        refresh_ttl=3600,
    )
