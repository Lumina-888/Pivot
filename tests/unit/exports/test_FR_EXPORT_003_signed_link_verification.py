"""ND-GAP-04: signed download link verification at the service gate."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from pivot.exports.errors import ExportError


def _link_parts(url: str) -> tuple[str, int, str]:
    parsed = urlparse(url)
    export_id = parsed.path.rsplit("/", 1)[-1]
    query = parse_qs(parsed.query)
    return export_id, int(query["e"][0]), query["s"][0]


def _ready_link(harness) -> tuple[str, int, str]:
    created = harness.service.create(
        harness.alice,
        source_type="conversation",
        source_id="conv_alice",
        fmt="markdown",
        request_id="req_create",
    )
    status = harness.service.get(harness.alice, created["export_id"], "req_status")
    assert status["download_url"]
    return _link_parts(status["download_url"])


def test_FR_EXPORT_003_valid_link_passes_verification(harness):
    export_id, expiry, signature = _ready_link(harness)
    harness.service.verify_download_link(export_id, expiry, signature, "req_ok")


def test_FR_EXPORT_003_tampered_signature_is_forbidden(harness):
    export_id, expiry, signature = _ready_link(harness)
    forged = signature[:-1] + ("0" if signature[-1] != "0" else "1")
    with pytest.raises(ExportError) as error:
        harness.service.verify_download_link(export_id, expiry, forged, "req_forged")
    assert error.value.code == "RESOURCE_FORBIDDEN"


def test_FR_EXPORT_003_expired_link_is_rejected(harness):
    export_id, expiry, signature = _ready_link(harness)
    harness.clock.advance(301)
    with pytest.raises(ExportError) as error:
        harness.service.verify_download_link(export_id, expiry, signature, "req_stale")
    assert error.value.code == "EXPORT_LINK_EXPIRED"
