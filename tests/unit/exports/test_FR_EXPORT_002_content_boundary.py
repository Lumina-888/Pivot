from __future__ import annotations

from fakes import PersistedAnswer, sample_answer

FORBIDDEN = (
    "SYSTEM_PROMPT",
    "chain-of-thought",
    "sk-secret-export",
    "tool_parameters",
    "hidden tool args",
)


def _body(harness, source_type="conversation", source_id="conv_alice", fmt="markdown"):
    created = harness.service.create(
        harness.alice,
        source_type=source_type,
        source_id=source_id,
        fmt=fmt,
        request_id="req_body",
    )
    return harness.service.download(harness.alice, created["export_id"], "req_dl")


def test_FR_EXPORT_002_payload_contains_only_persisted_answer_claims_citations(harness):
    data, filename, content_type = _body(harness)
    text = data.decode("utf-8")
    assert "迟到三次书面警告" in text
    assert "员工手册 p.12" in text
    assert "clm_1" in text or "迟到三次书面警告" in text
    assert filename.endswith(".md")
    assert "markdown" in content_type


def test_FR_EXPORT_002_excludes_prompt_and_chain_of_thought(harness):
    data, _, _ = _body(harness)
    text = data.decode("utf-8")
    for snippet in FORBIDDEN:
        assert snippet not in text
    data_docx, filename, content_type = _body(harness, fmt="docx")
    assert filename.endswith(".docx")
    assert "wordprocessingml" in content_type
    decoded = data_docx.decode("utf-8", errors="ignore")
    for snippet in FORBIDDEN:
        assert snippet not in decoded


def test_FR_EXPORT_002_document_source_stays_within_authorized_display_fields(harness):
    data, _, _ = _body(harness, source_type="document", source_id="doc_shared")
    text = data.decode("utf-8")
    assert "迟到累计三次给予书面警告。" in text
    assert "p.12" in text
    for snippet in FORBIDDEN:
        assert snippet not in text


def test_FR_EXPORT_002_missing_persisted_answer_fails_without_qa(harness):
    harness.answers.add_answer(
        PersistedAnswer(
            conversation_id="conv_alice",
            run_id="run_running",
            state="drafting",
            answer_markdown="",
            prompt="SYSTEM_PROMPT: should never export",
        )
    )
    created = harness.service.create(
        harness.alice,
        source_type="conversation",
        source_id="conv_alice",
        fmt="markdown",
        request_id="req_running",
    )
    status = harness.service.get(harness.alice, created["export_id"], "req_failed")
    assert status["state"] == "failed"
    assert status["download_url"] is None
    assert harness.answers.qa_invocations == 0
    actions = {event.action for event in harness.audits.events()}
    assert "export.failed" in actions
    # Keep the original sample for other tests in this module if fixture is reused.
    harness.answers.add_answer(sample_answer())
