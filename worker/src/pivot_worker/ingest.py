"""Ingest pipeline: parse → chunk → embed → index. State transitions stay with M02."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from pivot.chunking import ChunkingPolicy, ChunkSplitter
from pivot.parsing import ParseError, ParserRegistry
from pivot.parsing.errors import RETRYABLE_CODES
from pivot.retrieval.ports import RetrieverError
from pivot.shared.ids import new_id

from pivot_worker.embedding import EmbeddingPort, FakeEmbedding, assert_dimension
from pivot_worker.index import IndexPublisher
from pivot_worker.isolation import isolated_workspace
from pivot_worker.output import worker_failed, worker_insufficient, worker_ok


class IngestSink(Protocol):
    """M02-facing callbacks. M07 must not implement the document state machine."""

    def on_parse_ok(self, version_id: str) -> None: ...

    def on_parse_error(self, version_id: str, code: str) -> None: ...

    def on_chunks(self, version_id: str, texts: list[str], message_id: str) -> list[str]: ...

    def on_embedding_ok(self, version_id: str) -> None: ...

    def on_embedding_error(self, version_id: str) -> None: ...

    def on_publish(self, version_id: str) -> None: ...


@dataclass
class RecordingSink:
    parse_ok: list[str] = field(default_factory=list)
    parse_errors: list[tuple[str, str]] = field(default_factory=list)
    chunk_ids: dict[str, list[str]] = field(default_factory=dict)
    published: list[str] = field(default_factory=list)

    def on_parse_ok(self, version_id: str) -> None:
        self.parse_ok.append(version_id)

    def on_parse_error(self, version_id: str, code: str) -> None:
        self.parse_errors.append((version_id, code))

    def on_chunks(self, version_id: str, texts: list[str], message_id: str) -> list[str]:
        existing = self.chunk_ids.get(message_id)
        if existing is not None:
            return existing
        ids = [new_id("chunk") for _ in texts]
        self.chunk_ids[message_id] = ids
        return ids

    def on_embedding_ok(self, version_id: str) -> None:
        return None

    def on_embedding_error(self, version_id: str) -> None:
        return None

    def on_publish(self, version_id: str) -> None:
        self.published.append(version_id)


@dataclass
class IngestRequest:
    version_id: str
    kind: str
    content: bytes
    message_id: str
    embedding_model_version: str = "fake-embed-v1"
    dimension: int = 8
    document_id: str = ""
    title: str = ""
    space: str = ""
    tags: tuple[str, ...] = ()
    retrieval_config_version: str = ""


class IngestWorker:
    def __init__(
        self,
        *,
        parsers: ParserRegistry | None = None,
        splitter: ChunkSplitter | None = None,
        embedding: EmbeddingPort | None = None,
        index: IndexPublisher | None = None,
        sink: IngestSink | None = None,
        dimension: int = 8,
    ) -> None:
        self._parsers = parsers or ParserRegistry()
        self._splitter = splitter or ChunkSplitter(
            ChunkingPolicy(max_chars=80, overlap_chars=8)
        )
        self._embedding = embedding or FakeEmbedding(dimension=dimension)
        self._index = index or IndexPublisher()
        self._sink = sink or RecordingSink()
        self._dimension = dimension
        self._results: dict[str, dict[str, Any]] = {}

    def run(self, request: IngestRequest) -> dict[str, Any]:
        cached = self._results.get(request.message_id)
        if cached is not None:
            return cached
        with isolated_workspace():
            result = self._run(request)
        self._results[request.message_id] = result
        return result

    def _run(self, request: IngestRequest) -> dict[str, Any]:
        generation_id = new_id("generation")
        try:
            parsed = self._parsers.parse(request.kind, request.content)
        except ParseError as error:
            self._sink.on_parse_error(request.version_id, error.code)
            return worker_failed(error.code, "parse")
        if not parsed.text.strip():
            self._sink.on_parse_error(request.version_id, "EMPTY_TEXT")
            return worker_insufficient("parse")
        self._sink.on_parse_ok(request.version_id)
        drafts = self._splitter.split(parsed.blocks)
        if not drafts:
            self._sink.on_parse_error(request.version_id, "EMPTY_TEXT")
            return worker_insufficient("chunk")
        chunk_ids = self._sink.on_chunks(
            request.version_id, [draft.text for draft in drafts], request.message_id
        )
        try:
            vectors = self._embedding.embed([draft.text for draft in drafts])
            assert_dimension(vectors, self._dimension)
        except (ParseError, RetrieverError) as error:
            self._sink.on_embedding_error(request.version_id)
            self._index.abort(generation_id)
            return worker_failed(error.code, "embed")
        self._sink.on_embedding_ok(request.version_id)
        self._index.start(generation_id, self._dimension, request.embedding_model_version)
        for chunk_id, draft, vector in zip(chunk_ids, drafts, vectors, strict=True):
            self._index.add_vector(
                generation_id,
                version_id=request.version_id,
                chunk_id=chunk_id,
                vector=vector,
                text_hash=draft.text_hash,
                document_id=request.document_id,
                text=draft.text,
                title=request.title,
                space=request.space,
                tags=request.tags,
                ready=True,
                current=True,
                allowed=True,
                expired=False,
                deleted=False,
                index_generation=generation_id,
                embedding_model_version=request.embedding_model_version,
                retrieval_config_version=request.retrieval_config_version,
                locator=draft.locator,
            )
        try:
            published = self._index.publish(generation_id)
        except ParseError as error:
            self._index.abort(generation_id)
            return worker_failed(error.code, "index")
        self._sink.on_publish(request.version_id)
        return worker_ok(
            {
                "version_id": request.version_id,
                "generation_id": published.id,
                "chunk_ids": chunk_ids,
                "locators": [draft.locator for draft in drafts],
                "retryable": False,
            },
            "index",
        )

    def is_retryable(self, error_code: str) -> bool:
        return error_code in RETRYABLE_CODES
