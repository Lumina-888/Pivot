"""L2 dual-path comparison locks: expectations, no leaks, report in sync.

The comparison runs the synthetic Golden Set v0.2 through the native Golden
Set wiring and the LlamaIndex path. The evidence report must register every
case whose hit set or ordering differs; if behavior drifts, this file fails
until the report is regenerated and re-concluded. Not GATE-P0 verified.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("llama_index.core")

from backend_compare import compare  # noqa: E402
from golden_set import load_dataset  # noqa: E402
from pivot.retrieval.policy import RetrievalPolicy  # noqa: E402

_ROOT = Path(__file__).resolve().parents[3]
_REPORT = _ROOT / "evidence" / "llama-index-l2" / "backend-comparison.md"


def _policy() -> RetrievalPolicy:
    # Test-only sizes, same as the Golden Set harness. Not TBD-P0.
    return RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5)


@pytest.fixture(scope="module")
def report() -> dict:
    return compare(load_dataset(), policy=_policy())


def test_FR_RAG_007_expectations_hold_on_both_paths(report):
    assert report["case_count"] == 120
    assert report["native_failed"] == []
    assert report["llama_failed"] == []
    assert report["labeled_hit_rate"] == {"native": 1.0, "llama": 1.0}


def test_FR_RAG_007_no_forbidden_chunk_leaks_on_either_path(report):
    dataset = load_dataset()
    forbidden = {
        case["id"]: set(case["forbidden_chunk_ids"]) for case in dataset["cases"]
    }
    for row in report["results"]:
        assert not forbidden[row["id"]] & set(row["native_hits"]), row["id"]
        assert not forbidden[row["id"]] & set(row["llama_hits"]), row["id"]


def test_FR_RAG_007_report_registers_every_difference(report):
    text = _REPORT.read_text(encoding="utf-8")
    differing = {
        row["id"] for row in report["results"] if row["diff_class"] != "none"
    }
    registered = {
        line.split("|")[1].strip()
        for line in text.splitlines()
        if line.startswith("| gs_")
    }
    assert registered == differing
    assert report["diff_counts"] == {"none": 65, "order": 11, "set": 44}


def test_FR_RAG_007_report_records_benchmark_and_limits():
    text = _REPORT.read_text(encoding="utf-8")
    assert "golden-set-retrieval-v0.2-synthetic" in text
    assert "ops/run_backend_compare.py" in text
    assert "unverified" in text.lower()
    assert "GATE-P0-002" in text
