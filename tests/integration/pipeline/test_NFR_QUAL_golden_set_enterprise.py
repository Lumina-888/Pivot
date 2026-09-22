"""Enterprise Golden Set labels. Not GATE-P0 / NFR-QUAL verified."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest
from golden_set import (
    DATASET_PATH,
    ENTERPRISE_DATASET_PATH,
    SPEC_STRATA,
    evaluate,
    load_dataset,
    load_enterprise_dataset,
)
from pivot.retrieval.policy import RetrievalPolicy

_ROOT = Path(__file__).resolve().parents[3]
_ANNOTATION = _ROOT / "spec" / "fixtures" / "golden-set" / "ANNOTATION.md"
_README = _ROOT / "spec" / "fixtures" / "golden-set" / "README.md"
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "golden-set-enterprise.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_RUNNER = _ROOT / "ops" / "run_golden_set.py"
_GROUPED = _ROOT / "ops" / "run_grouped_tests.py"
_REQUIRED_CASE_FIELDS = (
    "问题",
    "期望证据",
    "允许答案",
    "是否应拒答",
    "人工标注",
    "数据集版本",
    "回归结果",
)


def test_NFR_QUAL_enterprise_annotation_spec_covers_strata_and_size():
    spec = _ANNOTATION.read_text(encoding="utf-8")
    lowered = spec.lower()
    for stratum in SPEC_STRATA:
        assert stratum in spec, stratum
    assert "100" in spec and "150" in spec
    assert "≥10" in spec or ">=10" in spec or "每层" in spec
    for field in _REQUIRED_CASE_FIELDS:
        assert field in spec, field
    assert "合同" in spec or "人事" in spec
    assert "v0.2" in spec
    assert "改名" in spec or "rename" in lowered
    assert "TBD-P0" in spec
    assert "GATE-P0-002" in spec
    assert "unverified" in lowered
    readme = _README.read_text(encoding="utf-8")
    assert "ANNOTATION.md" in readme
    assert "v0.3-enterprise" in readme


def _injected_policy() -> RetrievalPolicy:
    # Test-only sizes. Do not copy these into SPEC or freeze TBD-P0.
    return RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5)


def test_NFR_QUAL_enterprise_dataset_is_human_labeled_not_renamed_synthetic():
    payload = json.loads(ENTERPRISE_DATASET_PATH.read_text(encoding="utf-8"))
    synthetic = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    assert payload["source"] == "human"
    assert payload["status"] == "annotated_desensitized"
    assert payload["dataset_version"] == "golden-set-retrieval-v0.3-enterprise"
    assert payload["dataset_version"] != synthetic["dataset_version"]
    assert 100 <= len(payload["cases"]) <= 150
    assert payload["corpus"]
    counts = Counter(case["stratum"] for case in payload["cases"])
    assert set(counts) == SPEC_STRATA
    for stratum in SPEC_STRATA:
        assert counts[stratum] >= 10, stratum
    synthetic_ids = {case["id"] for case in synthetic["cases"]}
    assert synthetic_ids.isdisjoint({case["id"] for case in payload["cases"]})
    raw = ENTERPRISE_DATASET_PATH.read_text(encoding="utf-8")
    lowered = raw.lower()
    assert "employees late" not in lowered
    assert "topic01" not in lowered
    for banned in ("sk-", "api_key", "minio.example", "qdrant.cloud", "openai.com"):
        assert banned not in lowered
    assert not re.search(r"1[3-9]\d{9}", raw)
    assert not re.search(r"\d{11,}", raw)
    assert "@" not in raw
    for banned_text in ("合同编号", "纳税人识别号", "身份证", "人天单价", "薪酬"):
        assert banned_text not in raw
    for case in payload["cases"]:
        assert case["regression_result"] == "pending"
        assert case["annotation"]["annotator"]
        assert case["annotation"]["source_file"]
    notes = str(payload.get("notes", "")).lower()
    assert "synthetic" in notes or "非合成" in str(payload.get("notes", ""))
    assert "desensit" in notes or "脱敏" in str(payload.get("notes", ""))


def test_NFR_QUAL_enterprise_loader_rejects_synthetic_source(tmp_path: Path):
    with pytest.raises(ValueError, match="human"):
        load_enterprise_dataset(DATASET_PATH)
    with pytest.raises(ValueError, match="synthetic"):
        load_dataset(ENTERPRISE_DATASET_PATH)
    dataset = load_dataset()
    assert dataset["source"] == "synthetic"
    labeled = load_enterprise_dataset()
    assert labeled["source"] == "human"
    assert labeled["cases"]
    empty_path = tmp_path / "empty.json"
    empty_path.write_text(
        json.dumps(
            {
                "dataset_version": "golden-set-retrieval-v0.3-enterprise",
                "source": "human",
                "status": "awaiting_annotation",
                "corpus": [],
                "cases": [],
            }
        ),
        encoding="utf-8",
    )
    empty = load_enterprise_dataset(empty_path)
    assert empty["cases"] == []


def test_NFR_QUAL_golden_set_eval_runner_reports_unverified_for_enterprise(tmp_path: Path):
    empty_path = tmp_path / "empty.json"
    empty_path.write_text(
        json.dumps(
            {
                "dataset_version": "golden-set-retrieval-v0.3-enterprise",
                "source": "human",
                "status": "awaiting_annotation",
                "corpus": [],
                "cases": [],
            }
        ),
        encoding="utf-8",
    )
    empty_report = evaluate(load_enterprise_dataset(empty_path))
    assert empty_report["case_count"] == 0
    assert empty_report["status"] == "awaiting_annotation"
    assert empty_report["gate"] == "unverified"
    report = evaluate(load_enterprise_dataset(), policy=_injected_policy())
    assert report["failed"] == []
    assert report["passed_count"] == report["case_count"]
    assert report["gate"] == "unverified"
    assert report["status"] == "evaluated"
    runner = _RUNNER.read_text(encoding="utf-8")
    assert "v0.2-synthetic" in runner or "DATASET_PATH" in runner
    assert "--enterprise" in runner
    assert "GATE" in runner
    assert "unverified" in runner.lower()
    grouped = _GROUPED.read_text(encoding="utf-8")
    assert "run_golden_set.py" not in grouped or "does not start" in grouped.lower()


def test_GATE_P0_002_not_verified_by_enterprise_labels():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-002" in evidence
    assert "unverified" in evidence.lower()
    assert "脱敏" in evidence or "desensit" in evidence.lower()
    assert "v0.2" in evidence
    assert "Fake" in evidence or "Keyword" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-002" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
    assert "企业" in line or "enterprise" in line.lower()
    raw = ENTERPRISE_DATASET_PATH.read_text(encoding="utf-8")
    assert "Recall@5" not in raw
    assert "TBD-P0" in evidence
