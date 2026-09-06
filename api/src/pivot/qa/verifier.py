"""Citation verifier. Failure must not default to answered (FR-QA-004)."""

from __future__ import annotations

from pivot.qa.ports import EvidenceHit


class CandidateVerifier:
    def verify(
        self,
        claims: list[dict],
        citations: list[dict],
        candidate_chunk_ids: set[str],
    ) -> str:
        if not claims:
            return "uncertain"
        cited_chunks = {item["chunk_id"] for item in citations}
        if not cited_chunks or not cited_chunks.issubset(candidate_chunk_ids):
            for claim in claims:
                claim["support"] = "unsupported"
            return "refused"
        if any(not claim.get("citation_ids") for claim in claims):
            return "refused"
        for claim in claims:
            claim["support"] = "supported"
        return "answered"


class FailingVerifier:
    def verify(
        self, claims: list[dict], citations: list[dict], candidate_chunk_ids: set[str]
    ) -> str:
        raise RuntimeError("verifier unavailable")


def evidence_ids(hits: tuple[EvidenceHit, ...]) -> set[str]:
    return {hit.chunk_id for hit in hits}
