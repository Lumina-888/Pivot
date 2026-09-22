"""Enterprise Golden Set schema and annotation spec. Not GATE-P0 / NFR-QUAL verified."""

from __future__ import annotations

import json
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


def test_NFR_QUAL_enterprise_dataset_is_human_empty_not_renamed_synthetic():
    payload = json.loads(ENTERPRISE_DATASET_PATH.read_text(encoding="utf-8"))
    synthetic = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    assert payload["source"] == "human"
    assert payload["status"] == "awaiting_annotation"
    assert payload["dataset_version"] == "golden-set-retrieval-v0.3-enterprise"
    assert payload["dataset_version"] != synthetic["dataset_version"]
    assert payload["cases"] == []
    assert payload["corpus"] == []
    raw = ENTERPRISE_DATASET_PATH.read_text(encoding="utf-8").lower()
    assert "employees late" not in raw
    assert "topic01" not in raw
    for banned in ("sk-", "api_key", "minio.example", "qdrant.cloud", "openai.com"):
        assert banned not in raw
    notes = str(payload.get("notes", "")).lower()
    assert "not" in notes and "synthetic" in notes or "非合成" in str(payload.get("notes", ""))


def test_NFR_QUAL_enterprise_loader_rejects_synthetic_source():
    with pytest.raises(ValueError, match="human"):
        load_enterprise_dataset(DATASET_PATH)
    with pytest.raises(ValueError, match="synthetic"):
        load_dataset(ENTERPRISE_DATASET_PATH)
    dataset = load_dataset()
    assert dataset["source"] == "synthetic"
    empty = load_enterprise_dataset()
    assert empty["source"] == "human"
    assert empty["cases"] == []


def test_NFR_QUAL_golden_set_eval_runner_reports_unverified_for_empty_enterprise():
    report = evaluate(load_enterprise_dataset())
    assert report["case_count"] == 0
    assert report["status"] == "awaiting_annotation"
    assert report["gate"] == "unverified"
    assert report["passed_count"] == 0
    runner = _RUNNER.read_text(encoding="utf-8")
    assert "v0.2-synthetic" in runner or "DATASET_PATH" in runner
    assert "--enterprise" in runner
    assert "GATE" in runner
    grouped = _GROUPED.read_text(encoding="utf-8")
    assert "run_golden_set.py" not in grouped or "does not start" in grouped.lower()


def test_GATE_P0_002_not_verified_by_enterprise_schema():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-002" in evidence
    assert "unverified" in evidence.lower()
    assert "awaiting_annotation" in evidence or "空" in evidence
    assert "v0.2" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-002" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
    assert "企业标注" in line or "enterprise" in line.lower()
