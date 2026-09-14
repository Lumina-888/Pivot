"""Injected Fake MinerU transport. No network and no provider URLs."""

from __future__ import annotations

from collections.abc import Mapping


class ScriptedMinerUHttpClient:
    def __init__(
        self,
        *,
        post_responses: list[dict] | None = None,
        get_responses: list[dict] | None = None,
        byte_responses: list[bytes] | None = None,
        error: Exception | None = None,
        handler=None,
    ) -> None:
        self.calls: list[dict] = []
        self.uploads: list[bytes] = []
        self._posts = list(post_responses or [])
        self._gets = list(get_responses or [])
        self._bytes = list(byte_responses or [])
        self._error = error
        self._handler = handler

    def post_json(
        self,
        url: str,
        payload: dict,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> dict:
        self.calls.append(
            {
                "method": "POST",
                "url": url,
                "payload": payload,
                "headers": dict(headers),
                "timeout": timeout,
            }
        )
        if self._error is not None:
            raise self._error
        if self._handler is not None:
            return self._handler("POST", url, payload, headers, timeout)
        if not self._posts:
            raise RuntimeError("no scripted POST response")
        return self._posts.pop(0)

    def get_json(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> dict:
        self.calls.append(
            {
                "method": "GET",
                "url": url,
                "headers": dict(headers),
                "timeout": timeout,
            }
        )
        if self._error is not None:
            raise self._error
        if self._handler is not None:
            return self._handler("GET", url, None, headers, timeout)
        if not self._gets:
            raise RuntimeError("no scripted GET response")
        return self._gets.pop(0)

    def put_bytes(
        self,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> None:
        self.calls.append(
            {
                "method": "PUT",
                "url": url,
                "headers": dict(headers),
                "timeout": timeout,
                "size": len(body),
            }
        )
        self.uploads.append(body)
        if self._error is not None:
            raise self._error
        if self._handler is not None:
            self._handler("PUT", url, body, headers, timeout)

    def get_bytes(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> bytes:
        self.calls.append(
            {
                "method": "GET_BYTES",
                "url": url,
                "headers": dict(headers),
                "timeout": timeout,
            }
        )
        if self._error is not None:
            raise self._error
        if self._handler is not None:
            return self._handler("GET_BYTES", url, None, headers, timeout)
        if not self._bytes:
            raise RuntimeError("no scripted byte response")
        return self._bytes.pop(0)
