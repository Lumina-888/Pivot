"""LlamaIndex dense + existing BM25/RRF behind the QA Retriever port."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import MetadataMode, TextNode

from pivot.qa.ports import EvidenceHit, RetrievalResult
from pivot.retrieval.bm25 import Bm25Retriever
from pivot.retrieval.filters import passes_filters
from pivot.retrieval.models import ChunkRecord, RankedHit, RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.ports import RetrieverError
from pivot.retrieval.service import RetrievalService
from pivot.retrieval.tokenize import Tokenizer

# The caller supplies current resource authorization from its trusted facts.
ResourceAuthorizer = Callable[[str, str, str], bool]


class LlamaIndexRetriever:
    """Retrieve nodes without an LLM; policy and authorization are explicit.

    This adapter uses indexes whose nodes live in the LlamaIndex docstore
    (SimpleVectorStore or an index built with store_nodes_override=True).
    Do not use a cached index as the source of resource authorization.

    A node's chunk id is its node id, unless the node carries a
    ``chunk_id`` metadata entry (the Qdrant-backed index stores nodes
    under UUID point ids and keeps the chunk id in metadata).
    """

    def __init__(
        self,
        index: VectorStoreIndex,
        *,
        policy: RetrievalPolicy,
        tokenizer: Tokenizer,
        bm25_k1: float,
        bm25_b: float,
        dense_score_cutoff: float,
        authorize: ResourceAuthorizer,
    ) -> None:
        if not math.isfinite(dense_score_cutoff):
            raise ValueError("dense_score_cutoff must be finite")
        # Validate BM25 configuration even for an empty index.
        Bm25Retriever(tokenizer, k1=bm25_k1, b=bm25_b)
        self._index = index
        self._policy = policy
        self._tokenizer = tokenizer
        self._bm25_k1 = bm25_k1
        self._bm25_b = bm25_b
        self._cutoff = dense_score_cutoff
        self._authorize = authorize

    def retrieve(
        self,
        question: str,
        *,
        scope_type: str,
        scope_document_id: str | None,
        principal_id: str,
    ) -> RetrievalResult:
        if (
            not isinstance(question, str)
            or not question.strip()
            or not isinstance(principal_id, str)
            or not principal_id.strip()
            or scope_type not in {"global", "document"}
            or (
                scope_type == "document"
                and (not isinstance(scope_document_id, str) or not scope_document_id.strip())
            )
            or (scope_type == "global" and scope_document_id is not None)
        ):
            return RetrievalResult("failed", (), "RESOURCE_FORBIDDEN")
        query = RetrievalQuery(question, principal_id, scope_type, scope_document_id)
        try:
            nodes, corpus = self._eligible_nodes(query)
        except Exception:
            # No raw backend error, node text or credentials enter tool observations.
            return RetrievalResult("failed", (), "RESOURCE_FORBIDDEN")
        if not nodes:
            return RetrievalResult("empty", ())
        dense = _LlamaDense(self._index, nodes, self._cutoff)
        bm25 = Bm25Retriever(self._tokenizer, k1=self._bm25_k1, b=self._bm25_b)
        bm25.add(corpus)
        service = RetrievalService(
            corpus=corpus,
            dense=dense,
            bm25=bm25,
            policy=self._policy,
        )
        result = service.retrieve(query)
        hits = []
        for evidence in result.evidence:
            node = nodes[evidence.chunk_id]
            # Recheck current authorization after retrieval before releasing text.
            try:
                allowed = self._authorize(principal_id, evidence.document_id, evidence.version_id)
            except Exception:
                return RetrievalResult("failed", (), "RESOURCE_FORBIDDEN")
            if allowed is not True:
                continue
            hits.append(
                EvidenceHit(
                    chunk_id=evidence.chunk_id,
                    document_id=evidence.document_id,
                    version_id=evidence.version_id,
                    text=evidence.text,
                    locator=node.metadata["locator"],
                    external_llm_allowed=node.metadata["external_llm_allowed"],
                    index_generation=evidence.index_generation,
                    embedding_model_version=evidence.embedding_model_version,
                    retrieval_config_version=evidence.retrieval_config_version,
                )
            )
        if result.status == "failed":
            return RetrievalResult("failed", (), result.error_code)
        return RetrievalResult("found" if hits else "empty", tuple(hits))

    def resolve_evidence(
        self,
        chunk_id: str,
        *,
        scope_type: str,
        scope_document_id: str | None,
        principal_id: str,
    ) -> EvidenceHit | None:
        """Read current node text only after resource and scope reauthorization."""
        if (
            not principal_id
            or scope_type not in {"global", "document"}
            or (scope_type == "document" and not scope_document_id)
            or (scope_type == "global" and scope_document_id is not None)
        ):
            return None
        node = self._find_node(chunk_id)
        if node is None:
            return None
        record = _record(node)
        query = RetrievalQuery("", principal_id, scope_type, scope_document_id)
        if record is None or not passes_filters(record, query):
            return None
        if self._authorize(principal_id, record.document_id, record.version_id) is not True:
            return None
        return EvidenceHit(
            chunk_id=record.chunk_id,
            document_id=record.document_id,
            version_id=record.version_id,
            text=record.text,
            locator=node.metadata["locator"],
            external_llm_allowed=node.metadata["external_llm_allowed"],
            index_generation=record.index_generation,
            embedding_model_version=record.embedding_model_version,
            retrieval_config_version=record.retrieval_config_version,
        )

    def _find_node(self, chunk_id: str) -> TextNode | None:
        node_ids = self._index.index_struct.nodes_dict.values()
        if chunk_id in node_ids:
            node = self._index.docstore.get_node(chunk_id)
            if isinstance(node, TextNode):
                record = _record(node)
                if record is not None and record.chunk_id == chunk_id:
                    return node
        for node_id in node_ids:
            node = self._index.docstore.get_node(node_id)
            if not isinstance(node, TextNode):
                continue
            record = _record(node)
            if record is not None and record.chunk_id == chunk_id:
                return node
        return None

    def _eligible_nodes(self, query: RetrievalQuery):
        nodes: dict[str, TextNode] = {}
        corpus: list[ChunkRecord] = []
        for node_id in self._index.index_struct.nodes_dict.values():
            node = self._index.docstore.get_node(node_id)
            if not isinstance(node, TextNode):
                continue
            record = _record(node)
            if record is None or not passes_filters(record, query):
                continue
            authorized = self._authorize(query.principal_id, record.document_id, record.version_id)
            if authorized is not True:
                continue
            nodes[record.chunk_id] = node
            corpus.append(record)
        return nodes, tuple(corpus)


class _LlamaDense:
    def __init__(self, index: VectorStoreIndex, nodes: dict[str, TextNode], cutoff: float):
        self._index = index
        self._node_ids = tuple(node.node_id for node in nodes.values())
        self._chunk_by_node = {node.node_id: chunk_id for chunk_id, node in nodes.items()}
        self._cutoff = cutoff

    def search(self, query: str, k: int) -> tuple[RankedHit, ...]:
        try:
            retriever = self._index.as_retriever(
                similarity_top_k=k,
                node_ids=list(self._node_ids),
            )
            hits = retriever.retrieve(query)
            return tuple(
                RankedHit(self._chunk_by_node[hit.node.node_id], float(hit.score), "dense")
                for hit in hits
                if hit.node.node_id in self._chunk_by_node
                and hit.score is not None
                and math.isfinite(hit.score)
                and hit.score > self._cutoff
            )
        except Exception as exc:
            raise RetrieverError("PROVIDER_TEMPORARY_ERROR", "dense retrieval failed") from exc


def _record(node: TextNode) -> ChunkRecord | None:
    metadata = node.metadata
    required = (
        "document_id",
        "version_id",
        "locator",
        "index_generation",
    )
    if any(not isinstance(metadata.get(key), str) or not metadata[key].strip() for key in required):
        return None
    # Provenance versions are opaque strings and may be empty.
    if any(
        not isinstance(metadata.get(key), str)
        for key in ("embedding_model_version", "retrieval_config_version")
    ):
        return None
    if any(metadata.get(key) is not True for key in ("ready", "current", "allowed")):
        return None
    if any(metadata.get(key) is not False for key in ("expired", "deleted")):
        return None
    if type(metadata.get("external_llm_allowed")) is not bool:
        return None
    now = datetime.now(UTC)
    for key in ("effective_from", "effective_to"):
        raw = metadata.get(key)
        if raw is None:
            continue
        try:
            date = datetime.fromisoformat(raw)
            if date.tzinfo is None:
                return None
            if (key == "effective_from" and date > now) or (key == "effective_to" and date <= now):
                return None
        except (TypeError, ValueError):
            return None
    text = node.get_content(metadata_mode=MetadataMode.NONE)
    if not text.strip():
        return None
    chunk_id = metadata.get("chunk_id")
    if not isinstance(chunk_id, str) or not chunk_id.strip():
        chunk_id = node.node_id
    return ChunkRecord(
        chunk_id=chunk_id,
        document_id=metadata["document_id"],
        version_id=metadata["version_id"],
        text=text,
        index_generation=metadata["index_generation"],
        embedding_model_version=metadata["embedding_model_version"],
        retrieval_config_version=metadata["retrieval_config_version"],
    )
