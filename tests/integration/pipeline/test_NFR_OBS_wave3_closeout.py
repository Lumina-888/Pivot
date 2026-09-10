"""Wave 3 fixture close-out. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_CLOSEOUT = _ROOT / "evidence" / "wave3-m11" / "wave3-closeout.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_MATRIX = _ROOT / "spec" / "acceptance" / "matrix.md"
_CHANGE = _ROOT / "progress" / "changes" / "20260910-M11-wave3-closeout.md"


def _gate_line(text: str, gate: int) -> str:
    needle = f"GATE-P0-00{gate}"
    return next(item for item in text.splitlines() if needle in item)


def _assert_unverified_gate(text: str, gate: int) -> None:
    line = _gate_line(text, gate)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")


def test_NFR_OBS_wave3_closeout_records_a1_complete():
    text = _CLOSEOUT.read_text(encoding="utf-8")
    for ticket in ("ND-W3-01", "ND-W3-02", "ND-W3-12"):
        assert ticket in text
    assert "A1" in text
    assert "夹具" in text
    assert "celery" in text.lower() or "Celery" in text
    assert "Qdrant" in text


def test_NFR_OBS_wave3_closeout_lists_remaining_a2():
    text = _CLOSEOUT.read_text(encoding="utf-8")
    for ticket in ("ND-W3-04", "ND-W3-07"):
        assert ticket in text
    assert "导出" in text
    assert "PATCH" in text or "角色" in text


def test_GATE_P0_wave3_closeout_marks_all_gates_unverified():
    closeout = _CLOSEOUT.read_text(encoding="utf-8")
    limits = _LIMITS.read_text(encoding="utf-8")
    for gate in range(1, 9):
        _assert_unverified_gate(closeout, gate)
        _assert_unverified_gate(limits, gate)
    assert closeout.lower().count("unverified") >= 8


def test_GATE_P0_not_verified_by_wave3_integrated():
    text = _CLOSEOUT.read_text(encoding="utf-8")
    assert "wave-3-integrated" in text
    assert "不等于" in text
    assert "P0" in text
    assert "不得" in text
    for line in text.splitlines():
        if "GATE-P0-00" in line:
            assert "unverified" in line.lower()
            assert "verified" not in line.lower().replace("unverified", "")


def test_NFR_OBS_wave3_matrix_is_fixture_baseline_not_gate_verified():
    matrix = _MATRIX.read_text(encoding="utf-8")
    header = next(item for item in matrix.splitlines() if item.startswith("> 本表为"))
    assert "Wave 3" in header
    assert "wave-3-integrated" in header
    assert "夹具" in header
    assert "GATE-P0" in header
    assert "不是" in header
    ops = next(item for item in matrix.splitlines() if item.startswith("| 运维 |"))
    assert "unverified" in ops.lower()
    assert "verified" not in ops.lower().replace("unverified", "")
    assert "wave3-closeout" in matrix or "wave3-m11/wave3-closeout" in matrix


def test_NFR_OBS_wave3_closeout_change_does_not_freeze_tbd():
    change = _CHANGE.read_text(encoding="utf-8")
    assert "ND-W3-13" in change
    assert "TBD-P0" in change
    assert "不" in change
    assert "verified" in change.lower()
    assert "冻结" in change
