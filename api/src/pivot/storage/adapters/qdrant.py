"""Qdrant payload boundary without importing the Qdrant SDK.

The actual client belongs to an infrastructure/integration module. M03 owns
only the stable payload contract required for rebuildability (SPEC §2.1).
"""

from __future__ import annotations

from collections.abc import Mapping

_REQUIRED_PAYLOAD_KEYS = frozenset({"version_id", "chunk_id"})


def build_payload(
    *, version_id: str, chunk_id: str, text_hash: str | None = None, **metadata
) -> dict:
    """Build a traceable vector payload from persisted identifiers."""
    if not version_id or not chunk_id:
        raise ValueError("version_id and chunk_id are required")
    payload = {"version_id": version_id, "chunk_id": chunk_id}
    if text_hash is not None:
        payload["text_hash"] = text_hash
    payload.update(metadata)
    return payload


def validate_payload(payload: Mapping) -> bool:
    """Validate the minimum Qdrant payload traceability invariant."""
    if not isinstance(payload, Mapping) or not _REQUIRED_PAYLOAD_KEYS <= payload.keys():
        raise ValueError("Qdrant payload must contain version_id and chunk_id")
    if not all(isinstance(payload[key], str) and payload[key] for key in _REQUIRED_PAYLOAD_KEYS):
        raise ValueError("version_id and chunk_id must be non-empty strings")
    return True
