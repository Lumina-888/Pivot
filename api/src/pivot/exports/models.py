"""Export task and persisted-answer views (SPEC §2.2, §3.5, appendix C.5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

EXPORTABLE_RUN_STATES = frozenset({"answered", "uncertain", "refused"})
EXPORT_FORMATS = frozenset({"markdown", "docx"})
SOURCE_TYPES = frozenset({"conversation", "document"})


@dataclass(frozen=True)
class ClaimView:
    id: str
    text: str
    support: str
    citation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CitationView:
    id: str
    document_id: str
    version_id: str
    chunk_id: str
    locator: str = ""
    snippet: str = ""


@dataclass(frozen=True)
class PersistedAnswer:
    """Already-persisted M05 final answer. Hidden fields must never be exported."""

    conversation_id: str
    run_id: str
    state: str
    answer_markdown: str
    claims: tuple[ClaimView, ...] = ()
    citations: tuple[CitationView, ...] = ()
    title: str = "export"
    prompt: str | None = None
    chain_of_thought: str | None = None
    tool_parameters: dict | None = None


@dataclass(frozen=True)
class DocumentExportView:
    document_id: str
    title: str
    version_id: str
    locators: tuple[str, ...] = ()
    display_text: str = ""


@dataclass
class ExportRecord:
    id: str
    owner_id: str
    source_type: str
    source_id: str
    format: str
    state: str
    expires_at: datetime
    created_at: datetime
    filename: str
    storage_key: str | None = None
    error_code: str | None = None
    run_id: str | None = None
    content_type: str | None = None
    extra: dict = field(default_factory=dict)


def created_dto(record: ExportRecord) -> dict[str, str]:
    """POST /exports body: OpenAPI ExportCreated.state is const requested."""

    return {"export_id": record.id, "state": "requested"}


def format_utc(value: datetime) -> str:
    iso = value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return iso


def status_dto(record: ExportRecord, download_url: str | None) -> dict[str, str | None]:
    return {
        "export_id": record.id,
        "state": record.state,
        "download_url": download_url,
        "expires_at": format_utc(record.expires_at),
    }
