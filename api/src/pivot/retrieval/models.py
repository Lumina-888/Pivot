"""Retrieval request/result types (FR-SEARCH, FR-RAG)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    version_id: str
    document_id: str
    text: str
    title: str = ""
    space: str = ""
    tags: tuple[str, ...] = ()
    kind: str = "pdf"
    ready: bool = True
    current: bool = True
    allowed: bool = True
    expired: bool = False
    deleted: bool = False
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    version_label: str = "v1"
    index_generation: str = ""
    embedding_model_version: str = ""
    retrieval_config_version: str = ""


@dataclass(frozen=True)
class RetrievalQuery:
    text: str
    principal_id: str
    scope_type: str = "global"
    scope_document_id: str | None = None
    space: str | None = None
    tags: tuple[str, ...] = ()
    prompt: str = ""


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    document_id: str
    version_id: str
    text: str
    score: float
    index_generation: str
    embedding_model_version: str
    retrieval_config_version: str
    version_label: str = ""
    effective_from: datetime | None = None


@dataclass(frozen=True)
class VersionConflict:
    document_id: str
    versions: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalOutcome:
    status: str
    evidence: tuple[Evidence, ...]
    warnings: tuple[str, ...] = ()
    conflicts: tuple[VersionConflict, ...] = ()
    error_code: str | None = None


@dataclass(frozen=True)
class SearchHit:
    document_id: str
    version_id: str
    title: str
    snippet: str
    space: str
    index_generation: str
    embedding_model_version: str
    retrieval_config_version: str


@dataclass(frozen=True)
class AskIntent:
    question: str
    scope_type: str
    scope_document_id: str | None = None


@dataclass(frozen=True)
class RankedHit:
    chunk_id: str
    score: float
    source: str = ""


@dataclass
class ProviderCallNote:
    provider: str
    operation: str
    status: str
    error_code: str | None = None
    metadata: dict = field(default_factory=dict)
