"""Fail-closed bindings and conservative verbatim support (FR-QA-002/004).

A matching candidate ID is not support proof. Until DR-004 freezes a semantic
judge, only complete evidence text is accepted; substrings can omit qualifiers.
"""

from __future__ import annotations

from pivot.qa.ports import EvidenceHit


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_bindings(claims: list[dict], citations: list[dict], candidates: dict) -> bool:
    claim_ids: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict) or not _identifier(claim.get("id")):
            return False
        if claim["id"] in claim_ids or not _identifier(claim.get("text")):
            return False
        claim_ids.add(claim["id"])
    by_id: dict[str, dict] = {}
    for citation in citations:
        if not isinstance(citation, dict) or not _identifier(citation.get("id")):
            return False
        if citation["id"] in by_id or not _identifier(citation.get("chunk_id")):
            return False
        hit = candidates.get(citation["chunk_id"])
        if hit is None or citation.get("claim_id") not in claim_ids:
            return False
        if any(citation.get(field) != getattr(hit, field)
               for field in ("document_id", "version_id", "locator")):
            return False
        by_id[citation["id"]] = citation
    used: set[str] = set()
    for claim in claims:
        refs = claim.get("citation_ids")
        if not isinstance(refs, (tuple, list)) or not refs:
            return False
        if any(not _identifier(ref) for ref in refs) or len(set(refs)) != len(refs):
            return False
        for ref in refs:
            citation = by_id.get(ref)
            if citation is None or citation["claim_id"] != claim["id"]:
                return False
            used.add(ref)
    return used == set(by_id)


class CandidateVerifier:
    def verify(
        self, claims: list[dict], citations: list[dict], evidence: tuple[EvidenceHit, ...]
    ) -> str:
        if not isinstance(claims, list) or not isinstance(citations, list):
            return "refused"
        for claim in claims:
            if isinstance(claim, dict):
                claim["support"] = "unsupported"
        if not claims:
            return "uncertain"
        candidates = {hit.chunk_id: hit for hit in evidence}
        if len(candidates) != len(evidence) or not _valid_bindings(claims, citations, candidates):
            return "refused"
        by_id = {citation["id"]: citation for citation in citations}
        for claim in claims:
            sources = [candidates[by_id[ref]["chunk_id"]] for ref in claim["citation_ids"]]
            if not any(claim["text"].strip() == hit.text.strip() for hit in sources):
                return "uncertain"
        # Mark supported only after the entire candidate passes.
        for claim in claims:
            claim["support"] = "supported"
        return "answered"


class FailingVerifier:
    def verify(
        self, claims: list[dict], citations: list[dict], evidence: tuple[EvidenceHit, ...]
    ) -> str:
        raise RuntimeError("verifier unavailable")
