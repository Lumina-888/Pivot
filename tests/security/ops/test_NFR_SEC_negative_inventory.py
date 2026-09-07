"""Index existing security negatives. Do not modify M01/M04/M06 files."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]


def _tests(relative: str) -> list[str]:
    directory = _ROOT / relative
    return sorted(path.name for path in directory.glob("test_*.py"))


def test_NFR_SEC_auth_export_retrieval_negatives_still_present():
    auth = _tests("tests/security/auth")
    retrieval = _tests("tests/security/retrieval")
    export = _tests("tests/security/export")
    assert auth, "M01 security tests missing"
    assert retrieval, "M04 security tests missing"
    assert export, "M06 security tests missing"
    joined = " ".join(auth + retrieval + export)
    assert "RBAC" in joined or "AUTH" in joined or "auth" in joined.lower()
    assert "EXPORT" in joined or "export" in joined.lower()


def test_GATE_P0_005_not_claimed_verified_by_inventory():
    limits = (_ROOT / "evidence" / "wave2-m11" / "limits.md").read_text(encoding="utf-8")
    assert "GATE-P0-005" in limits
    assert "unverified" in limits.lower()
