"""Ports consumed by the QA graph. M04 retrieval is not imported from this branch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class EvidenceHit:
    chunk_id: str
    document_id: str
    version_id: str
    text: str
    locator: str = ""
    external_llm_allowed: bool = False
    index_generation: str = ""
    embedding_model_version: str = ""
    retrieval_config_version: str = ""


@dataclass(frozen=True)
class RetrievalResult:
    status: str
    evidence: tuple[EvidenceHit, ...]
    error_code: str | None = None


class Retriever(Protocol):
    def retrieve(
        self,
        question: str,
        *,
        scope_type: str,
        scope_document_id: str | None,
        principal_id: str,
    ) -> RetrievalResult: ...


@runtime_checkable
class EvidenceResolver(Protocol):
    """Optional retrieval capability for reading a candidate against current facts."""

    def resolve_evidence(
        self,
        chunk_id: str,
        *,
        scope_type: str,
        scope_document_id: str | None,
        principal_id: str,
    ) -> EvidenceHit | None: ...


class Verifier(Protocol):
    def verify(
        self, claims: list[dict], citations: list[dict], evidence: tuple[EvidenceHit, ...]
    ) -> str: ...


class Classifier(Protocol):
    def needs_clarification(self, question: str, clarification_count: int) -> bool: ...


class DraftWriter(Protocol):
    def draft(
        self, question: str, hits: tuple[EvidenceHit, ...]
    ) -> tuple[str, list[dict], list[dict]]: ...
