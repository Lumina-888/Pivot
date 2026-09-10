"""Synthetic Golden Set harness. Not GATE-P0 / NFR-QUAL verified."""

from __future__ import annotations

from collections import Counter
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from golden_set import DATASET_PATH, GENERATOR_PATH, SPEC_STRATA, evaluate, load_dataset
from pivot.retrieval.policy import RetrievalPolicy

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "golden-set.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_FIXTURE_README = _ROOT / "spec" / "fixtures" / "golden-set" / "README.md"


def _injected_policy() -> RetrievalPolicy:
    # Test-only sizes. Do not copy these into SPEC or freeze TBD-P0.
    return RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5)


def test_NFR_QUAL_golden_set_covers_spec_strata():
    dataset = load_dataset()
    strata = {case["stratum"] for case in dataset["cases"]}
    assert strata == SPEC_STRATA
    assert dataset["dataset_version"] == "golden-set-retrieval-v0.2-synthetic"
    assert 100 <= len(dataset["cases"]) <= 150
    counts = Counter(case["stratum"] for case in dataset["cases"])
    for stratum in SPEC_STRATA:
        assert counts[stratum] >= 10, stratum


def test_NFR_QUAL_golden_set_v02_is_reproducible():
    spec = spec_from_file_location("golden_set_synthetic", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    assert load_dataset() == module.build_dataset()


def test_NFR_QUAL_golden_set_is_synthetic_not_enterprise():
    raw = DATASET_PATH.read_text(encoding="utf-8").lower()
    readme = _FIXTURE_README.read_text(encoding="utf-8").lower()
    dataset = load_dataset()
    assert dataset["source"] == "synthetic"
    assert "enterprise" not in raw or "not enterprise" in raw
    for banned in ("sk-", "api_key", "minio.example", "qdrant.cloud", "openai.com"):
        assert banned not in raw
    assert "synthetic" in readme
    assert "100" in readme


def test_NFR_QUAL_golden_set_fake_retrieval_respects_labels():
    report = evaluate(load_dataset(), policy=_injected_policy())
    assert report["failed"] == []
    assert report["passed_count"] == report["case_count"]
    assert report["gate"] == "unverified"


def test_NFR_QUAL_golden_set_does_not_freeze_recall_threshold():
    raw = DATASET_PATH.read_text(encoding="utf-8")
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "Recall@5" not in raw
    assert "TBD-P0" in evidence
    assert "unverified" in evidence.lower()
    assert "NFR-QUAL" in evidence


def test_GATE_P0_002_not_verified_by_golden_set():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-002" in evidence
    assert "unverified" in evidence.lower()
    assert "fake" in evidence.lower() or "KeywordRetriever" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-002" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
