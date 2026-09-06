from __future__ import annotations

import pytest
from pivot.exports.content import sanitize_filename
from pivot.exports.errors import ExportError


def test_FR_EXPORT_003_expired_export_cannot_be_downloaded(harness):
    created = harness.service.create(
        harness.alice,
        source_type="conversation",
        source_id="conv_alice",
        fmt="markdown",
        request_id="req_exp",
    )
    harness.clock.advance(3601)
    status = harness.service.get(harness.alice, created["export_id"], "req_expired_get")
    assert status["state"] == "expired"
    assert status["download_url"] is None
    with pytest.raises(ExportError) as error:
        harness.service.download(harness.alice, created["export_id"], "req_expired_dl")
    assert error.value.code == "EXPORT_EXPIRED"
    assert error.value.retryable is False


def test_FR_EXPORT_003_filename_is_sanitized():
    dirty = sanitize_filename("..\\..\\etc/passwd", "markdown")
    assert ".." not in dirty
    assert "/" not in dirty
    assert "\\" not in dirty
    assert dirty.endswith(".md")
    injected = sanitize_filename('report.md"; DROP TABLE', "docx")
    assert '"' not in injected
    assert ";" not in injected
    assert injected.endswith(".docx")


def test_FR_EXPORT_003_create_download_failed_expired_are_audited(harness):
    harness.answers.answers.pop("conv_alice", None)
    failed = harness.service.create(
        harness.alice,
        source_type="conversation",
        source_id="conv_alice",
        fmt="markdown",
        request_id="req_fail_audit",
    )
    from fakes import sample_answer

    harness.answers.add_answer(sample_answer(title="../../../etc/passwd"))
    created = harness.service.create(
        harness.alice,
        source_type="conversation",
        source_id="conv_alice",
        fmt="markdown",
        request_id="req_create_audit",
    )
    body, filename, _ = harness.service.download(
        harness.alice, created["export_id"], "req_dl_audit"
    )
    assert ".." not in filename
    assert "/" not in filename
    assert "passwd" in filename or filename.endswith(".md")
    assert b"SYSTEM_PROMPT" not in body
    harness.clock.advance(3601)
    harness.service.get(harness.alice, created["export_id"], "req_expire_audit")
    actions = [event.action for event in harness.audits.events()]
    assert "export.create" in actions
    assert "export.download" in actions
    assert "export.failed" in actions
    assert "export.expired" in actions
    assert failed["state"] == "requested"


def test_FR_EXPORT_003_get_and_download_reauthorize_owner(harness):
    created = harness.service.create(
        harness.alice,
        source_type="conversation",
        source_id="conv_alice",
        fmt="markdown",
        request_id="req_reauth",
    )
    harness.access.calls.clear()
    harness.service.get(harness.alice, created["export_id"], "req_get_reauth")
    harness.service.download(harness.alice, created["export_id"], "req_dl_reauth")
    export_calls = [call for call in harness.access.calls if call[0] == "export"]
    assert len(export_calls) >= 2
    with pytest.raises(ExportError):
        harness.service.download(harness.bob, created["export_id"], "req_bob_dl")
