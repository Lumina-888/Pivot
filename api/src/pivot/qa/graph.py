"""Deterministic MVP graph (SPEC §7.1). Not LangGraph; see M05 change request."""

from __future__ import annotations

STAGES = (
    "normalize",
    "classify",
    "retrieve",
    "rerank",
    "build_evidence",
    "draft_answer",
    "verify_claims",
    "finalize",
)

MAX_REWRITES = 2
MAX_CLARIFICATIONS = 1
