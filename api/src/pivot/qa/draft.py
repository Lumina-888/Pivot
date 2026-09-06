"""Draft answers only from retrieved evidence. Writer cannot widen scope."""

from __future__ import annotations

from pivot.qa.ports import EvidenceHit
from pivot.shared.ids import new_id


def draft_from_evidence(hits: tuple[EvidenceHit, ...]) -> tuple[str, list[dict], list[dict]]:
    if not hits:
        return "", [], []
    claims = []
    citations = []
    sentences = []
    for hit in hits:
        citation_id = new_id("citation")
        claim_id = new_id("claim")
        claims.append(
            {
                "id": claim_id,
                "text": hit.text,
                "citation_ids": (citation_id,),
                "support": "unsupported",
            }
        )
        citations.append(
            {
                "id": citation_id,
                "claim_id": claim_id,
                "document_id": hit.document_id,
                "version_id": hit.version_id,
                "chunk_id": hit.chunk_id,
                "locator": hit.locator,
            }
        )
        sentences.append(hit.text)
    markdown = "。".join(sentences)
    return markdown, claims, citations
