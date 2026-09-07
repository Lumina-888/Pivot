"""Capacity plan exists; GATE-P0-007 stays unverified."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def test_GATE_P0_007_plan_documents_unverified_tbd():
    plan = (_ROOT / "tests" / "performance" / "PLAN.md").read_text(encoding="utf-8")
    assert "GATE-P0-007" in plan
    assert "unverified" in plan.lower()
    assert "TBD-P0" in plan
    assert "5" in plan
    assert "100" in plan
    limits = (_ROOT / "evidence" / "wave2-m11" / "limits.md").read_text(encoding="utf-8")
    assert "GATE-P0-007" in limits
    assert "unverified" in limits.lower()
