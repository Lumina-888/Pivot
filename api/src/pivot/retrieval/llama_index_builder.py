"""Build the in-memory LlamaIndex from published vector payloads.

The payload is the corpus source: it is the only place where a chunk carries
its full metadata set (locator, eligibility flags, generation and model
versions). Eligibility itself stays with LlamaIndexRetriever; this builder
only validates that every payload is complete and maps it to a node. Any
incomplete payload aborts the whole build so startup fails instead of
running on a partial index.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from llama_index.core import VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.schema import TextNode

# Resolve whether the version that produced a chunk allows external LLM use,
# from live version facts (never from the payload or the index itself).
ExternalLlmAllowed = Callable[[str], bool]

_STRING_FIELDS = (
    "chunk_id",
    "document_id",
    "version_id",
    "text",
    "locator",
    "index_generation",
)
# Provenance versions are opaque strings in the native path and may be
# empty when the publisher had none configured; they must still be
# present and typed as strings.
_VERSION_FIELDS = (
    "embedding_model_version",
    "retrieval_config_version",
)
_FLAG_FIELDS = ("ready", "current", "allowed", "expired", "deleted")
_NODE_METADATA_FIELDS = (
    "document_id",
    "version_id",
    "locator",
    "index_generation",
    "embedding_model_version",
    "retrieval_config_version",
)


def _payload_of(item: Mapping) -> Mapping:
    nested = item.get("payload")
    return nested if isinstance(nested, Mapping) else item


def build_llama_index(
    payloads: Iterable[Mapping],
    *,
    embed_model: BaseEmbedding,
    external_llm_allowed: ExternalLlmAllowed,
) -> VectorStoreIndex:
    nodes: list[TextNode] = []
    for item in payloads:
        payload = _payload_of(item)
        values: dict[str, str] = {}
        for field in _STRING_FIELDS:
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"vector payload is missing required field {field!r}")
            values[field] = value
        for field in _VERSION_FIELDS:
            value = payload.get(field)
            if not isinstance(value, str):
                raise ValueError(f"vector payload is missing required field {field!r}")
            values[field] = value
        metadata: dict[str, object] = {field: values[field] for field in _NODE_METADATA_FIELDS}
        for flag in _FLAG_FIELDS:
            value = payload.get(flag)
            if type(value) is not bool:
                raise ValueError(f"vector payload flag {flag!r} must be a bool")
            metadata[flag] = value
        # Library is optional here but validated when present: the
        # index layer stamps every node stored in a library collection
        # with that collection's library, so per-library nodes are
        # always labeled. Direct builds (evals, single-library
        # corpora) may omit it.
        library_id = payload.get("library_id")
        if library_id is not None:
            if not isinstance(library_id, str) or not library_id.strip():
                raise ValueError("vector payload field 'library_id' must be a non-empty string")
            metadata["library_id"] = library_id
        # Folder likewise (ADR-018 D3): the index layer stamps every
        # node stored in a folder collection with that folder, so
        # per-folder nodes are always labeled. Nodes without a folder
        # fact sit in the default folder, which is the library itself.
        folder_id = payload.get("folder_id")
        if folder_id is not None:
            if not isinstance(folder_id, str) or not folder_id.strip():
                raise ValueError("vector payload field 'folder_id' must be a non-empty string")
            metadata["folder_id"] = folder_id
        for key in ("effective_from", "effective_to"):
            raw = payload.get(key)
            if raw is not None:
                if not isinstance(raw, str):
                    raise ValueError(f"vector payload field {key!r} must be a string")
                metadata[key] = raw
        allowed = external_llm_allowed(values["version_id"])
        if type(allowed) is not bool:
            raise ValueError("external_llm_allowed must return a bool")
        metadata["external_llm_allowed"] = allowed
        nodes.append(
            TextNode(id_=values["chunk_id"], text=values["text"], metadata=metadata)
        )
    return VectorStoreIndex(nodes, embed_model=embed_model)


def scroll_payloads(store, *, page_size: int = 256) -> tuple[Mapping, ...]:
    """Drain every payload from a VectorStore via its scroll port."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    collected: list[Mapping] = []
    offset: str | None = None
    seen: set[str] = set()
    while True:
        page, next_offset = store.scroll(limit=page_size, offset=offset)
        collected.extend(page)
        if next_offset is None:
            return tuple(collected)
        if next_offset == offset or next_offset in seen:
            raise RuntimeError("vector store scroll offset did not advance")
        seen.add(next_offset)
        offset = next_offset
