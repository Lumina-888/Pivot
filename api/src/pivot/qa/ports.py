"""Ports consumed by the QA graph. M04 retrieval is not imported from this branch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EvidenceHit:
    chunk_id: str
    document_id: str
    version_id: str
    text: str
    locator: str = ""


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


class Verifier(Protocol):
    def verify(self, claims: list[dict], candidate_chunk_ids: set[str]) -> str: ...


class Classifier(Protocol):
    def needs_clarification(self, question: str, clarification_count: int) -> bool: ...
