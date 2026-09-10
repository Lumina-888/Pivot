"""HTTP query embedder. Endpoint/model/dimension stay injected, not frozen."""

from __future__ import annotations

from pathlib import Path

import pytest
from pivot.retrieval.fakes import ScriptedJsonHttpClient
from pivot.retrieval.ports import RetrieverError
from pivot.retrieval.providers import HttpQueryEmbedder

_SRC = Path(__file__).resolve().parents[3] / "api" / "src" / "pivot" / "retrieval"


def _embedder(client, **overrides) -> HttpQueryEmbedder:
    values = dict(
        endpoint="https://embed.test/v1/embeddings",
        model="injected-embed-model",
        api_key="secret-embed-key",
        timeout_seconds=1.5,
        expected_dimension=4,
    )
    values.update(overrides)
    return HttpQueryEmbedder(client, **values)


def test_FR_RAG_001_http_embedder_posts_injected_model_and_input():
    client = ScriptedJsonHttpClient(
        [{"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]}]}]
    )
    embedder = _embedder(client)
    vectors = embedder.embed(["迟到书面警告"])
    assert vectors == [[0.1, 0.2, 0.3, 0.4]]
    assert client.calls[0]["url"] == "https://embed.test/v1/embeddings"
    assert client.calls[0]["payload"] == {
        "model": "injected-embed-model",
        "input": ["迟到书面警告"],
    }
    assert client.calls[0]["headers"]["Authorization"] == "Bearer secret-embed-key"
    assert client.calls[0]["timeout"] == 1.5


def test_FR_RAG_001_http_embedder_uses_injected_dimension():
    client = ScriptedJsonHttpClient(
        [{"data": [{"embedding": [1.0, 2.0], "index": 0}]}]
    )
    embedder = _embedder(client, expected_dimension=2, timeout_seconds=None)
    assert len(embedder.embed(["ok"])[0]) == 2
    with pytest.raises(RetrieverError) as mismatch:
        _embedder(
            client=ScriptedJsonHttpClient(
                [{"data": [{"index": 0, "embedding": [1.0, 2.0, 3.0]}]}]
            )
        ).embed(["bad-dim"])
    assert mismatch.value.code == "RESOURCE_LIMIT"


def test_FR_RAG_001_http_embedder_does_not_hardcode_vendor():
    src = (_SRC / "providers.py").read_text(encoding="utf-8")
    lowered = src.lower()
    assert "siliconflow" not in lowered
    assert "openai.com" not in lowered
    assert "bge-m3" not in lowered
    assert "1024" not in src
    assert "top-50" not in src
    assert "timeout=30" not in src.replace(" ", "")


def test_FR_RAG_001_http_embedder_failure_is_provider_error():
    client = ScriptedJsonHttpClient(error=RuntimeError("upstream 503"))
    with pytest.raises(RetrieverError) as caught:
        _embedder(client).embed(["迟到"])
    assert caught.value.code == "PROVIDER_TEMPORARY_ERROR"
    assert "secret-embed-key" not in str(caught.value)
    assert "secret-embed-key" not in repr(caught.value)


def test_FR_RAG_001_http_embedder_does_not_leak_api_key():
    client = ScriptedJsonHttpClient(responses=[{"data": []}])
    with pytest.raises(RetrieverError) as caught:
        _embedder(client).embed(["迟到"])
    assert "secret-embed-key" not in str(caught.value)
    assert "secret-embed-key" not in repr(caught.value)
