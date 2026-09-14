"""MinerU cloud parser. Endpoint/token stay injected, not frozen."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from pivot.parsing.errors import ParseError
from pivot.parsing.fakes import ScriptedMinerUHttpClient
from pivot.parsing.mineru import MinerUCloudParser
from pivot.retrieval.providers import JsonHttpError
from samples import pdf_with_text

_SRC = (
    Path(__file__).resolve().parents[3]
    / "api"
    / "src"
    / "pivot"
    / "parsing"
    / "mineru.py"
)
_ENDPOINT = "https://parser.test/api/v4"
_TOKEN = "secret-mineru-token"


def _zip(*, markdown: str = "", content_list: list | None = None) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        if content_list is not None:
            archive.writestr("auto/content_list.json", json.dumps(content_list))
        archive.writestr("auto/full.md", markdown)
    return buffer.getvalue()


def _batch_accepted() -> dict:
    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "batch_id": "batch_1",
            "file_urls": ["https://upload.test/obj"],
        },
    }


def _batch_done(*, zip_url: str = "https://download.test/result.zip") -> dict:
    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "batch_id": "batch_1",
            "extract_result": [
                {
                    "file_name": "document.pdf",
                    "state": "done",
                    "full_zip_url": zip_url,
                }
            ],
        },
    }


def _parser(client, **overrides) -> MinerUCloudParser:
    values = dict(
        endpoint=_ENDPOINT,
        token=_TOKEN,
        kind="pdf",
        sleep=lambda _seconds: None,
    )
    values.update(overrides)
    return MinerUCloudParser(client, **values)


def test_FR_DOC_004_mineru_posts_injected_endpoint_and_bearer():
    client = ScriptedMinerUHttpClient(
        post_responses=[_batch_accepted()],
        get_responses=[_batch_done()],
        byte_responses=[_zip(markdown="Late arrival policy")],
    )
    parsed = _parser(client).parse(pdf_with_text())
    assert parsed.kind == "pdf"
    assert "Late arrival policy" in parsed.text
    post = next(item for item in client.calls if item["method"] == "POST")
    assert post["url"] == f"{_ENDPOINT}/file-urls/batch"
    assert post["headers"]["Authorization"] == f"Bearer {_TOKEN}"
    assert post["payload"]["files"][0]["name"].endswith(".pdf")
    assert "model_version" not in post["payload"]


def test_FR_DOC_004_mineru_uploads_bytes_and_polls_batch():
    pending = {
        "code": 0,
        "data": {
            "batch_id": "batch_1",
            "extract_result": [{"file_name": "document.pdf", "state": "running"}],
        },
    }
    client = ScriptedMinerUHttpClient(
        post_responses=[_batch_accepted()],
        get_responses=[pending, _batch_done()],
        byte_responses=[_zip(markdown="Attendance policy")],
    )
    content = pdf_with_text("Attendance policy")
    parsed = _parser(client, poll_interval_seconds=0.5).parse(content)
    assert "Attendance policy" in parsed.text
    assert client.uploads == [content]
    put = next(item for item in client.calls if item["method"] == "PUT")
    assert put["url"] == "https://upload.test/obj"
    polls = [item for item in client.calls if item["method"] == "GET"]
    assert len(polls) == 2
    assert polls[0]["url"] == f"{_ENDPOINT}/extract-results/batch/batch_1"
    download = next(item for item in client.calls if item["method"] == "GET_BYTES")
    assert download["url"] == "https://download.test/result.zip"


def test_FR_DOC_004_mineru_parses_zip_markdown_and_content_list():
    client = ScriptedMinerUHttpClient(
        post_responses=[_batch_accepted()],
        get_responses=[_batch_done()],
        byte_responses=[
            _zip(
                markdown="# ignored",
                content_list=[
                    {"type": "text", "text": "Section A", "page_idx": 0, "text_level": 1},
                    {"type": "table", "table_body": "late | absent", "page_idx": 1},
                ],
            )
        ],
    )
    parsed = _parser(client).parse(pdf_with_text())
    assert parsed.blocks[0].text == "Section A"
    assert parsed.blocks[0].locator == "page=1"
    assert parsed.blocks[0].title_path == "Section A"
    assert parsed.blocks[1].text == "late | absent"
    assert parsed.blocks[1].locator == "page=2"


def test_FR_DOC_004_mineru_does_not_hardcode_vendor():
    text = _SRC.read_text(encoding="utf-8").lower()
    assert "mineru.net" not in text
    assert "opendatalab" not in text
    assert "vlm" not in text
    assert "pipeline" not in text


def test_FR_DOC_004_mineru_encrypted_pdf_skips_http():
    client = ScriptedMinerUHttpClient()
    with pytest.raises(ParseError) as caught:
        _parser(client).parse(b"%PDF-1.4\n/Encrypt 1 0 R\n%%EOF\n")
    assert caught.value.code == "ENCRYPTED_FILE"
    assert client.calls == []


def test_FR_DOC_004_mineru_corrupted_pdf_skips_http():
    client = ScriptedMinerUHttpClient()
    with pytest.raises(ParseError) as caught:
        _parser(client).parse(b"not-a-pdf")
    assert caught.value.code == "CORRUPTED_FILE"
    assert client.calls == []


def test_FR_DOC_004_mineru_scan_pdf_goes_to_cloud():
    client = ScriptedMinerUHttpClient(
        post_responses=[_batch_accepted()],
        get_responses=[_batch_done()],
        byte_responses=[_zip(markdown="OCR recovered text")],
    )
    parsed = _parser(client).parse(b"%PDF-1.4\n/Subtype /Image\n%%EOF\n")
    assert "OCR recovered text" in parsed.text
    assert client.uploads


def test_FR_DOC_004_mineru_empty_zip_is_empty_text():
    client = ScriptedMinerUHttpClient(
        post_responses=[_batch_accepted()],
        get_responses=[_batch_done()],
        byte_responses=[_zip(markdown="   ")],
    )
    with pytest.raises(ParseError) as caught:
        _parser(client).parse(pdf_with_text())
    assert caught.value.code == "EMPTY_TEXT"


def test_FR_DOC_004_mineru_timeout_is_provider_timeout():
    client = ScriptedMinerUHttpClient(error=JsonHttpError("slow", timeout=True))
    with pytest.raises(ParseError) as caught:
        _parser(client).parse(pdf_with_text())
    assert caught.value.code == "PROVIDER_TIMEOUT"
    assert caught.value.retryable is True


def test_FR_DOC_004_mineru_429_is_rate_limited():
    client = ScriptedMinerUHttpClient(error=JsonHttpError("limited", status=429))
    with pytest.raises(ParseError) as caught:
        _parser(client).parse(pdf_with_text())
    assert caught.value.code == "PROVIDER_RATE_LIMITED"
    assert caught.value.retryable is True


def test_FR_DOC_004_mineru_5xx_is_temporary():
    client = ScriptedMinerUHttpClient(error=JsonHttpError("upstream", status=503))
    with pytest.raises(ParseError) as caught:
        _parser(client).parse(pdf_with_text())
    assert caught.value.code == "PROVIDER_TEMPORARY_ERROR"
    assert caught.value.retryable is True


def test_FR_DOC_004_mineru_poll_timeout_is_provider_timeout():
    pending = {
        "code": 0,
        "data": {
            "batch_id": "batch_1",
            "extract_result": [{"file_name": "document.pdf", "state": "running"}],
        },
    }
    client = ScriptedMinerUHttpClient(
        post_responses=[_batch_accepted()],
        get_responses=[pending, pending, pending],
    )
    times = iter([0.0, 0.0, 0.5, 2.5])

    def _monotonic() -> float:
        return next(times)

    with pytest.raises(ParseError) as caught:
        _parser(
            client,
            poll_timeout_seconds=2.0,
            poll_interval_seconds=0.5,
            monotonic=_monotonic,
        ).parse(pdf_with_text())
    assert caught.value.code == "PROVIDER_TIMEOUT"
    assert caught.value.retryable is True


def test_FR_DOC_004_mineru_too_large_is_resource_limit():
    client = ScriptedMinerUHttpClient(
        post_responses=[{"code": -60005, "msg": "too large", "data": None}]
    )
    with pytest.raises(ParseError) as caught:
        _parser(client).parse(pdf_with_text())
    assert caught.value.code == "RESOURCE_LIMIT"
    assert caught.value.retryable is True


def test_FR_DOC_004_mineru_does_not_leak_token():
    client = ScriptedMinerUHttpClient(error=RuntimeError("secret-mineru-token exploded"))
    with pytest.raises(ParseError) as caught:
        _parser(client).parse(pdf_with_text())
    assert _TOKEN not in str(caught.value)
    assert _TOKEN not in repr(caught.value)


def test_FR_DOC_004_mineru_does_not_send_frozen_model():
    client = ScriptedMinerUHttpClient(
        post_responses=[_batch_accepted()],
        get_responses=[_batch_done()],
        byte_responses=[_zip(markdown="ok")],
    )
    _parser(client).parse(pdf_with_text())
    payload = client.calls[0]["payload"]
    assert "model_version" not in payload
    assert "vlm" not in json.dumps(payload).lower()
    assert "pipeline" not in json.dumps(payload).lower()


def test_FR_DOC_004_mineru_sends_injected_model():
    client = ScriptedMinerUHttpClient(
        post_responses=[_batch_accepted()],
        get_responses=[_batch_done()],
        byte_responses=[_zip(markdown="ok")],
    )
    _parser(client, model="injected-parser-model").parse(pdf_with_text())
    assert client.calls[0]["payload"]["model_version"] == "injected-parser-model"
