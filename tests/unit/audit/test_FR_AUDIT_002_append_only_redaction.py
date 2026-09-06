from __future__ import annotations

import pytest
from pivot.audit.errors import AuditError
from pivot.audit.store import AppendOnlyAuditStore


def test_FR_AUDIT_002_store_has_no_update_or_delete():
    public = set(dir(AppendOnlyAuditStore))
    assert not {"update", "delete", "remove", "pop"}.intersection(public)


def test_FR_AUDIT_002_rejects_duplicate_append(audit_service):
    first = audit_service.record(
        actor="usr_alice",
        action="auth.login",
        target="usr_alice",
        result="ok",
        request_id="req_dup",
    )
    with pytest.raises(AuditError):
        audit_service._store.append(first)


def test_FR_AUDIT_002_redacts_secrets_and_prompts(audit_service):
    event = audit_service.record(
        actor="usr_alice",
        action="qa.run",
        target="run_1",
        result="ok",
        request_id="req_redact",
        run_id="run_1",
        metadata={
            "question": "请说明迟到处理规则以及内部系统口令 abcdefghijklmnop",
            "prompt": "full system prompt text",
            "api_key": "sk-live-should-never-store",
            "token": "Bearer abc.def",
            "snippet": "引用正文应截断 " + ("很长" * 40),
            "retrieval_params": {"k": 8, "system_prompt": "nope"},
        },
    )
    metadata = event.metadata
    assert metadata["prompt"] == "[REDACTED]"
    assert metadata["api_key"] == "[REDACTED]"
    assert metadata["token"] == "[REDACTED]"
    assert "sk-live" not in str(metadata)
    assert "full system prompt" not in str(metadata)
    assert metadata["question"].endswith("…")
    assert "abcdefghijklmnop" not in metadata["question"]
    assert metadata["retrieval_params"]["system_prompt"] == "[REDACTED]"
    assert metadata["retrieval_params"]["k"] == 8


def test_FR_AUDIT_002_non_admin_cannot_list_events(audit_service, user):
    audit_service.record(
        actor="usr_alice",
        action="auth.login",
        target="usr_alice",
        result="ok",
        request_id="req_hidden",
    )
    with pytest.raises(AuditError) as error:
        audit_service.list_events(user, "req_user_list")
    assert error.value.code == "AUTH_FORBIDDEN"
    assert error.value.to_envelope()["request_id"] == "req_user_list"


def test_FR_AUDIT_002_admin_query_is_itself_audited(audit_service, admin):
    audit_service.record(
        actor="usr_alice",
        action="auth.login",
        target="usr_alice",
        result="ok",
        request_id="req_login_row",
    )
    listed = audit_service.list_events(admin, "req_admin_list", filter_action="auth.login")
    listed_actions = {item["action"] for item in listed["items"]}
    assert listed_actions == {"auth.login"}
    debug = [event for event in audit_service.events() if event.action == "admin.debug_access"]
    assert len(debug) == 1
    assert debug[0].metadata["filter_action"] == "auth.login"
    assert "password" not in debug[0].metadata
