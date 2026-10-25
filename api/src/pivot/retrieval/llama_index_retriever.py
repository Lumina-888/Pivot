"""LlamaIndex dense + existing BM25/RRF behind the QA Retriever port."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from llama_index.core import VectorStoreIndex
from llama_index.core.indices.vector_store.retrievers import VectorIndexRetriever
from llama_index.core.schema import MetadataMode, TextNode

from pivot.qa.ports import EvidenceHit, RetrievalResult
from pivot.retrieval.bm25 import Bm25Retriever
from pivot.retrieval.filters import passes_filters
from pivot.retrieval.llama_qdrant_index import CollectionRefresher
from pivot.retrieval.models import ChunkRecord, RankedHit, RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.ports import Reranker, RetrieverError
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

    The retriever may serve several indexes at once, one per library
    (S3). When ``visible_libraries_for`` is given, only the libraries
    that principal may see are queried at all: collection selection
    is library enforcement, and the authorize hook stays as defense
    in depth. Without it, every given index is queried, as before.
    Folder indexes (ADR-018 D3) follow the same shape under
    ``visible_folders_for``: only the caller's visible folders are
    queried, and the default folder is the library collection itself,
    never a separate index.

    Document-level exceptions (ADR-017 D1) widen selection but never
    visibility: when ``exception_documents_for`` reports live exception
    documents for a principal, every library-keyed index is selected,
    because the retriever cannot map document ids to libraries without
    a live-fact lookup it does not own. Per-node authorization in
    _eligible_nodes (the exception-aware hook) is what keeps ungranted
    nodes out of the scoring corpus, so selection breadth costs scan
    time only, never leakage.
    """

    def __init__(
        self,
        index: VectorStoreIndex | None = None,
        *,
        indexes: dict[str | None, VectorStoreIndex] | None = None,
        policy: RetrievalPolicy,
        tokenizer: Tokenizer,
        bm25_k1: float,
        bm25_b: float,
        dense_score_cutoff: float,
        authorize: ResourceAuthorizer,
        reranker: Reranker | None = None,
        refresher: CollectionRefresher | None = None,
        visible_libraries_for: Callable[[str], tuple[str, ...]] | None = None,
        exception_documents_for: Callable[[str], tuple[str, ...]] | None = None,
        folder_indexes: Mapping[str, VectorStoreIndex] | None = None,
        visible_folders_for: Callable[[str], tuple[str, ...]] | None = None,
    ) -> None:
        if index is not None and indexes is not None:
            raise ValueError("pass either index or indexes, not both")
        if indexes is None:
            if index is None:
                raise ValueError("a retriever needs an index")
            indexes = {None: index}
        if not math.isfinite(dense_score_cutoff):
            raise ValueError("dense_score_cutoff must be finite")
        # Validate BM25 configuration even for an empty index.
        Bm25Retriever(tokenizer, k1=bm25_k1, b=bm25_b)
        # Stored as given, not copied: a library set's indexes mapping
        # is a live view, and lazily created libraries must become
        # visible without a restart. Selection snapshots it per query.
        self._indexes = indexes
        self._policy = policy
        self._tokenizer = tokenizer
        self._bm25_k1 = bm25_k1
        self._bm25_b = bm25_b
        self._cutoff = dense_score_cutoff
        self._authorize = authorize
        self._reranker = reranker
        self._refresher = refresher
        self._visible_libraries_for = visible_libraries_for
        self._exception_documents_for = exception_documents_for
        # Folder collections (ADR-018 D3): stored as given, not copied,
        # like _indexes: a library set's folder_indexes mapping is a
        # live view, and a lazily created folder must become visible
        # without a restart. Folder ids never equal library ids (the
        # folder service refuses the collision at creation), so the
        # merged selection dict cannot drop a library key.
        self._folder_indexes = folder_indexes
        self._visible_folders_for = visible_folders_for

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
        if self._refresher is not None:
            self._refresher.maybe_refresh()
        try:
            nodes, corpus, per_index = self._eligible_nodes(query)
        except Exception:
            # No raw backend error, node text or credentials enter tool observations.
            return RetrievalResult("failed", (), "RESOURCE_FORBIDDEN")
        if not nodes:
            return RetrievalResult("empty", ())
        dense = _LlamaDense(per_index, self._cutoff)
        bm25 = Bm25Retriever(self._tokenizer, k1=self._bm25_k1, b=self._bm25_b)
        bm25.add(corpus)
        service = RetrievalService(
            corpus=corpus,
            dense=dense,
            bm25=bm25,
            policy=self._policy,
            reranker=self._reranker,
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
        node = self._find_node(chunk_id, principal_id=principal_id)
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

    def _selected_indexes(
        self, principal_id: str
    ) -> dict[str | None, VectorStoreIndex]:
        """Indexes this principal may be served from, by library and folder.

        No resolver means every index (the pre-S3 single-index shape);
        a legacy single index has no library key, so it is also served
        whole and the authorize hook remains its enforcement. A resolver
        failure denies everything (fail closed) rather than falling
        back to all libraries. The returned dict is a per-query
        snapshot, so a holder added mid-query never breaks iteration.

        With live exception documents, every library-keyed index is
        selected: an exception document's library is not derivable from
        its id inside the retriever, so wholesale exclusion would hide
        granted documents. The per-node authorize hook (exception-aware)
        still filters every node before it reaches the corpus, so the
        wider selection cannot leak ungranted documents. An exception
        resolver failure only drops the exception widening; library
        visibility is unaffected.

        Folder indexes (ADR-018 D3) follow the same shape: without a
        folder resolver every folder index is served; with one, only
        the caller's visible folders are. Exceptions widen the folder
        selection too, because an exception document's folder is not
        derivable from its id either, and the hook still filters every
        node. Without folder_indexes the selection is exactly the
        library selection, so pre-folder callers are untouched.
        """
        if self._visible_libraries_for is None:
            library_selected = dict(self._indexes)
        elif not any(key is not None for key in self._indexes):
            library_selected = dict(self._indexes)
        else:
            try:
                visible = set(self._visible_libraries_for(principal_id))
            except Exception:
                # A library resolver failure denies everything, as
                # before: folder selection does not run either.
                return {}
            if self._exception_documents_for is not None:
                try:
                    exceptions = self._exception_documents_for(principal_id)
                except Exception:
                    exceptions = ()
                if exceptions:
                    library_selected = dict(self._indexes)
                else:
                    library_selected = {
                        key: index
                        for key, index in self._indexes.items()
                        if key in visible
                    }
            else:
                library_selected = {
                    key: index
                    for key, index in self._indexes.items()
                    if key in visible
                }
        if self._folder_indexes is None:
            return library_selected
        if self._visible_folders_for is None:
            return {**library_selected, **dict(self._folder_indexes)}
        try:
            visible_folders = set(self._visible_folders_for(principal_id))
        except Exception:
            return library_selected
        if self._exception_documents_for is not None:
            try:
                exceptions = self._exception_documents_for(principal_id)
            except Exception:
                exceptions = ()
            if exceptions:
                return {**library_selected, **dict(self._folder_indexes)}
        return {
            **library_selected,
            **{
                key: index
                for key, index in self._folder_indexes.items()
                if key in visible_folders
            },
        }

    def _find_node(self, chunk_id: str, *, principal_id: str) -> TextNode | None:
        for index in self._selected_indexes(principal_id).values():
            node_ids = index.index_struct.nodes_dict.values()
            if chunk_id in node_ids:
                node = index.docstore.get_node(chunk_id)
                if isinstance(node, TextNode):
                    record = _record(node)
                    if record is not None and record.chunk_id == chunk_id:
                        return node
            for node_id in node_ids:
                node = index.docstore.get_node(node_id)
                if not isinstance(node, TextNode):
                    continue
                record = _record(node)
                if record is not None and record.chunk_id == chunk_id:
                    return node
        return None

    def _eligible_nodes(self, query: RetrievalQuery):
        nodes: dict[str, TextNode] = {}
        corpus: list[ChunkRecord] = []
        per_index: list[tuple[VectorStoreIndex, dict[str, TextNode]]] = []
        for index in self._selected_indexes(query.principal_id).values():
            index_nodes: dict[str, TextNode] = {}
            for node_id in index.index_struct.nodes_dict.values():
                node = index.docstore.get_node(node_id)
                if not isinstance(node, TextNode):
                    continue
                record = _record(node)
                if record is None or not passes_filters(record, query):
                    continue
                authorized = self._authorize(
                    query.principal_id, record.document_id, record.version_id
                )
                if authorized is not True:
                    continue
                index_nodes[record.chunk_id] = node
                if record.chunk_id not in nodes:
                    nodes[record.chunk_id] = node
                    corpus.append(record)
            per_index.append((index, index_nodes))
        return nodes, tuple(corpus), per_index


class _LlamaDense:
    """Dense search merged across the selected indexes.

    Each index is searched at its own top-k and the hits are merged:
    per-index top-k union is exactly the global top-k, because any hit
    below its own index's top-k has k better hits in that index alone.
    """

    def __init__(
        self,
        sources: list[tuple[VectorStoreIndex, dict[str, TextNode]]],
        cutoff: float,
    ) -> None:
        self._sources = sources
        self._cutoff = cutoff

    def search(self, query: str, k: int) -> tuple[RankedHit, ...]:
        try:
            ranked: list[RankedHit] = []
            for index, nodes in self._sources:
                if not nodes:
                    continue
                # Construct the retriever directly: index.as_retriever()
                # forwards node_ids itself on llama-index-core 0.11.23, so
                # passing node_ids through it raises TypeError and every
                # dense search silently degraded to no hits (FR-RAG-009).
                retriever = VectorIndexRetriever(
                    index=index,
                    similarity_top_k=k,
                    node_ids=[node.node_id for node in nodes.values()],
                )
                chunk_by_node = {
                    node.node_id: chunk_id for chunk_id, node in nodes.items()
                }
                hits = retriever.retrieve(query)
                for hit in hits:
                    if hit.node.node_id not in chunk_by_node:
                        continue
                    if hit.score is None or not math.isfinite(hit.score):
                        continue
                    if hit.score <= self._cutoff:
                        continue
                    ranked.append(
                        RankedHit(chunk_by_node[hit.node.node_id], float(hit.score), "dense")
                    )
            # ANN traversal order varies between runs; make tie order a
            # pure function of (score, chunk_id) so fusion ranks are
            # stable across runs and environments.
            ranked.sort(key=lambda hit: (-hit.score, hit.chunk_id))
            return tuple(ranked)
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
    library_id = metadata.get("library_id")
    folder_id = metadata.get("folder_id")
    return ChunkRecord(
        chunk_id=chunk_id,
        document_id=metadata["document_id"],
        version_id=metadata["version_id"],
        text=text,
        index_generation=metadata["index_generation"],
        embedding_model_version=metadata["embedding_model_version"],
        retrieval_config_version=metadata["retrieval_config_version"],
        library_id=library_id if isinstance(library_id, str) else "",
        # Nodes in a folder collection carry their folder id (stamped
        # by the folder holder); anything else reads as the default
        # folder, which is the library itself.
        folder_id=folder_id if isinstance(folder_id, str) else None,
    )
