"""Export content boundary and filename hygiene (FR-EXPORT-002/003, SPEC §8.2)."""

from __future__ import annotations

import re

from pivot.exports.models import (
    EXPORTABLE_RUN_STATES,
    DocumentExportView,
    PersistedAnswer,
)

_HIDDEN_FIELDS = frozenset(
    {
        "prompt",
        "system_prompt",
        "chain_of_thought",
        "thinking",
        "thought",
        "tool_parameters",
        "tool_args",
        "hidden_context",
        "secret",
        "api_key",
    }
)

_UNSAFE_FILENAME = re.compile(r"[^\w\u4e00-\u9fff.-]+", re.UNICODE)


def sanitize_filename(name: str, fmt: str) -> str:
    """Strip path segments, traversal and injection characters (SPEC §8.2)."""

    base = str(name or "export").replace("\\", "/").split("/")[-1]
    base = base.replace("..", "")
    cleaned = _UNSAFE_FILENAME.sub("_", base).strip("._") or "export"
    cleaned = cleaned[:120]
    ext = ".md" if fmt == "markdown" else ".docx"
    if not cleaned.lower().endswith(ext):
        cleaned = f"{cleaned}{ext}"
    return cleaned


def build_conversation_payload(answer: PersistedAnswer) -> dict:
    if answer.state not in EXPORTABLE_RUN_STATES:
        raise ValueError("conversation has no persisted final answer")
    payload = {
        "source_type": "conversation",
        "conversation_id": answer.conversation_id,
        "run_id": answer.run_id,
        "state": answer.state,
        "title": answer.title,
        "answer": answer.answer_markdown,
        "claims": [
            {
                "id": claim.id,
                "text": claim.text,
                "support": claim.support,
                "citation_ids": list(claim.citation_ids),
            }
            for claim in answer.claims
        ],
        "citations": [
            {
                "id": citation.id,
                "document_id": citation.document_id,
                "version_id": citation.version_id,
                "chunk_id": citation.chunk_id,
                "locator": citation.locator,
                "snippet": citation.snippet,
            }
            for citation in answer.citations
        ],
    }
    _assert_no_hidden_keys(payload)
    return payload


def build_document_payload(document: DocumentExportView) -> dict:
    payload = {
        "source_type": "document",
        "document_id": document.document_id,
        "version_id": document.version_id,
        "title": document.title,
        "locators": list(document.locators),
        "display_text": document.display_text,
    }
    _assert_no_hidden_keys(payload)
    return payload


def _assert_no_hidden_keys(node: object) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _HIDDEN_FIELDS:
                raise ValueError(f"hidden field leaked into export payload: {key}")
            _assert_no_hidden_keys(value)
    elif isinstance(node, list):
        for item in node:
            _assert_no_hidden_keys(item)
