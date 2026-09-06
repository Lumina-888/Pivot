from __future__ import annotations

from pivot.audit.provider import ProviderCallRecorder


def test_FR_AUDIT_003_replay_by_request_id_and_run_id(audit_service, admin):
    audit_service.record_qa(
        actor="usr_alice",
        request_id="req_qa_1",
        run_id="run_qa_1",
        state="answered",
        hit_documents=("doc_shared",),
        citations=("cit_1",),
        model="fake-llm-v1",
        prompt_version="prompt-v3",
        role_card_version="role-hr-v1",
        retrieval_params={"k": 8, "prompt": "should-redact"},
        index_generation="gen_9",
        retry_count=1,
        duration_ms=842,
    )
    by_request = audit_service.replay(admin, "req_replay", replay_request_id="req_qa_1")
    by_run = audit_service.replay(admin, "req_replay_run", run_id="run_qa_1")
    for replayed in (by_request, by_run):
        assert replayed["request_id"] == "req_qa_1"
        assert replayed["run_id"] == "run_qa_1"
        assert replayed["actor"] == "usr_alice"
        assert replayed["state"] == "answered"
        assert replayed["hit_documents"] == ["doc_shared"]
        assert replayed["citations"] == ["cit_1"]
        assert replayed["model"] == "fake-llm-v1"
        assert replayed["prompt_version"] == "prompt-v3"
        assert replayed["role_card_version"] == "role-hr-v1"
        assert replayed["index_generation"] == "gen_9"
        assert replayed["retry_count"] == 1
        assert replayed["duration_ms"] == 842
        assert replayed["retrieval_params"]["k"] == 8
        assert replayed["retrieval_params"]["prompt"] == "[REDACTED]"


def test_FR_AUDIT_003_provider_call_omits_sensitive_context():
    recorder = ProviderCallRecorder()
    call = recorder.record(
        provider="fake-vendor",
        model="fake-llm-v1",
        operation="chat",
        status="ok",
        request_id="req_qa_1",
        run_id="run_qa_1",
        tokens=128,
        latency_ms=40,
        retry_count=1,
        estimated_cost=0.002,
        prompt="SYSTEM_PROMPT should not persist",
        messages=[{"role": "system", "content": "hidden"}],
        response="model completion",
    )
    assert call.tokens == 128
    assert call.estimated_cost == 0.002
    assert call.retry_count == 1
    dumped = str(call)
    assert "SYSTEM_PROMPT" not in dumped
    assert "hidden" not in dumped
    assert "model completion" not in dumped
    assert recorder.list_for_run("run_qa_1") == (call,)
