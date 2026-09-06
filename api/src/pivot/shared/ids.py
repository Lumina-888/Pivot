"""Opaque identifier helpers.

SPEC §5.1/Appendix B.3 requires non-sequential opaque string IDs. The prefix is
an internal type hint; callers must not infer ordering or persistence semantics.
"""

from __future__ import annotations

import re
import secrets

_PREFIXES = {
    "user": "usr",
    "document": "doc",
    "version": "ver",
    "chunk": "chk",
    "generation": "gen",
    "conversation": "conv",
    "message": "msg",
    "run": "run",
    "claim": "clm",
    "citation": "cit",
    "export": "exp",
    "task": "task",
    "audit": "aud",
    "provider_call": "pvc",
    "parse_error": "perr",
}

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,15}_[A-Za-z0-9_-]{20,127}$")


def new_id(kind: str) -> str:
    """Create a cryptographically random, opaque string identifier."""
    prefix = _PREFIXES.get(kind, kind.replace("_", "-").lower())
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,15}", prefix):
        raise ValueError("kind must produce a lowercase identifier prefix")
    return f"{prefix}_{secrets.token_urlsafe(24)}"


def validate_id(value: str, kind: str | None = None) -> bool:
    """Return whether *value* has the opaque ID shape, optionally for *kind*."""
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        return False
    if kind is None:
        return True
    prefix = _PREFIXES.get(kind, kind.replace("_", "-").lower())
    return value.startswith(f"{prefix}_")
