"""Fake in-process domain pipeline. Not HTTP/Compose and not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path

import pytest
from harness import POLICY_TEXT, Pipeline
from pivot.exports.errors import ExportError
from pivot.retrieval.models import RetrievalQuery

_ROOT = Path(__file__).resolve().parents[3]


def test_NFR_OBS_fake_pipeline_auth_ingest_retrieve_qa_export():
    pipeline = Pipeline()
    login = pipeline.login_alice()
    principal = pipeline.auth.authenticate(login.access_token, "req_auth")
    assert principal.username == "alice"

    _version, ready, document, worker_result = pipeline.ingest_policy_pdf(principal.user_id)
    assert worker_result["status"] == "ok"
    assert ready is not None and ready.state == "ready" and ready.current is True
    assert document is not None

    retrieval = pipeline.retrieval_for_ready_chunks()
    hits = retrieval.search_documents(
        RetrievalQuery(text="late three times", principal_id=principal.user_id)
    )
    assert hits
    assert hits[0].document_id == document.id

    bundle = pipeline.ask(
        owner_id=principal.user_id,
        question="late three times written warning?",
        conversation_id="conv_alice",
        retrieval=retrieval,
    )
    assert bundle.run.state == "answered"
    assert POLICY_TEXT.split(".")[0] in (bundle.run.answer_markdown or "")

    created = pipeline.exports.create(
        pipeline.alice_actor(),
        source_type="conversation",
        source_id="conv_alice",
        fmt="markdown",
        request_id="req_export",
    )
    assert created["state"] == "requested"
    status = pipeline.exports.get(pipeline.alice_actor(), created["export_id"], "req_export_get")
    assert status["state"] == "ready"
    assert status["download_url"]
    assert "minio" not in (status["download_url"] or "")
    body, filename, _content_type = pipeline.exports.download(
        pipeline.alice_actor(), created["export_id"], "req_dl"
    )
    text = body.decode("utf-8")
    assert "SYSTEM_PROMPT" not in text
    assert "hidden thinking" not in text
    assert filename.endswith(".md")
    assert pipeline.answers.qa_invocations == 0


def test_FR_EXPORT_001_other_user_cannot_export_foreign_conversation():
    pipeline = Pipeline()
    login = pipeline.login_alice()
    principal = pipeline.auth.authenticate(login.access_token, "req_auth")
    pipeline.ingest_policy_pdf(principal.user_id)
    retrieval = pipeline.retrieval_for_ready_chunks()
    pipeline.ask(
        owner_id=principal.user_id,
        question="late three times",
        conversation_id="conv_alice",
        retrieval=retrieval,
    )
    with pytest.raises(ExportError) as caught:
        pipeline.exports.create(
            pipeline.bob_actor(),
            source_type="conversation",
            source_id="conv_alice",
            fmt="markdown",
            request_id="req_bob",
        )
    assert caught.value.code in {"RESOURCE_NOT_FOUND", "RESOURCE_FORBIDDEN"}


def test_FR_QA_003_unmatched_question_is_refused():
    pipeline = Pipeline()
    login = pipeline.login_alice()
    principal = pipeline.auth.authenticate(login.access_token, "req_auth")
    pipeline.ingest_policy_pdf(principal.user_id)
    retrieval = pipeline.retrieval_for_ready_chunks()
    bundle = pipeline.ask(
        owner_id=principal.user_id,
        question="completely unrelated celestial navigation tables",
        conversation_id="conv_empty",
        retrieval=retrieval,
    )
    assert bundle.run.state in {"refused", "uncertain", "failed"}
    assert bundle.run.state != "answered"


def test_GATE_P0_evidence_file_marks_all_gates_unverified():
    text = (_ROOT / "evidence" / "wave2-m11" / "limits.md").read_text(encoding="utf-8")
    for gate in range(1, 9):
        assert f"GATE-P0-00{gate}" in text
    assert text.lower().count("unverified") >= 8
    for gate in range(1, 9):
        line = next(item for item in text.splitlines() if f"GATE-P0-00{gate}" in item)
        assert "unverified" in line.lower()
        assert "verified" not in line.lower().replace("unverified", "")


def test_NFR_OBS_ci_does_not_start_compose():
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "docker compose" not in workflow.lower()
    assert "docker-compose" not in workflow.lower()
    assert not (_ROOT / "docker-compose.yml").exists()
    intent = (_ROOT / "ops" / "compose-intent.md").read_text(encoding="utf-8")
    assert "未启用" in intent
