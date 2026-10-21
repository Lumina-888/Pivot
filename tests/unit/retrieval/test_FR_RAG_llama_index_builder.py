"""Index builder for the LlamaIndex backend: payload mapping and fail-fast checks."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("llama_index.core")

from pivot.retrieval.llama_embeddings import PivotEmbedding  # noqa: E402
from pivot.retrieval.llama_index_builder import (  # noqa: E402
    build_llama_index,
    scroll_payloads,
)
from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever  # noqa: E402
from pivot.retrieval.policy import RetrievalPolicy  # noqa: E402
from pivot.retrieval.tokenize import SimpleLexTokenizer  # noqa: E402
from pivot.storage.adapters.qdrant import QdrantVectorStore  # noqa: E402


def _payload(**overrides):
    payload = {
        "chunk_id": "chunk-1",
        "version_id": "ver-1",
        "document_id": "doc-1",
        "text": "一个月内累计迟到三次，视为旷工一天。",
        "locator": "第一条",
        "ready": True,
        "current": True,
        "allowed": True,
        "expired": False,
        "deleted": False,
        "index_generation": "gen-1",
        "embedding_model_version": "controlled-2",
        "retrieval_config_version": "cfg-1",
    }
    payload.update(overrides)
    return payload


class _ControlledEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0] if "迟到" in text else [0.0, 1.0] for text in texts]


def _embed_model() -> PivotEmbedding:
    return PivotEmbedding(_ControlledEmbedder(), model_name="controlled-2", dimension=2)


def _nodes(index):
    return {node.node_id: node for node in index.docstore.docs.values()}


def test_FR_RAG_006_builder_builds_nodes_with_full_metadata():
    nested = {"id": "pt-1", "score": None, "chunk_id": "chunk-1", "version_id": "ver-1",
              "payload": _payload()}
    flat = _payload(chunk_id="chunk-2", version_id="ver-2", text="年假每年五天。",
                    locator="第二条")
    index = build_llama_index(
        [nested, flat],
        embed_model=_embed_model(),
        external_llm_allowed=lambda version_id: version_id == "ver-1",
    )
    nodes = _nodes(index)
    assert set(nodes) == {"chunk-1", "chunk-2"}
    first = nodes["chunk-1"]
    assert first.text == "一个月内累计迟到三次，视为旷工一天。"
    assert first.metadata["document_id"] == "doc-1"
    assert first.metadata["version_id"] == "ver-1"
    assert first.metadata["locator"] == "第一条"
    assert first.metadata["external_llm_allowed"] is True
    assert first.metadata["index_generation"] == "gen-1"
    assert first.metadata["embedding_model_version"] == "controlled-2"
    assert first.metadata["retrieval_config_version"] == "cfg-1"
    assert nodes["chunk-2"].metadata["external_llm_allowed"] is False


def test_FR_RAG_006_builder_index_supports_retrieval():
    index = build_llama_index(
        [_payload()],
        embed_model=_embed_model(),
        external_llm_allowed=lambda version_id: True,
    )
    retriever = LlamaIndexRetriever(
        index,
        policy=RetrievalPolicy(dense_k=5, bm25_k=5, rrf_k=60, evidence_limit=5),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=-1.0,
        authorize=lambda principal, document, version: True,
    )
    result = retriever.retrieve(
        "迟到三次怎么处理？",
        scope_type="global",
        scope_document_id=None,
        principal_id="user-1",
    )
    assert result.status == "found"
    hit, = result.evidence
    assert hit.chunk_id == "chunk-1"
    assert hit.locator == "第一条"
    assert hit.external_llm_allowed is True


@pytest.mark.parametrize(
    "field",
    [
        "chunk_id", "document_id", "version_id", "text", "locator",
        "index_generation", "embedding_model_version", "retrieval_config_version",
    ],
)
def test_FR_RAG_006_builder_rejects_payload_missing_required_field(field):
    payload = _payload()
    del payload[field]
    with pytest.raises(ValueError):
        build_llama_index(
            [payload],
            embed_model=_embed_model(),
            external_llm_allowed=lambda version_id: True,
        )


def test_FR_RAG_006_builder_rejects_non_bool_flag():
    with pytest.raises(ValueError):
        build_llama_index(
            [_payload(ready="true")],
            embed_model=_embed_model(),
            external_llm_allowed=lambda version_id: True,
        )


def test_FR_RAG_006_builder_fails_when_authorization_lookup_fails():
    def broken(version_id):
        raise RuntimeError("version store unavailable")

    with pytest.raises(RuntimeError):
        build_llama_index(
            [_payload()],
            embed_model=_embed_model(),
            external_llm_allowed=broken,
        )


def test_FR_RAG_006_builder_accepts_empty_payloads():
    index = build_llama_index(
        [],
        embed_model=_embed_model(),
        external_llm_allowed=lambda version_id: True,
    )
    assert _nodes(index) == {}


class _PagedStore:
    def __init__(self, payloads):
        self._payloads = list(payloads)

    def scroll(self, *, limit, offset=None):
        start = int(offset) if offset is not None else 0
        page = self._payloads[start:start + limit]
        next_offset = start + limit
        return page, (str(next_offset) if next_offset < len(self._payloads) else None)


def test_FR_RAG_006_scroll_payloads_drains_all_pages():
    store = _PagedStore([_payload(chunk_id=f"chunk-{i}") for i in range(5)])
    payloads = scroll_payloads(store, page_size=2)
    assert [item["chunk_id"] for item in payloads] == [f"chunk-{i}" for i in range(5)]


def test_FR_RAG_006_scroll_payloads_rejects_stuck_offset():
    class _StuckStore:
        def scroll(self, *, limit, offset=None):
            return [_payload()], "again"

    with pytest.raises(RuntimeError):
        scroll_payloads(_StuckStore(), page_size=1)


class _ScrollClient:
    def __init__(self, payloads):
        self._points = [
            SimpleNamespace(id=f"pt-{i}", payload=payload)
            for i, payload in enumerate(payloads)
        ]

    def collection_exists(self, collection_name):
        return True

    def upsert(self, collection_name, points):
        raise NotImplementedError

    def search(self, collection_name, query_vector, limit=10, query_filter=None):
        raise NotImplementedError

    def delete(self, collection_name, points_selector=None):
        raise NotImplementedError

    def scroll(self, collection_name, *, limit, offset=None):
        start = int(offset) if offset is not None else 0
        page = self._points[start:start + limit]
        next_offset = start + limit
        return page, (str(next_offset) if next_offset < len(self._points) else None)


def test_FR_RAG_006_qdrant_store_scroll_pages_points():
    payloads = [_payload(chunk_id=f"chunk-{i}", version_id=f"ver-{i}") for i in range(3)]
    store = QdrantVectorStore(_ScrollClient(payloads), collection="pivot-chunks")
    page, offset = store.scroll(limit=2)
    assert offset == "2"
    assert [item["chunk_id"] for item in page] == ["chunk-0", "chunk-1"]
    assert page[0]["payload"]["document_id"] == "doc-1"
    assert page[0]["version_id"] == "ver-0"
    rest, offset = store.scroll(limit=2, offset=offset)
    assert offset is None
    assert [item["chunk_id"] for item in rest] == ["chunk-2"]
