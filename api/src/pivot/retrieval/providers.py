"""Injected HTTP query embedder and reranker. No vendor URLs or frozen sizes."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import NoReturn, Protocol

from pivot.retrieval.models import RankedHit
from pivot.retrieval.ports import RetrieverError

__all__ = [
    "HttpBgeReranker",
    "HttpQueryEmbedder",
    "JsonHttpClient",
    "JsonHttpError",
    "StdlibJsonHttpClient",
]


class JsonHttpError(Exception):
    def __init__(
        self, message: str, *, status: int | None = None, timeout: bool = False
    ) -> None:
        super().__init__(message)
        self.status = status
        self.timeout = timeout


class JsonHttpClient(Protocol):
    def post_json(
        self,
        url: str,
        payload: dict,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> dict: ...


class StdlibJsonHttpClient:
    def post_json(
        self,
        url: str,
        payload: dict,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST")
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


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _provider_error(
    code: str, message: str, api_key: str, exc: BaseException | None = None
) -> NoReturn:
    safe = message.replace(api_key, "[redacted]") if api_key else message
    error = RetrieverError(code, safe)
    if exc is not None:
        raise error from exc
    raise error


class HttpQueryEmbedder:
    def __init__(
        self,
        client: JsonHttpClient,
        *,
        endpoint: str,
        model: str,
        api_key: str,
        timeout_seconds: float | None = None,
        expected_dimension: int | None = None,
    ) -> None:
        if not endpoint.strip() or not model.strip() or not api_key:
            raise ValueError("endpoint, model, and api_key are required")
        if expected_dimension is not None and expected_dimension <= 0:
            raise ValueError("dimension must be positive")
        self._client = client
        self._endpoint = endpoint.strip()
        self._model = model.strip()
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._expected_dimension = expected_dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            payload = self._client.post_json(
                self._endpoint,
                {"model": self._model, "input": list(texts)},
                _auth_headers(self._api_key),
                timeout=self._timeout,
            )
        except RetrieverError:
            raise
        except Exception as exc:
            _provider_error(
                "PROVIDER_TEMPORARY_ERROR", "query embedding failed", self._api_key, exc
            )
        return self._vectors(payload, expected=len(texts))

    def _vectors(self, payload: Mapping, *, expected: int) -> list[list[float]]:
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            _provider_error("PROVIDER_TEMPORARY_ERROR", "query embedding empty", self._api_key)
        ordered = sorted(
            (item for item in data if isinstance(item, Mapping)),
            key=lambda item: int(item.get("index") or 0),
        )
        vectors: list[list[float]] = []
        for item in ordered:
            raw = item.get("embedding")
            if not isinstance(raw, list) or not raw:
                _provider_error(
                    "PROVIDER_TEMPORARY_ERROR", "query embedding empty", self._api_key
                )
            vector = [float(value) for value in raw]
            if (
                self._expected_dimension is not None
                and len(vector) != self._expected_dimension
            ):
                _provider_error(
                    "RESOURCE_LIMIT", "embedding dimension mismatch", self._api_key
                )
            vectors.append(vector)
        if len(vectors) != expected:
            _provider_error("PROVIDER_TEMPORARY_ERROR", "query embedding empty", self._api_key)
        return vectors


class HttpBgeReranker:
    def __init__(
        self,
        client: JsonHttpClient,
        *,
        endpoint: str,
        model: str,
        api_key: str,
        timeout_seconds: float | None = None,
    ) -> None:
        if not endpoint.strip() or not model.strip() or not api_key:
            raise ValueError("endpoint, model, and api_key are required")
        self._client = client
        self._endpoint = endpoint.strip()
        self._model = model.strip()
        self._api_key = api_key
        self._timeout = timeout_seconds

    def rerank(
        self, query: str, chunk_ids: tuple[str, ...], texts: dict[str, str], limit: int
    ) -> tuple[RankedHit, ...]:
        if limit <= 0:
            _provider_error("PROVIDER_TEMPORARY_ERROR", "limit must be positive", self._api_key)
        if not chunk_ids:
            return ()
        documents = [texts.get(chunk_id, "") for chunk_id in chunk_ids]
        try:
            payload = self._client.post_json(
                self._endpoint,
                {"model": self._model, "query": query, "documents": documents},
                _auth_headers(self._api_key),
                timeout=self._timeout,
            )
        except RetrieverError:
            raise
        except Exception as exc:
            _provider_error("PROVIDER_TEMPORARY_ERROR", "rerank failed", self._api_key, exc)
        return self._ranked(payload, chunk_ids, limit)

    def _ranked(
        self, payload: Mapping, chunk_ids: tuple[str, ...], limit: int
    ) -> tuple[RankedHit, ...]:
        results = payload.get("results")
        if not isinstance(results, list):
            _provider_error("PROVIDER_TEMPORARY_ERROR", "rerank failed", self._api_key)
        scored: list[RankedHit] = []
        for item in results:
            if not isinstance(item, Mapping):
                continue
            index = item.get("index")
            if not isinstance(index, int) or index < 0 or index >= len(chunk_ids):
                continue
            raw_score = item.get("relevance_score", item.get("score"))
            try:
                score = float(raw_score or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            scored.append(
                RankedHit(chunk_id=chunk_ids[index], score=score, source="rerank")
            )
        scored.sort(key=lambda hit: hit.score, reverse=True)
        unique: list[RankedHit] = []
        seen: set[str] = set()
        for hit in scored:
            if hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            unique.append(hit)
        return tuple(unique[:limit])
