"""Real LlamaIndex retrieval with controlled embeddings, no provider calls."""

import pytest

pytest.importorskip("llama_index.core")

from llama_index.core import VectorStoreIndex  # noqa: E402
from llama_index.core.embeddings import MockEmbedding  # noqa: E402
from llama_index.core.schema import TextNode  # noqa: E402
from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever  # noqa: E402
from pivot.retrieval.policy import RetrievalPolicy  # noqa: E402
from pivot.retrieval.tokenize import SimpleLexTokenizer  # noqa: E402


def make_node(chunk_id="chunk-attendance", **overrides):
    metadata = {
        "document_id": "doc-attendance",
        "version_id": "version-attendance-1",
        "locator": "第一条",
        "ready": True,
        "current": True,
        "allowed": True,
        "expired": False,
        "deleted": False,
        "external_llm_allowed": True,
        "index_generation": "test-generation-1",
        "embedding_model_version": "mock-8",
        "retrieval_config_version": "test-hybrid-1",
    }
    metadata.update(overrides)
    return TextNode(id_=chunk_id, text="一个月内累计迟到三次，视为旷工一天。", extra_info=metadata)


def make_retriever(nodes, authorize=None, **kwargs):
    index = VectorStoreIndex(nodes, embed_model=MockEmbedding(embed_dim=8))
    return LlamaIndexRetriever(
        index,
        policy=RetrievalPolicy(dense_k=5, bm25_k=5, rrf_k=60, evidence_limit=5),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=0.5,
        authorize=authorize or (lambda principal, document, version: principal == "user-1"),
        **kwargs,
    )


def retrieve(retriever, **kwargs):
    args = {"scope_type": "global", "scope_document_id": None, "principal_id": "user-1"}
    args.update(kwargs)
    return retriever.retrieve("迟到三次怎么处理？", **args)


def test_FR_RAG_006_llama_index_returns_real_evidence_identity_and_locator():
    result = retrieve(make_retriever([make_node(external_llm_allowed=False)]))
    assert result.status == "found"
    hit, = result.evidence
    assert (hit.chunk_id, hit.document_id, hit.version_id) == (
        "chunk-attendance", "doc-attendance", "version-attendance-1"
    )
    assert hit.text == "一个月内累计迟到三次，视为旷工一天。"
    assert hit.locator == "第一条"
    assert hit.external_llm_allowed is False
    assert (hit.index_generation, hit.embedding_model_version, hit.retrieval_config_version) == (
        "test-generation-1", "mock-8", "test-hybrid-1",
    )


@pytest.mark.parametrize("metadata", [
    {"ready": False}, {"current": False}, {"allowed": False},
    {"expired": True}, {"deleted": True}, {"ready": "true"},
    {"external_llm_allowed": "false"}, {"version_id": ""},
    {"locator": ""}, {"index_generation": ""},
    {"embedding_model_version": ""}, {"retrieval_config_version": ""},
    {"effective_to": "2000-01-01T00:00:00+00:00"},
    {"effective_from": "2999-01-01T00:00:00+00:00"},
    {"effective_to": "invalid"}, {"effective_to": "2000-01-01T00:00:00"},
])
def test_FR_RAG_002_ineligible_llama_nodes_never_become_evidence(metadata):
    assert retrieve(make_retriever([make_node(**metadata)])).evidence == ()


def test_FR_RAG_003_scope_filters_before_top_k():
    forbidden = [make_node(f"other-{i}", document_id="other-doc") for i in range(6)]
    result = retrieve(
        make_retriever([*forbidden, make_node()]),
        scope_type="document", scope_document_id="doc-attendance",
    )
    assert [hit.chunk_id for hit in result.evidence] == ["chunk-attendance"]


@pytest.mark.parametrize("args", [
    {"scope_type": "all"}, {"scope_type": "shared"},
    {"scope_type": "document"}, {"scope_type": "document", "scope_document_id": " "},
    {"scope_document_id": "doc-attendance"}, {"principal_id": ""},
])
def test_FR_RAG_003_invalid_scope_fails_closed(args):
    result = retrieve(make_retriever([make_node()]), **args)
    assert (result.status, result.error_code, result.evidence) == (
        "failed", "RESOURCE_FORBIDDEN", (),
    )


def test_FR_RBAC_003_principal_authorization_is_rechecked_for_each_request():
    retriever = make_retriever([make_node()])
    assert retrieve(retriever).status == "found"
    assert retrieve(retriever, principal_id="user-2").evidence == ()
    assert retrieve(retriever).status == "found"


def test_FR_RBAC_003_permission_revoked_during_retrieval_is_not_released():
    decisions = iter([True, False])
    retriever = make_retriever([make_node()], authorize=lambda *args: next(decisions))
    assert retrieve(retriever).evidence == ()


def test_FR_RBAC_003_authorization_failure_is_sanitized():
    def unavailable(*args):
        raise RuntimeError("private backend credential")
    result = retrieve(make_retriever([make_node()], authorize=unavailable))
    assert (result.status, result.error_code) == ("failed", "RESOURCE_FORBIDDEN")
    assert "private" not in repr(result)


def test_FR_RAG_006_injected_embeddings_keep_credentials_out_of_serialization():
    from pivot.retrieval.llama_embeddings import PivotEmbedding

    class ControlledEmbedder:
        api_key = "private-api-key"

        def embed(self, texts):
            return [[1.0, 0.0] if "迟到" in text else [0.0, 1.0] for text in texts]

    embedding = PivotEmbedding(ControlledEmbedder(), model_name="controlled-2", dimension=2)
    assert embedding.get_query_embedding("迟到") == [1.0, 0.0]
    assert embedding.get_text_embedding_batch(["迟到", "福利"]) == [[1.0, 0.0], [0.0, 1.0]]
    assert "private-api-key" not in str(embedding.to_dict())
    assert "private-api-key" not in repr(embedding)
