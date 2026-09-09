"""Opt-in 100k chunk retrieve harness. GATE-P0-007 stays unverified."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_OPS = str(_ROOT / "ops")
if _OPS not in sys.path:
    sys.path.insert(0, _OPS)
from chunk_capacity import resolve_chunk_count, retrieve_synthetic  # noqa: E402

_PLAN = _ROOT / "tests" / "performance" / "PLAN.md"
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "chunk-capacity.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_RUNNER = _ROOT / "ops" / "chunk_capacity.py"
_QUERY_TEXT = "late three times"


def test_NFR_CAP_004_chunk_count_requires_injection():
    with pytest.raises(RuntimeError, match="PIVOT_CHUNK_COUNT"):
        resolve_chunk_count({})
    assert resolve_chunk_count({"PIVOT_CHUNK_COUNT": "32"}) == 32
    source = _RUNNER.read_text(encoding="utf-8")
    assert "PIVOT_CHUNK_COUNT" in source
    assert "os.environ.get(\"PIVOT_CHUNK_COUNT\", \"100000\")" not in source
    assert "os.environ.get('PIVOT_CHUNK_COUNT', '100000')" not in source


def test_NFR_CAP_004_small_corpus_retrieve_completes():
    result = retrieve_synthetic(count=32, text=_QUERY_TEXT)
    assert result.count == 32
    assert result.status == "ok"
    assert result.evidence_count > 0
    assert result.traced_peak_bytes is None or result.traced_peak_bytes > 0


def test_NFR_CAP_004_require_100k_rejects_wrong_count():
    with pytest.raises(RuntimeError, match="PIVOT_REQUIRE_100K"):
        resolve_chunk_count({"PIVOT_REQUIRE_100K": "1", "PIVOT_CHUNK_COUNT": "32"})
    with pytest.raises(RuntimeError, match="PIVOT_CHUNK_COUNT"):
        resolve_chunk_count({"PIVOT_REQUIRE_100K": "1"})


def test_NFR_CAP_004_one_hundred_k_retrieve_when_required():
    require = os.environ.get("PIVOT_REQUIRE_100K") == "1"
    if not require:
        pytest.skip("100k chunk retrieve is opt-in (PIVOT_REQUIRE_100K=1)")
    count = resolve_chunk_count(os.environ)
    assert count == 100_000
    result = retrieve_synthetic(count=count, text=_QUERY_TEXT)
    assert result.count == 100_000
    assert result.status == "ok"
    assert result.evidence_count > 0


def test_NFR_CAP_004_does_not_freeze_peak_or_p95():
    source = _RUNNER.read_text(encoding="utf-8")
    plan = _PLAN.read_text(encoding="utf-8")
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "P95" not in source
    assert "P50" not in source
    assert "TBD-P0" in plan
    assert "TBD-P0" in evidence
    assert "不" in evidence and ("门禁" in evidence or "冻结" in evidence)


def test_NFR_CAP_004_ci_does_not_require_100k():
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    grouped = (_ROOT / "ops" / "run_grouped_tests.py").read_text(encoding="utf-8")
    assert "PIVOT_REQUIRE_100K" not in workflow
    assert "PIVOT_REQUIRE_100K" not in grouped


def test_GATE_P0_007_not_verified_by_one_hundred_k_harness():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    plan = _PLAN.read_text(encoding="utf-8")
    limits = _LIMITS.read_text(encoding="utf-8")
    assert "GATE-P0-007" in evidence
    assert "unverified" in evidence.lower()
    assert "unverified" in plan.lower()
    line = next(item for item in limits.splitlines() if "GATE-P0-007" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
