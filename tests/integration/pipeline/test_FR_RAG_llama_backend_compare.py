"""L2 dual-path comparison locks: expectations, leaks, report in sync.

The comparison runs the synthetic Golden Set v0.2 through the native Golden
Set wiring and the LlamaIndex path. The evidence report must register every
case whose hit set or ordering differs; if behavior drifts, this file fails
until the report is regenerated and re-concluded. Not GATE-P0 verified.

Re-measured 2026-10-23 after the FR-RAG-009 dense-leg fix: the original
locks were taken with the LlamaIndex dense leg silently down, so the
llama path behaved as BM25-only and passed every expectation. With the
dense leg live, the llama path fails the refusal strata exactly like
the production path does (no relevance floor, ADR-014), while content
recall stays at 1.0 on both paths.
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
    # Measured after the dense-leg fix: all 24 refusal-stratum cases
    # plus two document_scope cases fail on the llama path because the
    # dense leg returns nearest neighbours and no relevance floor
    # exists yet (ADR-014). Locked as the current measured state.
    assert report["llama_failed"] == [
        "gs_no_answer_01",
        "gs_unauthorized_01",
        "gs_no_answer_02",
        "gs_unauthorized_02",
        "gs_no_answer_03",
        "gs_unauthorized_03",
        "gs_no_answer_04",
        "gs_document_scope_04",
        "gs_unauthorized_04",
        "gs_no_answer_05",
        "gs_unauthorized_05",
        "gs_no_answer_06",
        "gs_document_scope_06",
        "gs_unauthorized_06",
        "gs_no_answer_07",
        "gs_unauthorized_07",
        "gs_no_answer_08",
        "gs_unauthorized_08",
        "gs_no_answer_09",
        "gs_unauthorized_09",
        "gs_no_answer_10",
        "gs_unauthorized_10",
        "gs_no_answer_11",
        "gs_unauthorized_11",
        "gs_no_answer_12",
        "gs_unauthorized_12",
    ]
    assert report["labeled_hit_rate"] == {"native": 1.0, "llama": 1.0}


def test_FR_RAG_007_no_forbidden_chunk_leaks_on_either_path(report):
    dataset = load_dataset()
    forbidden = {
        case["id"]: set(case["forbidden_chunk_ids"]) for case in dataset["cases"]
    }
    llama_leaks = {}
    for row in report["results"]:
        assert not forbidden[row["id"]] & set(row["native_hits"]), row["id"]
        leaked = forbidden[row["id"]] & set(row["llama_hits"])
        if leaked:
            llama_leaks[row["id"]] = leaked
    # One measured leak after the dense-leg fix: the no_answer_12
    # distractor chunks are recalled by the dense leg. Locked so any
    # change, better or worse, forces a report update.
    assert llama_leaks == {"gs_no_answer_12": {"chk_fact_12", "chk_param_12"}}


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
    assert report["diff_counts"] == {"none": 22, "order": 0, "set": 98}


def test_FR_RAG_007_report_records_benchmark_and_limits():
    text = _REPORT.read_text(encoding="utf-8")
    assert "golden-set-retrieval-v0.2-synthetic" in text
    assert "ops/run_backend_compare.py" in text
    assert "unverified" in text.lower()
    assert "GATE-P0-002" in text
