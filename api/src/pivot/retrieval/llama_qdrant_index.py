"""Qdrant-backed LlamaIndex: persistent collection, validation, reconcile.

The native collection stays the ingest write path. This module owns the
parallel LlamaIndex collection (same cluster, isolated name). Nodes are
stored under UUID point ids derived from chunk ids; the chunk id itself
travels in node metadata, and each node carries its document as its
reference doc so a whole document can be dropped with one delete.

Startup either creates the collection from the native payloads, rebuilds
it when asked to, or validates and rehydrates the running index from the
existing collection. Runtime ingest changes reach the index through
document-level reconciliation against live facts (see LlamaIndexSync in
the HTTP bootstrap); nothing here trusts flags baked into payloads for
authorization.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from uuid import NAMESPACE_URL, uuid5

from llama_index.core import VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import (
    MetadataMode,
    NodeRelationship,
    ObjectType,
    RelatedNodeInfo,
    TextNode,
)
from llama_index.core.vector_stores.utils import metadata_dict_to_node
from llama_index.vector_stores.qdrant import QdrantVectorStore

from pivot.retrieval.llama_index_builder import _payload_of, build_llama_index

_COLLECTION_SUFFIX = "__llama"
_SCROLL_PAGE = 256

ExternalLlmLookup = Callable[[str], bool]


def llama_collection_name(native_collection: str) -> str:
    return f"{native_collection}{_COLLECTION_SUFFIX}"


def point_id_for(chunk_id: str) -> str:
    """Same UUID mapping the native Qdrant adapter uses for chunk points."""
    return str(uuid5(NAMESPACE_URL, f"pivot:chunk:{chunk_id}"))


def _persistent_node(node: TextNode) -> TextNode:
    metadata = dict(node.metadata)
    chunk_id = node.node_id
    metadata["chunk_id"] = chunk_id
    return TextNode(
        id_=point_id_for(chunk_id),
        text=node.get_content(metadata_mode=MetadataMode.NONE),
        metadata=metadata,
        embedding=node.embedding,
        relationships={
            NodeRelationship.SOURCE: RelatedNodeInfo(
                node_id=str(metadata["document_id"]), node_type=ObjectType.DOCUMENT
            )
        },
    )


def _built_nodes(index: VectorStoreIndex) -> list[TextNode]:
    """Persistent-form nodes for an in-memory build, embeddings attached."""
    data = index.storage_context.vector_store.data  # SimpleVectorStore data
    embeddings = getattr(data, "embedding_dict", {})
    nodes = []
    for node in index.docstore.docs.values():
        if not isinstance(node, TextNode):
            continue
        if node.embedding is None and node.node_id in embeddings:
            node = node.model_copy(update={"embedding": list(embeddings[node.node_id])})
        nodes.append(_persistent_node(node))
    return nodes


class LlamaQdrantIndex:
    """A VectorStoreIndex whose vectors and nodes live in Qdrant."""

    def __init__(self, index: VectorStoreIndex, embed_model: BaseEmbedding) -> None:
        self._index = index
        self._embed_model = embed_model

    @property
    def index(self) -> VectorStoreIndex:
        return self._index

    @classmethod
    def open(
        cls,
        *,
        client,
        native_collection: str,
        embed_model: BaseEmbedding,
        vector_size: int,
        distance: str,
        native_payloads: Iterable[Mapping],
        external_llm_allowed: ExternalLlmLookup,
        rebuild: bool = False,
    ) -> "LlamaQdrantIndex":
        payloads = list(native_payloads)
        collection = llama_collection_name(native_collection)
        store = QdrantVectorStore(client=client, collection_name=collection)
        exists = bool(client.collection_exists(collection_name=collection))
        if exists and rebuild:
            client.delete_collection(collection_name=collection)
            exists = False
        index = VectorStoreIndex.from_vector_store(
            store, embed_model=embed_model, store_nodes_override=True
        )
        holder = cls(index, embed_model)
        if exists:
            _validate_collection(
                client, collection, vector_size=vector_size, native_payloads=payloads
            )
            _hydrate(index, client, collection)
            return holder
        _create_collection(client, collection, vector_size=vector_size, distance=distance)
        holder.load(payloads, external_llm_allowed=external_llm_allowed)
        return holder

    def load(
        self,
        payloads: Iterable[Mapping],
        *,
        external_llm_allowed: ExternalLlmLookup,
    ) -> None:
        """Fill the collection from native payloads (first build/rebuild)."""
        built = build_llama_index(
            payloads,
            embed_model=self._embed_model,
            external_llm_allowed=external_llm_allowed,
        )
        nodes = _built_nodes(built)
        if nodes:
            self._index.insert_nodes(nodes)

    def reconcile_document(
        self,
        document_id: str,
        *,
        current_payloads: Iterable[Mapping],
        external_llm_allowed: ExternalLlmLookup,
    ) -> None:
        """Align one document's nodes with live facts.

        Every node of the document is dropped first, then the current
        version's nodes are re-added from the native payloads. The call
        is idempotent: running it twice leaves the same state.
        """
        # delete_from_docstore=True also clears the docstore ref-doc info,
        # which keeps repeated reconciles of the same document idempotent.
        self._index.delete_ref_doc(document_id, delete_from_docstore=True)
        built = build_llama_index(
            current_payloads,
            embed_model=self._embed_model,
            external_llm_allowed=external_llm_allowed,
        )
        nodes = _built_nodes(built)
        if nodes:
            self._index.insert_nodes(nodes)


def _create_collection(client, collection: str, *, vector_size: int, distance: str) -> None:
    from qdrant_client.http import models as rest

    distances = {
        "cosine": rest.Distance.COSINE,
        "dot": rest.Distance.DOT,
        "euclid": rest.Distance.EUCLID,
    }
    resolved = distances.get(str(distance).strip().lower())
    if resolved is None:
        raise RuntimeError(
            f"unsupported PIVOT_QDRANT_DISTANCE={distance!r} for the LlamaIndex "
            "collection; use cosine, dot or euclid"
        )
    client.create_collection(
        collection_name=collection,
        vectors_config=rest.VectorParams(size=vector_size, distance=resolved),
    )


def _collection_vector_size(client, collection: str) -> int | None:
    info = client.get_collection(collection_name=collection)
    vectors = info.config.params.vectors
    if isinstance(vectors, dict):
        params = vectors.get("") or next(iter(vectors.values()), None)
    else:
        params = vectors
    return None if params is None else params.size


def _validate_collection(
    client,
    collection: str,
    *,
    vector_size: int,
    native_payloads: list[Mapping],
) -> None:
    size = _collection_vector_size(client, collection)
    if size != vector_size:
        raise RuntimeError(
            f"LlamaIndex collection {collection!r} has vector size {size}, "
            f"expected {vector_size}; restart with PIVOT_LLAMA_INDEX_REBUILD=1 "
            "to rebuild it"
        )
    points, _ = client.scroll(
        collection_name=collection,
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if not points:
        return
    if not native_payloads:
        raise RuntimeError(
            f"LlamaIndex collection {collection!r} is not empty but the native "
            "collection is; restart with PIVOT_LLAMA_INDEX_REBUILD=1 to rebuild it"
        )
    node = metadata_dict_to_node(dict(points[0].payload or {}))
    actual = node.metadata.get("embedding_model_version")
    expected = {
        value
        for payload in native_payloads
        if isinstance(
            value := _payload_of(payload).get("embedding_model_version"), str
        )
        and value
    }
    if expected and actual not in expected:
        raise RuntimeError(
            f"LlamaIndex collection {collection!r} holds embedding model "
            f"version {actual!r}, current payloads use {sorted(expected)!r}; "
            "restart with PIVOT_LLAMA_INDEX_REBUILD=1 to rebuild it"
        )


def _hydrate(index: VectorStoreIndex, client, collection: str) -> None:
    """Repopulate docstore and index struct from the stored points.

    Embeddings stay in Qdrant; the docstore copies carry none, mirroring
    how the insert path stores nodes when the vector store keeps text.
    """
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            limit=_SCROLL_PAGE,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            node = metadata_dict_to_node(dict(point.payload or {}))
            if not isinstance(node, TextNode):
                continue
            stored = node.model_copy(update={"embedding": None})
            index.index_struct.add_node(stored, text_id=stored.node_id)
            index.docstore.add_documents([stored], allow_update=True)
        if offset is None:
            return
