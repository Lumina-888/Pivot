"""Qdrant-backed LlamaIndex: per-library collections, validation, reconcile.

The native collection stays the ingest write path. This module owns the
parallel LlamaIndex collections (same cluster, one collection per
library, named {native}__llama__{library_id}). Nodes are stored under
UUID point ids derived from chunk ids; the chunk id itself travels in
node metadata, and each node carries its document as its reference doc
so a whole document can be dropped with one delete. Every node in a
library collection carries that library in its metadata.

Startup either creates each library collection from the native
payloads, rebuilds it when asked to, or validates and rehydrates the
running index from the existing collections. Runtime ingest changes
reach the index through document-level reconciliation against live
facts (see LlamaIndexSync in the HTTP bootstrap); nothing here trusts
flags baked into payloads for authorization.

The pre-S3 single collection {native}__llama is never opened,
validated, or deleted here: per-library collections are built fresh
from native payloads, and the old collection is left untouched for an
operator to drop after verifying the new ones.
"""

from __future__ import annotations

import logging
import math
import threading
import time
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


def llama_collection_name(native_collection: str, library_id: str) -> str:
    """Per-library collection name: {native}__llama__{library_id}."""
    if not isinstance(library_id, str) or not library_id.strip():
        raise ValueError("library_id must be a non-empty string")
    return f"{native_collection}{_COLLECTION_SUFFIX}__{library_id}"


def llama_folder_collection_name(
    native_collection: str, library_id: str, folder_id: str
) -> str:
    """Per-folder collection name (ADR-018 D3).

    {native}__llama__{library_id}__{folder_id}. Naming only: S1 does
    not wire retrieval to folder collections (that is S2). The default
    folder has no row and keeps the library collection above.
    """
    if not isinstance(library_id, str) or not library_id.strip():
        raise ValueError("library_id must be a non-empty string")
    if not isinstance(folder_id, str) or not folder_id.strip():
        raise ValueError("folder_id must be a non-empty string")
    return f"{native_collection}{_COLLECTION_SUFFIX}__{library_id}__{folder_id}"


def resolve_payload_library(
    payload: Mapping, library_id_for: Callable[[str], str | None] | None
) -> str | None:
    """Resolve which library a native payload belongs to, or None.

    Live document facts win over the payload's own library field: a
    document that moved libraries since ingest still resolves to its
    current library. When live facts cannot resolve the version
    (orphan payload, facts not yet loaded), the payload's own library
    field is the fallback, so startup validation still runs on real
    data and the payload is not dropped merely because facts lag.
    Only a payload with neither live facts nor a usable field
    resolves to None, and is skipped (fail closed); it is never filed
    under a guessed library. Serving stays safe regardless of this
    choice: the authorize hook rechecks every hit against live facts.
    """
    raw = _payload_of(payload)
    version_id = raw.get("version_id")
    if library_id_for is not None and isinstance(version_id, str):
        try:
            resolved = library_id_for(version_id)
        except Exception:
            resolved = None
        if isinstance(resolved, str) and resolved.strip():
            return resolved
    field = raw.get("library_id")
    if isinstance(field, str) and field.strip():
        return field
    return None


def partition_payloads(
    payloads: Iterable[Mapping],
    library_id_for: Callable[[str], str | None] | None,
) -> tuple[dict[str, list[Mapping]], int]:
    """Group payloads by resolved library; count the unresolvable ones."""
    by_library: dict[str, list[Mapping]] = {}
    skipped = 0
    for item in payloads:
        library_id = resolve_payload_library(item, library_id_for)
        if library_id is None:
            skipped += 1
            continue
        by_library.setdefault(library_id, []).append(item)
    return by_library, skipped


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
    """A VectorStoreIndex whose vectors and nodes live in one Qdrant collection."""

    def __init__(
        self,
        index: VectorStoreIndex,
        embed_model: BaseEmbedding,
        *,
        client=None,
        collection: str | None = None,
        library_id: str | None = None,
    ) -> None:
        self._index = index
        self._embed_model = embed_model
        self._client = client
        self._collection = collection
        self._library_id = library_id

    @property
    def index(self) -> VectorStoreIndex:
        return self._index

    @property
    def library_id(self) -> str | None:
        return self._library_id

    @classmethod
    def open(
        cls,
        *,
        client,
        native_collection: str,
        library_id: str,
        embed_model: BaseEmbedding,
        vector_size: int,
        distance: str,
        native_payloads: Iterable[Mapping],
        external_llm_allowed: ExternalLlmLookup,
        library_id_for: Callable[[str], str | None] | None = None,
        rebuild: bool = False,
        hydrate: bool = True,
    ) -> "LlamaQdrantIndex":
        """Open one library's collection, creating or rehydrating it.

        Only payloads resolving to this library are used; everything
        else is left for its own library's collection. A payload that
        cannot be resolved is skipped, never filed here.
        """
        if not isinstance(library_id, str) or not library_id.strip():
            raise ValueError("library_id must be a non-empty string")
        payloads = [
            item
            for item in native_payloads
            if resolve_payload_library(item, library_id_for) == library_id
        ]
        collection = llama_collection_name(native_collection, library_id)
        store = QdrantVectorStore(client=client, collection_name=collection)
        exists = bool(client.collection_exists(collection_name=collection))
        if exists and rebuild:
            client.delete_collection(collection_name=collection)
            exists = False
        index = VectorStoreIndex.from_vector_store(
            store, embed_model=embed_model, store_nodes_override=True
        )
        holder = cls(
            index, embed_model, client=client, collection=collection, library_id=library_id
        )
        if exists:
            _validate_collection(
                client, collection, vector_size=vector_size, native_payloads=payloads
            )
            if hydrate:
                _hydrate(index, client, collection)
            return holder
        _create_collection(client, collection, vector_size=vector_size, distance=distance)
        holder.load(payloads, external_llm_allowed=external_llm_allowed)
        return holder

    @classmethod
    def open_for_sync(cls, **kwargs) -> "LlamaQdrantIndex":
        """Open for collection-level reconcile only (worker processes).

        Validation and the initial load match open(); hydration is
        skipped, so reconcile writes reach the collection while this
        process never serves queries from the returned holder.
        """
        return cls.open(hydrate=False, **kwargs)

    def load(
        self,
        payloads: Iterable[Mapping],
        *,
        external_llm_allowed: ExternalLlmLookup,
    ) -> None:
        """Fill the collection from native payloads (first build/rebuild)."""
        built = build_llama_index(
            self._stamped(payloads),
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
        Payloads are stamped with this collection's library, so a
        document that moved libraries never leaves stale-library nodes
        behind in its new collection.
        """
        # delete_from_docstore=True also clears the docstore ref-doc info,
        # which keeps repeated reconciles of the same document idempotent.
        self._index.delete_ref_doc(document_id, delete_from_docstore=True)
        built = build_llama_index(
            self._stamped(current_payloads),
            embed_model=self._embed_model,
            external_llm_allowed=external_llm_allowed,
        )
        nodes = _built_nodes(built)
        if nodes:
            self._index.insert_nodes(nodes)

    def drop_document(self, document_id: str) -> bool:
        """Remove one document's nodes if this collection holds them.

        Returns True when nodes were dropped, False when this
        collection never held the document (a safe no-op, no Qdrant
        write). The library set uses this to sweep non-target
        collections after a reconcile, which also clears the old
        collection when a document moved libraries.
        """
        if self._index.docstore.get_ref_doc_info(document_id) is None:
            return False
        self._index.delete_ref_doc(document_id, delete_from_docstore=True)
        return True

    def _stamped(self, payloads: Iterable[Mapping]) -> list[dict]:
        """Payload copies stamped with this collection's library.

        Stamping is unconditional: a node stored in a library
        collection always carries that library in its metadata, even
        when the native payload still names a library the document has
        since left. Holders built without a library (legacy direct
        construction only) pass payloads through unstamped.
        """
        stamped: list[dict] = []
        for item in payloads:
            payload = dict(_payload_of(item))
            if self._library_id:
                payload["library_id"] = self._library_id
            stamped.append(payload)
        return stamped

    def refresh_from_collection(self) -> tuple[int, int]:
        """Pull collection-side changes into the serving snapshot.

        Ingest under celery runs in the worker process, which reconciles
        the collection directly; this process only learns about those
        writes by diffing point ids. Vanished points are dropped from the
        docstore, new points are hydrated from their stored payloads.
        The collection itself is never written here. Returns the
        (added, removed) node counts.
        """
        if self._client is None or self._collection is None:
            raise RuntimeError(
                "collection refresh requires the qdrant client and collection name"
            )
        current: set[str] = set()
        offset = None
        while True:
            points, offset = self._client.scroll(
                collection_name=self._collection,
                limit=_SCROLL_PAGE,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            for point in points:
                current.add(str(point.id))
            if offset is None:
                break
        nodes_dict = self._index.index_struct.nodes_dict
        local = {str(key) for key in nodes_dict}
        for point_id in sorted(local - current):
            if point_id in nodes_dict:
                self._index.index_struct.delete(point_id)
            self._index.docstore.delete_document(point_id, raise_error=False)
        added = sorted(current - local)
        if added:
            records = self._client.retrieve(
                collection_name=self._collection,
                ids=added,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                node = metadata_dict_to_node(dict(record.payload or {}))
                if not isinstance(node, TextNode):
                    continue
                stored = node.model_copy(update={"embedding": None})
                self._index.index_struct.add_node(stored, text_id=stored.node_id)
                self._index.docstore.add_documents([stored], allow_update=True)
        return len(added), len(local - current)


class _LiveLibraryIndexes(Mapping):
    """Live view over a library index set's serving indexes.

    The set gains holders lazily (a new library's first document), so
    the retriever must see holders created after assembly; a snapshot
    dict would freeze the serving set at startup and hide new
    libraries until restart. The retriever snapshots this view once
    per query, so a holder added mid-query never breaks iteration.
    """

    def __init__(self, index_set: "LlamaLibraryIndexSet") -> None:
        self._index_set = index_set

    def __getitem__(self, library_id: str) -> VectorStoreIndex:
        return self._index_set._holders[library_id].index

    def __iter__(self):
        return iter(self._index_set._holders)

    def __len__(self) -> int:
        return len(self._index_set._holders)


class LlamaLibraryIndexSet:
    """One LlamaQdrantIndex holder per library, with routed reconcile.

    The set is the unit the API and worker processes build: startup
    partitions the native payloads by resolved library and opens one
    collection per library. Serving indexes come from
    :attr:`indexes`; refresh is a single :meth:`refresh_from_collection`
    call that sums every holder, so the existing interval-gated
    refresher works unchanged. Reconcile is routed by the document's
    current library, and non-target collections are swept with
    :meth:`LlamaQdrantIndex.drop_document`, which also clears the old
    collection when a document moved libraries. A document whose row
    is gone entirely (library unknown) is dropped from every
    collection.
    """

    def __init__(
        self,
        holders: dict[str, LlamaQdrantIndex],
        *,
        client,
        native_collection: str,
        embed_model: BaseEmbedding,
        vector_size: int,
        distance: str,
        external_llm_allowed: ExternalLlmLookup,
        rebuild: bool = False,
        hydrate: bool = True,
    ) -> None:
        self._holders = dict(holders)
        self._client = client
        self._native_collection = native_collection
        self._embed_model = embed_model
        self._vector_size = vector_size
        self._distance = distance
        self._external_llm_allowed = external_llm_allowed
        self._rebuild = rebuild
        self._hydrate = hydrate

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
        library_id_for: Callable[[str], str | None] | None = None,
        rebuild: bool = False,
        hydrate: bool = True,
    ) -> "LlamaLibraryIndexSet":
        payloads = list(native_payloads)
        by_library, skipped = partition_payloads(payloads, library_id_for)
        if skipped:
            logging.getLogger(__name__).warning(
                "skipped %d vector payloads with no resolvable library; "
                "they are indexed in no library collection",
                skipped,
            )
        holders = {
            library_id: LlamaQdrantIndex.open(
                client=client,
                native_collection=native_collection,
                library_id=library_id,
                embed_model=embed_model,
                vector_size=vector_size,
                distance=distance,
                native_payloads=lib_payloads,
                external_llm_allowed=external_llm_allowed,
                library_id_for=library_id_for,
                rebuild=rebuild,
                hydrate=hydrate,
            )
            for library_id, lib_payloads in by_library.items()
        }
        return cls(
            holders,
            client=client,
            native_collection=native_collection,
            embed_model=embed_model,
            vector_size=vector_size,
            distance=distance,
            external_llm_allowed=external_llm_allowed,
            rebuild=rebuild,
            hydrate=hydrate,
        )

    @property
    def holders(self) -> dict[str, LlamaQdrantIndex]:
        return dict(self._holders)

    @property
    def indexes(self) -> Mapping[str, VectorStoreIndex]:
        """Live view of the serving indexes, keyed by library.

        Deliberately not a snapshot: holders are created lazily when
        a new library's first document arrives, and the retriever must
        serve that library without a restart.
        """
        return _LiveLibraryIndexes(self)

    def holder_for(
        self, library_id: str, *, native_payloads: Iterable[Mapping] = ()
    ) -> LlamaQdrantIndex:
        """Return the holder for a library, creating its collection lazily.

        A library with no payloads at startup has no holder yet; its
        first document creates the collection on demand. The current
        payloads are passed for validation context when the collection
        already exists with stale points.
        """
        holder = self._holders.get(library_id)
        if holder is None:
            holder = LlamaQdrantIndex.open(
                client=self._client,
                native_collection=self._native_collection,
                library_id=library_id,
                embed_model=self._embed_model,
                vector_size=self._vector_size,
                distance=self._distance,
                native_payloads=native_payloads,
                external_llm_allowed=self._external_llm_allowed,
                rebuild=False,
                hydrate=self._hydrate,
            )
            self._holders[library_id] = holder
        return holder

    def reconcile_document(
        self,
        document_id: str,
        *,
        library_id: str | None,
        current_payloads: Iterable[Mapping],
        external_llm_allowed: ExternalLlmLookup,
    ) -> None:
        """Reconcile one document in its own library collection only.

        The target collection is reconciled with the current payloads;
        every other collection is swept for the document. When the
        library is unknown (document row gone), every collection is
        swept and nothing is re-added.
        """
        payloads = list(current_payloads)
        target = None
        if library_id:
            target = self.holder_for(library_id, native_payloads=payloads)
            target.reconcile_document(
                document_id,
                current_payloads=payloads,
                external_llm_allowed=external_llm_allowed,
            )
        for holder in self._holders.values():
            if holder is not target:
                holder.drop_document(document_id)

    def drop_document(self, document_id: str) -> None:
        for holder in self._holders.values():
            holder.drop_document(document_id)

    def refresh_from_collection(self) -> tuple[int, int]:
        """Pull every library collection's changes into the snapshots.

        Returns the summed (added, removed) node counts, so the
        interval-gated refresher treats the set like a single holder.
        """
        added = 0
        removed = 0
        for holder in self._holders.values():
            step_added, step_removed = holder.refresh_from_collection()
            added += step_added
            removed += step_removed
        return added, removed


def scroll_library_version_ids(
    client, native_collection: str, library_ids: Iterable[str]
) -> dict[str, tuple[str, ...]]:
    """Version ids held by each named library collection.

    This is the input orphan scanning needs per library: callers pass
    the libraries they know, and only those collections are read. The
    legacy single collection is never consulted. Points whose payload
    cannot be read as a node, or that carry no version id, are skipped.
    """
    found: dict[str, tuple[str, ...]] = {}
    for library_id in library_ids:
        collection = llama_collection_name(native_collection, library_id)
        if not client.collection_exists(collection_name=collection):
            found[library_id] = ()
            continue
        versions: list[str] = []
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
                try:
                    node = metadata_dict_to_node(dict(point.payload or {}))
                except Exception:
                    continue
                if not isinstance(node, TextNode):
                    continue
                version = node.metadata.get("version_id")
                if isinstance(version, str) and version:
                    versions.append(version)
            if offset is None:
                break
        found[library_id] = tuple(versions)
    return found


class CollectionRefresher:
    """Interval-gated, failure-tolerant trigger for snapshot refresh.

    A failed refresh is swallowed so retrieval keeps serving the last
    good snapshot, and the success timestamp is left untouched so the
    next retrieve retries instead of waiting out a whole interval.
    """

    def __init__(
        self,
        holder: LlamaQdrantIndex,
        *,
        interval_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not math.isfinite(interval_seconds) or interval_seconds < 0:
            raise ValueError("interval_seconds must be a finite number >= 0")
        self._holder = holder
        self._interval = interval_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._last_success: float | None = None

    def maybe_refresh(self) -> None:
        if (
            self._last_success is not None
            and self._clock() - self._last_success < self._interval
        ):
            return
        with self._lock:
            if (
                self._last_success is not None
                and self._clock() - self._last_success < self._interval
            ):
                return
            try:
                self._holder.refresh_from_collection()
            except Exception:
                return
            self._last_success = self._clock()


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
