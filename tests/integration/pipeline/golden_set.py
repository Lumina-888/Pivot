"""Load and score Golden Set fixtures against Fake retrieval.

Synthetic v0.2 is the default CI harness. Enterprise v0.3 is a human-labeled,
desensitized excerpt set. Not GATE-P0 verified. Injected RetrievalPolicy sizes
are test values, not TBD-P0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pivot.retrieval.fakes import KeywordRetriever
from pivot.retrieval.models import ChunkRecord, RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService

_ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = (
    _ROOT / "spec" / "fixtures" / "golden-set" / "retrieval" / "v0.2-synthetic.json"
)
ENTERPRISE_DATASET_PATH = (
    _ROOT
    / "spec"
    / "fixtures"
    / "golden-set"
    / "retrieval"
    / "v0.3-enterprise.json"
)
GENERATOR_PATH = _ROOT / "ops" / "golden_set_synthetic.py"
SPEC_STRATA = frozenset(
    {
        "fact",
        "parameter",
        "multi_span",
        "no_answer",
        "distractor",
        "version_conflict",
        "document_scope",
        "parse_failure",
        "prompt_injection",
        "unauthorized",
    }
)
_CASE_KEYS = frozenset(
    {
        "id",
        "stratum",
        "question",
        "scope_type",
        "scope_document_id",
        "principal_id",
        "prompt",
        "expect_refuse",
        "expect_conflicts",
        "expected_chunk_ids",
        "forbidden_chunk_ids",
        "allowed_answers",
        "annotation",
    }
)
_CHUNK_KEYS = frozenset(
    {
        "chunk_id",
        "version_id",
        "document_id",
        "text",
        "title",
        "ready",
        "current",
        "allowed",
        "expired",
        "deleted",
    }
)


def _read_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("golden set must be an object")
    if not payload.get("dataset_version"):
        raise ValueError("dataset_version is required")
    cases = payload.get("cases")
    corpus = payload.get("corpus")
    if not isinstance(cases, list) or not isinstance(corpus, list):
        raise ValueError("corpus and cases must be lists")
    return payload


def _validate_labeled_rows(
    payload: dict[str, Any],
    *,
    extra_case_keys: frozenset[str] = frozenset(),
) -> None:
    case_keys = _CASE_KEYS.union(extra_case_keys)
    for chunk in payload["corpus"]:
        missing = _CHUNK_KEYS.difference(chunk)
        if missing:
            raise ValueError(f"chunk missing {sorted(missing)}")
    for case in payload["cases"]:
        missing = case_keys.difference(case)
        if missing:
            raise ValueError(f"case missing {sorted(missing)}")
        if case["stratum"] not in SPEC_STRATA:
            raise ValueError(f"unknown stratum {case['stratum']!r}")


def load_dataset(path: Path | None = None) -> dict[str, Any]:
    payload = _read_payload(path or DATASET_PATH)
    if payload.get("source") != "synthetic":
        raise ValueError("this slice only loads synthetic golden sets")
    _validate_labeled_rows(payload)
    return payload


def load_enterprise_dataset(path: Path | None = None) -> dict[str, Any]:
    payload = _read_payload(path or ENTERPRISE_DATASET_PATH)
    if payload.get("source") != "human":
        raise ValueError("enterprise loader only loads human golden sets")
    if not payload["cases"] and not payload["corpus"]:
        if payload.get("status") != "awaiting_annotation":
            raise ValueError("empty enterprise set must be awaiting_annotation")
        return payload
    if payload.get("status") == "awaiting_annotation":
        raise ValueError("labeled enterprise set cannot stay awaiting_annotation")
    _validate_labeled_rows(
        payload, extra_case_keys=frozenset({"regression_result"})
    )
    return payload


def corpus_records(dataset: dict[str, Any]) -> tuple[ChunkRecord, ...]:
    records = []
    for item in dataset["corpus"]:
        records.append(
            ChunkRecord(
                chunk_id=item["chunk_id"],
                version_id=item["version_id"],
                document_id=item["document_id"],
                text=item["text"],
                title=item.get("title", ""),
                space=item.get("space", ""),
                tags=tuple(item.get("tags") or ()),
                ready=bool(item["ready"]),
                current=bool(item["current"]),
                allowed=bool(item["allowed"]),
                expired=bool(item["expired"]),
                deleted=bool(item["deleted"]),
                version_label=item.get("version_label", "v1"),
                index_generation="gen_golden_synthetic",
                embedding_model_version="embed-fake",
                retrieval_config_version="retr-fake",
            )
        )
    return tuple(records)


def evaluate(
    dataset: dict[str, Any],
    *,
    policy: RetrievalPolicy | None = None,
) -> dict[str, Any]:
    if not dataset.get("cases"):
        return {
            "dataset_version": dataset["dataset_version"],
            "case_count": 0,
            "passed_count": 0,
            "failed": [],
            "results": [],
            "diagnostic_labeled_hit_rate": None,
            "gate": "unverified",
            "status": dataset.get("status") or "awaiting_annotation",
        }
    if dataset.get("source") == "human" and dataset.get("status") not in {
        "annotated_desensitized",
        "evaluated",
    }:
        raise ValueError("human golden set status is not evaluable")
    if policy is None:
        raise ValueError("policy is required to evaluate labeled cases")
    records = corpus_records(dataset)
    service = RetrievalService(
        corpus=records,
        dense=KeywordRetriever(records, "dense"),
        bm25=KeywordRetriever(records, "bm25"),
        policy=policy,
    )
    results: list[dict[str, Any]] = []
    labeled_hits = 0
    labeled_needed = 0
    for case in dataset["cases"]:
        outcome = service.retrieve(
            RetrievalQuery(
                text=case["question"],
                principal_id=case["principal_id"],
                scope_type=case["scope_type"],
                scope_document_id=case["scope_document_id"],
                prompt=case.get("prompt") or "",
            )
        )
        hit_ids = [item.chunk_id for item in outcome.evidence]
        reasons: list[str] = []
        if case["expect_refuse"]:
            if outcome.status != "empty" or hit_ids:
                reasons.append(f"expected empty, got {outcome.status} {hit_ids}")
        else:
            missing = [
                chunk_id
                for chunk_id in case["expected_chunk_ids"]
                if chunk_id not in hit_ids
            ]
            if missing:
                reasons.append(f"missing {missing} in {hit_ids}")
        leaked = [
            chunk_id for chunk_id in case["forbidden_chunk_ids"] if chunk_id in hit_ids
        ]
        if leaked:
            reasons.append(f"leaked {leaked}")
        if case.get("expect_conflicts") and not outcome.conflicts:
            reasons.append("expected version conflict")
        expected = list(case["expected_chunk_ids"])
        labeled_needed += len(expected)
        labeled_hits += sum(1 for chunk_id in expected if chunk_id in hit_ids)
        results.append(
            {
                "id": case["id"],
                "stratum": case["stratum"],
                "ok": not reasons,
                "reasons": reasons,
                "hit_ids": hit_ids,
                "status": outcome.status,
            }
        )
    failed = [item for item in results if not item["ok"]]
    return {
        "dataset_version": dataset["dataset_version"],
        "case_count": len(results),
        "passed_count": len(results) - len(failed),
        "failed": failed,
        "results": results,
        "diagnostic_labeled_hit_rate": (
            labeled_hits / labeled_needed if labeled_needed else None
        ),
        "gate": "unverified",
        "status": "evaluated",
    }
