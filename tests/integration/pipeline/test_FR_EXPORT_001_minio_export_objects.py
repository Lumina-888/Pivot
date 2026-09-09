"""MinIO export object wiring. Public URL stays on PublicDownloadSigner."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "minio-export-objects.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"


def test_GATE_P0_003_not_verified_by_minio_export_objects():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "export" in evidence.lower() or "导出" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
