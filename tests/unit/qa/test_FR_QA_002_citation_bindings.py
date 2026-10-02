"""Complete citation bindings are a prerequisite, not support proof."""

from __future__ import annotations

import pytest
from pivot.qa.draft import draft_from_evidence
from pivot.qa.ports import EvidenceHit
from pivot.qa.verifier import CandidateVerifier

HIT = EvidenceHit("chk_a", "doc_a", "ver_a", "迟到三次以上记为旷工。", "page=1")


@pytest.mark.parametrize(
    "mutation",
    ["dangling", "outside", "document", "version", "locator", "reverse",
     "duplicate_citation", "duplicate_claim", "orphan", "empty_reference", "missing_id"],
)
def test_FR_QA_002_dangling_citation_rejected(mutation):
    _, claims, citations = draft_from_evidence((HIT,))
    if mutation == "dangling":
        claims[0]["citation_ids"] = ("cit_unknown",)
    elif mutation == "outside":
        citations[0]["chunk_id"] = "chk_other_run"
    elif mutation in {"document", "version", "locator"}:
        field = mutation + "_id" if mutation != "locator" else mutation
        citations[0][field] = "forged"
    elif mutation == "reverse":
        citations[0]["claim_id"] = "clm_other"
    elif mutation == "duplicate_citation":
        citations.append(dict(citations[0]))
    elif mutation == "duplicate_claim":
        claims.append(dict(claims[0]))
    elif mutation == "orphan":
        citations.append({**citations[0], "id": "cit_orphan"})
    elif mutation == "empty_reference":
        claims[0]["citation_ids"] = ()
    elif mutation == "missing_id":
        del citations[0]["id"]
    assert CandidateVerifier().verify(claims, citations, (HIT,)) == "refused"
