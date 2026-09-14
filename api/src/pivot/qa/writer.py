"""Injected HTTP draft writer. No vendor URLs or frozen model names."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import NoReturn

from pivot.qa.draft import draft_from_evidence
from pivot.qa.errors import WriterError
from pivot.qa.ports import EvidenceHit
from pivot.retrieval.providers import JsonHttpError
from pivot.shared.ids import new_id

_RETRYABLE = frozenset(
    {"PROVIDER_TIMEOUT", "PROVIDER_RATE_LIMITED", "PROVIDER_TEMPORARY_ERROR"}
)
_DRAFT_INSTRUCTIONS = (
    "Answer only from the provided evidence. "
    "Return JSON with markdown and claims. "
    "Each claim must use evidence_index from the evidence list. "
    "Do not add facts that are not in the evidence."
)


def _redact(message: str, api_key: str) -> str:
    if api_key and api_key in message:
        return message.replace(api_key, "[redacted]")
    return message


def _raise(code: str, message: str, api_key: str, exc: BaseException | None = None) -> NoReturn:
    error = WriterError(code, _redact(message, api_key))
    if exc is not None:
        raise error from exc
    raise error


def _auth_headers(api_key: str, header: str | None, scheme: str | None) -> dict[str, str]:
    name = (header or "Authorization").strip() or "Authorization"
    if scheme is None:
        prefix = "Bearer" if name.lower() == "authorization" else ""
    else:
        prefix = scheme.strip()
    value = f"{prefix} {api_key}".strip() if prefix else api_key
    return {name: value}


def _map_http_error(exc: BaseException, api_key: str) -> NoReturn:
    if isinstance(exc, JsonHttpError):
        if exc.timeout:
            _raise("PROVIDER_TIMEOUT", "draft writer timed out", api_key, exc)
        if exc.status == 429:
            _raise("PROVIDER_RATE_LIMITED", "draft writer rate limited", api_key, exc)
        if exc.status is not None and exc.status >= 500:
            _raise("PROVIDER_TEMPORARY_ERROR", "draft writer unavailable", api_key, exc)
    _raise("PROVIDER_TEMPORARY_ERROR", "draft writer failed", api_key, exc)


def _maybe_json(content: str) -> dict | None:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = "\n".join(lines[1:])
        if inner.rstrip().endswith("```"):
            inner = inner.rsplit("```", 1)[0]
        text = inner.strip()
    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _citations_for_hits(hits: tuple[EvidenceHit, ...]) -> list[dict]:
    citations = []
    for hit in hits:
        citations.append(
            {
                "id": new_id("citation"),
                "document_id": hit.document_id,
                "version_id": hit.version_id,
                "chunk_id": hit.chunk_id,
                "locator": hit.locator,
            }
        )
    return citations


def _draft_from_hits(
    hits: tuple[EvidenceHit, ...], markdown: str
) -> tuple[str, list[dict], list[dict]]:
    _, claims, citations = draft_from_evidence(hits)
    return markdown, claims, citations


def _draft_from_payload(
    parsed: Mapping, hits: tuple[EvidenceHit, ...], fallback_markdown: str
) -> tuple[str, list[dict], list[dict]]:
    markdown = str(parsed.get("markdown") or "").strip() or fallback_markdown.strip()
    raw_claims = parsed.get("claims")
    if not isinstance(raw_claims, list) or not raw_claims:
        return _draft_from_hits(hits, markdown)
    citations = _citations_for_hits(hits)
    by_index = {index: item for index, item in enumerate(citations)}
    by_chunk = {item["chunk_id"]: item for item in citations}
    claims: list[dict] = []
    used: list[dict] = []
    seen: set[str] = set()
    for raw in raw_claims:
        if not isinstance(raw, Mapping):
            continue
        citation = None
        index = raw.get("evidence_index")
        if isinstance(index, int) and index in by_index:
            citation = by_index[index]
        chunk_id = raw.get("chunk_id")
        if citation is None and isinstance(chunk_id, str) and chunk_id in by_chunk:
            citation = by_chunk[chunk_id]
        if citation is None:
            continue
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        claim_id = new_id("claim")
        bound = dict(citation)
        bound["claim_id"] = claim_id
        claims.append(
            {
                "id": claim_id,
                "text": text,
                "citation_ids": (bound["id"],),
                "support": "unsupported",
            }
        )
        if bound["id"] not in seen:
            used.append(bound)
            seen.add(bound["id"])
    if not claims:
        return _draft_from_hits(hits, markdown)
    return markdown, claims, used


class EvidenceJoinWriter:
    def draft(
        self, question: str, hits: tuple[EvidenceHit, ...]
    ) -> tuple[str, list[dict], list[dict]]:
        del question
        return draft_from_evidence(hits)


class HttpDraftWriter:
    def __init__(
        self,
        client,
        *,
        endpoint: str,
        model: str,
        api_key: str,
        timeout_seconds: float | None = None,
        auth_header: str | None = None,
        auth_scheme: str | None = None,
    ) -> None:
        if not endpoint.strip() or not model.strip() or not api_key:
            raise ValueError("endpoint, model, and api_key are required")
        self._client = client
        self._endpoint = endpoint.strip()
        self._model = model.strip()
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._auth_header = auth_header
        self._auth_scheme = auth_scheme

    def draft(
        self, question: str, hits: tuple[EvidenceHit, ...]
    ) -> tuple[str, list[dict], list[dict]]:
        if not hits:
            return "", [], []
        if any(not hit.external_llm_allowed for hit in hits):
            _raise(
                "EXTERNAL_LLM_NOT_ALLOWED",
                "document forbids external llm",
                self._api_key,
            )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _DRAFT_INSTRUCTIONS},
                {"role": "user", "content": _user_content(question, hits)},
            ],
        }
        try:
            response = self._client.post_json(
                self._endpoint,
                payload,
                _auth_headers(self._api_key, self._auth_header, self._auth_scheme),
                timeout=self._timeout,
            )
        except WriterError:
            raise
        except Exception as exc:
            _map_http_error(exc, self._api_key)
        else:
            return self._parse(response, hits)

    def _parse(
        self, payload: Mapping, hits: tuple[EvidenceHit, ...]
    ) -> tuple[str, list[dict], list[dict]]:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            _raise("PROVIDER_TEMPORARY_ERROR", "draft writer empty", self._api_key)
        first = choices[0]
        if not isinstance(first, Mapping):
            _raise("PROVIDER_TEMPORARY_ERROR", "draft writer empty", self._api_key)
        message = first.get("message")
        if not isinstance(message, Mapping):
            _raise("PROVIDER_TEMPORARY_ERROR", "draft writer empty", self._api_key)
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            _raise("PROVIDER_TEMPORARY_ERROR", "draft writer empty", self._api_key)
        parsed = _maybe_json(content)
        if parsed is None:
            return _draft_from_hits(hits, content.strip())
        return _draft_from_payload(parsed, hits, content)


def _user_content(question: str, hits: tuple[EvidenceHit, ...]) -> str:
    lines = [f"Question: {question}", "Evidence:"]
    for index, hit in enumerate(hits):
        lines.append(f"[{index}] chunk_id={hit.chunk_id} locator={hit.locator}")
        lines.append(hit.text)
    return "\n".join(lines)


class FailoverDraftWriter:
    def __init__(self, primary, fallback) -> None:
        self._primary = primary
        self._fallback = fallback

    def draft(
        self, question: str, hits: tuple[EvidenceHit, ...]
    ) -> tuple[str, list[dict], list[dict]]:
        try:
            return self._primary.draft(question, hits)
        except WriterError as exc:
            if exc.code not in _RETRYABLE:
                raise
            return self._fallback.draft(question, hits)
