"""In-memory Run aggregate used by M05 unit tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime


def run_fingerprint(question: str, scope_type: str, scope_document_id: str | None) -> str:
    raw = f"{question}|{scope_type}|{scope_document_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def synthetic_user_message_id(run_id: str) -> str:
    return f"msg_{run_id.split('_', 1)[-1]}q"


@dataclass
class RunRecord:
    id: str
    conversation_id: str
    message_id: str
    owner_id: str
    question: str
    idempotency_key: str
    fingerprint: str
    scope_type: str = "global"
    scope_document_id: str | None = None
    state: str = "received"
    rewrite_count: int = 0
    clarification_count: int = 0
    error_code: str | None = None
    answer_markdown: str | None = None
    created_at: datetime | None = None


@dataclass
class ClaimRecord:
    id: str
    run_id: str
    text: str
    citation_ids: tuple[str, ...]
    support: str = "unsupported"


@dataclass
class CitationRecord:
    id: str
    run_id: str
    claim_id: str
    document_id: str
    version_id: str
    chunk_id: str
    locator: str = ""


@dataclass
class RunBundle:
    run: RunRecord
    # QA adapters currently return dictionaries; SQL fact records arrive in ND-AGENT-04.
    claims: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
