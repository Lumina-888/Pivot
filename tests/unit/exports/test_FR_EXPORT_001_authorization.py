from __future__ import annotations

import pytest
from pivot.exports.errors import ExportError
from pivot.exports.signer import contains_internal_storage_host


def test_FR_EXPORT_001_unauthorized_user_cannot_create_export(harness):
    with pytest.raises(ExportError) as error:
        harness.service.create(
            harness.bob,
            source_type="conversation",
            source_id="conv_alice",
            fmt="markdown",
            request_id="req_unauth",
        )
    assert error.value.code in {"RESOURCE_NOT_FOUND", "RESOURCE_FORBIDDEN"}
    assert error.value.to_envelope()["request_id"] == "req_unauth"
    assert harness.answers.qa_invocations == 0
    assert harness.exports.list() == ()


def test_FR_EXPORT_001_guessed_export_id_does_not_bypass_authorization(harness):
    created = harness.service.create(
        harness.alice,
        source_type="conversation",
        source_id="conv_alice",
        fmt="markdown",
        request_id="req_create",
    )
    with pytest.raises(ExportError) as error:
        harness.service.get(harness.bob, created["export_id"], "req_guess")
    assert error.value.code in {"RESOURCE_NOT_FOUND", "RESOURCE_FORBIDDEN"}
    with pytest.raises(ExportError) as missing:
        harness.service.get(harness.alice, "exp_unknown_guess", "req_missing")
    assert missing.value.code in {"RESOURCE_NOT_FOUND", "RESOURCE_FORBIDDEN"}


def test_FR_EXPORT_001_create_returns_requested_without_rerunning_qa(harness):
    reads_before = harness.answers.reads
    created = harness.service.create(
        harness.alice,
        source_type="conversation",
        source_id="conv_alice",
        fmt="markdown",
        request_id="req_ok",
    )
    assert created["state"] == "requested"
    assert created["export_id"].startswith("exp_")
    assert harness.answers.qa_invocations == 0
    assert harness.answers.reads == reads_before + 1
    status = harness.service.get(harness.alice, created["export_id"], "req_status")
    assert status["state"] == "ready"
    assert status["download_url"]
    assert not contains_internal_storage_host(status["download_url"])
    assert harness.objects.presign_calls == []


def test_FR_EXPORT_001_download_url_hides_minio_internal_address(harness):
    created = harness.service.create(
        harness.alice,
        source_type="conversation",
        source_id="conv_alice",
        fmt="markdown",
        request_id="req_url",
    )
    status = harness.service.get(harness.alice, created["export_id"], "req_get")
    url = status["download_url"]
    assert url is not None
    assert url.startswith("https://files.pivot.test/")
    assert "minio" not in url.lower()
    assert ":9000" not in url
    assert "X-Amz" not in url
    assert harness.objects.presign_calls == []


def test_FR_EXPORT_001_source_ownership_is_rechecked_on_document(harness):
    with pytest.raises(ExportError) as error:
        harness.service.create(
            harness.alice,
            source_type="document",
            source_id="doc_secret",
            fmt="docx",
            request_id="req_doc",
        )
    assert error.value.code in {"RESOURCE_NOT_FOUND", "RESOURCE_FORBIDDEN"}
    created = harness.service.create(
        harness.alice,
        source_type="document",
        source_id="doc_shared",
        fmt="docx",
        request_id="req_doc_ok",
    )
    status = harness.service.get(harness.alice, created["export_id"], "req_doc_get")
    assert status["state"] == "ready"
    kinds = [call[0] for call in harness.access.calls]
    assert "document" in kinds
    assert "export" in kinds
