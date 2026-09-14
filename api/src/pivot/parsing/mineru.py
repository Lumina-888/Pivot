"""Injected MinerU cloud parser. No vendor URLs or frozen model names."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from io import BytesIO
from typing import NoReturn, Protocol

from pivot.parsing.errors import ParseError, parse_error
from pivot.parsing.models import ParsedBlock, ParsedDocument
from pivot.retrieval.providers import JsonHttpError

_KINDS = ("pdf", "docx", "pptx", "xlsx")
_BUSINESS_CODES = {
    -60002: "UNSUPPORTED_EXTENSION",
    -60003: "CORRUPTED_FILE",
    -60004: "EMPTY_TEXT",
    -60005: "RESOURCE_LIMIT",
    -60006: "RESOURCE_LIMIT",
    -60008: "PROVIDER_TIMEOUT",
    -60010: "CORRUPTED_FILE",
    -60015: "CORRUPTED_FILE",
    -60016: "CORRUPTED_FILE",
    -60018: "RESOURCE_LIMIT",
}


class MinerUHttpClient(Protocol):
    def post_json(
        self,
        url: str,
        payload: dict,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> dict: ...

    def get_json(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> dict: ...

    def put_bytes(
        self,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> None: ...

    def get_bytes(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> bytes: ...


class StdlibMinerUHttpClient:
    def post_json(
        self,
        url: str,
        payload: dict,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> dict:
        return _read_json(url, json.dumps(payload).encode("utf-8"), headers, timeout, "POST")

    def get_json(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> dict:
        return _read_json(url, None, headers, timeout, "GET")

    def put_bytes(
        self,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> None:
        request = urllib.request.Request(url, data=body, method="PUT")
        request.unredirected_hdrs.pop("Content-type", None)
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response.read()
        except urllib.error.HTTPError as exc:
            raise JsonHttpError("http request failed", status=exc.code) from exc
        except TimeoutError as exc:
            raise JsonHttpError("http request timed out", timeout=True) from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise JsonHttpError("http transport failed") from exc

    def get_bytes(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> bytes:
        request = urllib.request.Request(url, method="GET")
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise JsonHttpError("http request failed", status=exc.code) from exc
        except TimeoutError as exc:
            raise JsonHttpError("http request timed out", timeout=True) from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise JsonHttpError("http transport failed") from exc


def _read_json(
    url: str,
    body: bytes | None,
    headers: Mapping[str, str],
    timeout: float | None,
    method: str,
) -> dict:
    request = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise JsonHttpError("http request failed", status=exc.code) from exc
    except TimeoutError as exc:
        raise JsonHttpError("http request timed out", timeout=True) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise JsonHttpError("http transport failed") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JsonHttpError("http response is not json") from exc
    if not isinstance(parsed, dict):
        raise JsonHttpError("http response is not an object")
    return parsed


def _redact(message: str, token: str) -> str:
    if token and token in message:
        return message.replace(token, "[redacted]")
    return message


def _raise(
    code: str, message: str, token: str, exc: BaseException | None = None
) -> NoReturn:
    error = parse_error(code, _redact(message, token))
    if exc is not None:
        raise error from exc
    raise error


def _map_transport(exc: BaseException, token: str) -> NoReturn:
    if isinstance(exc, ParseError):
        raise exc
    if isinstance(exc, JsonHttpError):
        if exc.timeout:
            _raise("PROVIDER_TIMEOUT", "parser timed out", token, exc)
        if exc.status == 429:
            _raise("PROVIDER_RATE_LIMITED", "parser rate limited", token, exc)
        if exc.status is not None and exc.status >= 500:
            _raise("PROVIDER_TEMPORARY_ERROR", "parser unavailable", token, exc)
    _raise("PROVIDER_TEMPORARY_ERROR", "parser failed", token, exc)


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return None


def _join(endpoint: str, path: str) -> str:
    return f"{endpoint.rstrip('/')}/{path.lstrip('/')}"


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _raise_from_envelope(payload: Mapping, token: str) -> None:
    msg_code = str(payload.get("msgCode") or "")
    if msg_code in {"A0202", "A0211"}:
        _raise("PROVIDER_TEMPORARY_ERROR", "parser authentication failed", token)
    code = _as_int(payload.get("code"))
    if code is None or code == 0:
        return
    mapped = _BUSINESS_CODES.get(code, "PROVIDER_TEMPORARY_ERROR")
    message = str(payload.get("msg") or payload.get("err_msg") or "parser failed")
    _raise(mapped, message, token)


class MinerUCloudParser:
    def __init__(
        self,
        client: MinerUHttpClient,
        *,
        endpoint: str,
        token: str,
        kind: str = "pdf",
        timeout_seconds: float | None = None,
        poll_timeout_seconds: float | None = None,
        poll_interval_seconds: float | None = None,
        model: str | None = None,
        sleep: Callable[[float], None] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        if not endpoint.strip() or not token:
            raise ValueError("endpoint and token are required")
        if kind not in _KINDS:
            raise ValueError(f"unsupported kind {kind!r}")
        self._client = client
        self._endpoint = endpoint.strip()
        self._token = token
        self.kind = kind
        self._timeout = timeout_seconds
        self._poll_timeout = poll_timeout_seconds
        self._poll_interval = poll_interval_seconds
        self._model = (model or "").strip() or None
        self._sleep = sleep or time.sleep
        self._monotonic = monotonic or time.monotonic

    def parse(self, content: bytes) -> ParsedDocument:
        self._reject_local(content)
        headers = _auth_headers(self._token)
        try:
            batch = self._submit(content, headers)
            zip_url = self._poll(batch, headers)
            blob = self._client.get_bytes(zip_url, headers, timeout=self._timeout)
        except Exception as exc:
            _map_transport(exc, self._token)
        return _document_from_zip(self.kind, blob, self._token)

    def _reject_local(self, content: bytes) -> None:
        if self.kind == "pdf":
            if not content.startswith(b"%PDF"):
                _raise("CORRUPTED_FILE", "PDF 文件损坏", self._token)
            if b"/Encrypt" in content:
                _raise("ENCRYPTED_FILE", "加密文件无法解析", self._token)
            return
        if not content.startswith(b"PK"):
            _raise("CORRUPTED_FILE", "Office 文件损坏", self._token)

    def _submit(self, content: bytes, headers: Mapping[str, str]) -> str:
        payload: dict[str, object] = {
            "files": [{"name": f"document.{self.kind}", "data_id": "document"}]
        }
        if self._model:
            payload["model_version"] = self._model
        accepted = self._client.post_json(
            _join(self._endpoint, "file-urls/batch"),
            payload,
            headers,
            timeout=self._timeout,
        )
        _raise_from_envelope(accepted, self._token)
        data = accepted.get("data")
        if not isinstance(data, Mapping):
            _raise("PROVIDER_TEMPORARY_ERROR", "parser empty", self._token)
        urls = data.get("file_urls")
        batch_id = str(data.get("batch_id") or "").strip()
        if not batch_id or not isinstance(urls, list) or not urls:
            _raise("PROVIDER_TEMPORARY_ERROR", "parser empty", self._token)
        upload_url = str(urls[0] or "").strip()
        if not upload_url:
            _raise("PROVIDER_TEMPORARY_ERROR", "parser empty", self._token)
        self._client.put_bytes(upload_url, content, headers, timeout=self._timeout)
        return batch_id

    def _poll(self, batch_id: str, headers: Mapping[str, str]) -> str:
        deadline = None
        if self._poll_timeout is not None:
            deadline = self._monotonic() + self._poll_timeout
        url = _join(self._endpoint, f"extract-results/batch/{batch_id}")
        while True:
            if deadline is not None and self._monotonic() >= deadline:
                _raise("PROVIDER_TIMEOUT", "parser poll timed out", self._token)
            payload = self._client.get_json(url, headers, timeout=self._timeout)
            _raise_from_envelope(payload, self._token)
            item = _result_item(payload, self._token)
            state = str(item.get("state") or "").strip()
            if state == "done":
                zip_url = str(item.get("full_zip_url") or "").strip()
                if not zip_url:
                    _raise("PROVIDER_TEMPORARY_ERROR", "parser empty", self._token)
                return zip_url
            if state == "failed":
                _raise_failed_item(item, self._token)
            interval = self._poll_interval if self._poll_interval is not None else 0.0
            self._sleep(interval)


def _result_item(payload: Mapping, token: str) -> Mapping:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        _raise("PROVIDER_TEMPORARY_ERROR", "parser empty", token)
    results = data.get("extract_result")
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, Mapping):
            return first
    if str(data.get("state") or "").strip():
        return data
    _raise("PROVIDER_TEMPORARY_ERROR", "parser empty", token)


def _raise_failed_item(item: Mapping, token: str) -> NoReturn:
    code = _as_int(item.get("err_code") or item.get("code"))
    mapped = _BUSINESS_CODES.get(code or 0, "CORRUPTED_FILE") if code else "CORRUPTED_FILE"
    message = str(item.get("err_msg") or item.get("msg") or "parse failed")
    _raise(mapped, message, token)


def _document_from_zip(kind: str, blob: bytes, token: str) -> ParsedDocument:
    try:
        archive = zipfile.ZipFile(BytesIO(blob))
    except zipfile.BadZipFile as exc:
        _raise("CORRUPTED_FILE", "parser zip damaged", token, exc)
    with archive:
        names = archive.namelist()
        list_name = _named(names, "content_list.json")
        markdown_name = _named(names, "full.md")
        blocks: list[ParsedBlock] = []
        if list_name is not None:
            try:
                raw = json.loads(archive.read(list_name).decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                _raise("CORRUPTED_FILE", "parser json damaged", token, exc)
            if isinstance(raw, list):
                blocks = _blocks_from_content_list(raw)
        if not blocks and markdown_name is not None:
            try:
                markdown = archive.read(markdown_name).decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                _raise("CORRUPTED_FILE", "parser markdown damaged", token, exc)
            blocks = _blocks_from_markdown(markdown)
    if not blocks:
        _raise("EMPTY_TEXT", "解析结果为空", token)
    return ParsedDocument(kind=kind, blocks=tuple(blocks))


def _named(names: list[str], suffix: str) -> str | None:
    for name in names:
        if name.rsplit("/", 1)[-1] == suffix:
            return name
    return None


def _blocks_from_content_list(items: list) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    title = ""
    for index, item in enumerate(items, start=1):
        if not isinstance(item, Mapping):
            continue
        text = str(item.get("text") or item.get("table_body") or "").strip()
        if not text:
            continue
        if item.get("text_level") == 1:
            title = text
        page = item.get("page_idx")
        locator = f"page={int(page) + 1}" if isinstance(page, int) else f"block={index}"
        blocks.append(ParsedBlock(text=text, locator=locator, title_path=title))
    return blocks


def _blocks_from_markdown(markdown: str) -> list[ParsedBlock]:
    paragraphs = [part.strip() for part in markdown.split("\n\n") if part.strip()]
    return [
        ParsedBlock(text=text, locator=f"block={index}", title_path="")
        for index, text in enumerate(paragraphs, start=1)
    ]
