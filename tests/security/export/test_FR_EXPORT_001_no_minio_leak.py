from __future__ import annotations

import pytest
from pivot.exports.errors import ExportError
from pivot.exports.signer import contains_internal_storage_host


def test_FR_EXPORT_001_download_url_does_not_contain_minio_or_internal_hosts(harness):
    created = harness.service.create(
        harness.alice,
        source_type="conversation",
        source_id="conv_alice",
        fmt="markdown",
        request_id="req_sec_url",
    )
    status = harness.service.get(harness.alice, created["export_id"], "req_sec_get")
    url = status["download_url"]
    assert url is not None
    assert not contains_internal_storage_host(url)
    assert "minio" not in url.lower()
    assert "127.0.0.1" not in url
    assert "X-Amz-Expires" not in url
    assert harness.objects.presign_calls == []
    record = harness.exports.get(created["export_id"])
    assert record is not None
    assert record.storage_key is not None
    assert record.storage_key.startswith("exports/")


def test_FR_EXPORT_001_guessed_export_id_is_not_found_or_forbidden(harness):
    with pytest.raises(ExportError) as error:
        harness.service.download(harness.alice, "exp_forged", "req_forged")
    assert error.value.code in {"RESOURCE_NOT_FOUND", "RESOURCE_FORBIDDEN"}
    envelope = error.value.to_envelope()
    assert envelope["retryable"] is False
    assert "minio" not in envelope["message"].lower()


def test_FR_EXPORT_002_rendered_bytes_exclude_hidden_tool_parameters(harness):
    created = harness.service.create(
        harness.alice,
        source_type="conversation",
        source_id="conv_alice",
        fmt="docx",
        request_id="req_sec_doc",
    )
    data, filename, _ = harness.service.download(harness.alice, created["export_id"], "req_sec_dl")
    decoded = data.decode("latin-1", errors="ignore")
    assert "sk-secret-export" not in decoded
    assert "SYSTEM_PROMPT" not in decoded
    assert "tool_parameters" not in decoded
    assert ".." not in filename
    assert "/" not in filename
