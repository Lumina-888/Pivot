from __future__ import annotations

import pytest
from pivot.auth.errors import AuthError


def _principal(auth_service, username="alice", password="correct-password"):
    login = auth_service.login(username, password, request_id="req_login")
    return auth_service.authenticate(login.access_token)


def test_FR_RBAC_003_guessed_secret_document_is_forbidden_or_missing(auth_service):
    principal = _principal(auth_service)
    with pytest.raises(AuthError) as error:
        auth_service.authorize_document(principal, "doc_secret")
    assert error.value.code in {"RESOURCE_FORBIDDEN", "RESOURCE_NOT_FOUND"}


def test_FR_RBAC_003_guessed_unknown_ids_do_not_leak_existence(auth_service):
    principal = _principal(auth_service)
    for kind, identifier in [
        ("document", "doc_unknown"),
        ("chunk", "chk_unknown"),
        ("citation", "cit_unknown"),
        ("export", "exp_unknown"),
    ]:
        with pytest.raises(AuthError) as error:
            auth_service.authorize_resource(principal, kind, identifier)
        assert error.value.code in {"RESOURCE_FORBIDDEN", "RESOURCE_NOT_FOUND"}


def test_FR_RBAC_003_chunk_and_citation_follow_document_authorization(auth_service):
    principal = _principal(auth_service)
    auth_service.authorize_chunk(principal, "chk_shared")
    auth_service.authorize_citation(principal, "cit_shared")
    with pytest.raises(AuthError):
        auth_service.authorize_chunk(principal, "chk_secret")


def test_FR_RBAC_003_export_owner_isolation(auth_service):
    alice = _principal(auth_service, "alice", "correct-password")
    bob = _principal(auth_service, "bob", "bob-password")
    auth_service.authorize_export(alice, "exp_alice")
    with pytest.raises(AuthError) as error:
        auth_service.authorize_export(alice, "exp_bob")
    assert error.value.code in {"RESOURCE_FORBIDDEN", "RESOURCE_NOT_FOUND"}
    auth_service.authorize_export(bob, "exp_bob")


def test_FR_RBAC_003_deleted_document_is_not_authorized(auth_service):
    principal = _principal(auth_service)
    with pytest.raises(AuthError) as error:
        auth_service.authorize_document(principal, "doc_deleted")
    assert error.value.code in {"RESOURCE_FORBIDDEN", "RESOURCE_NOT_FOUND"}
