"""Golden Set evaluation of the default (LlamaIndex) retrieval path.

Runs a labeled Golden Set through the path production now uses by
default: LlamaIndexRetriever over the Qdrant-backed persistent index
(LlamaQdrantIndex), built from the same corpus records, with
authorization facts derived from the same records. The Qdrant client is
in-memory; the index build, hydration and retrieval code are the
production ones.

Expectations are scored with the Golden Set semantics: a refuse case
passes only when the result is empty, a labeled case passes when every
expected chunk is present, and any forbidden chunk in the evidence is a
leak failure. Version-conflict expectations are not scored at this
layer: the QA-level retrieval result carries no conflict signal (the
orchestrator owns that branch), so those cases are scored on their
chunk expectations only and counted separately in the report.

The embedder is the controlled BowEmbedder from the L2 harness and the
policy sizes are test values: neither is a production setting or a
TBD-P0 freeze. Not GATE-P0 verified.
"""

from __future__ import annotations

from typing import Any

from backend_compare import BOW_DIMENSION, BowEmbedder, corpus_payloads
from golden_set import corpus_records
from pivot.retrieval.llama_embeddings import PivotEmbedding
from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
from pivot.retrieval.llama_qdrant_index import LlamaQdrantIndex
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.tokenize import SimpleLexTokenizer

BM25_K1 = 1.2
BM25_B = 0.75
DENSE_SCORE_CUTOFF = -1.0
NATIVE_COLLECTION = "pivot-chunks"


def build_default_retriever(records, policy) -> LlamaIndexRetriever:
    """Assemble the default-path retriever over a persistent index."""
    from qdrant_client import QdrantClient

    authorized = {
        (record.document_id, record.version_id)
        for record in records
        if record.allowed and record.current
    }
    external_allowed: dict[str, bool] = {}
    for record in records:
        external_allowed[record.version_id] = (
            external_allowed.get(record.version_id, False) or record.allowed
        )
    embed_model = PivotEmbedding(
        BowEmbedder(), model_name="bow-harness", dimension=BOW_DIMENSION
    )
    holder = LlamaQdrantIndex.open(
        client=QdrantClient(location=":memory:"),
        native_collection=NATIVE_COLLECTION,
        embed_model=embed_model,
        vector_size=BOW_DIMENSION,
        distance="Cosine",
        native_payloads=corpus_payloads(records),
        external_llm_allowed=lambda version_id: external_allowed[version_id],
    )
    return LlamaIndexRetriever(
        holder.index,
        policy=policy,
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=BM25_K1,
        bm25_b=BM25_B,
        dense_score_cutoff=DENSE_SCORE_CUTOFF,
        authorize=lambda principal, document, version: (document, version) in authorized,
    )


def evaluate_default_path(
    dataset: dict[str, Any], *, policy: RetrievalPolicy
) -> dict[str, Any]:
    """Score every case of a labeled dataset against the default path."""
    records = corpus_records(dataset)
    retriever = build_default_retriever(records, policy)
    results: list[dict[str, Any]] = []
    strata: dict[str, dict[str, int]] = {}
    labeled_hits = 0
    labeled_needed = 0
    leaks = 0
    conflicts_expected = 0
    for case in dataset["cases"]:
        result = retriever.retrieve(
            case["question"],
            scope_type=case["scope_type"],
            scope_document_id=case["scope_document_id"],
            principal_id=case["principal_id"],
        )
        hit_ids = [hit.chunk_id for hit in result.evidence]
        reasons: list[str] = []
        if case["expect_refuse"]:
            if result.status != "empty" or hit_ids:
                reasons.append(f"expected empty, got {result.status} {hit_ids}")
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
        leaks += len(leaked)
        if case.get("expect_conflicts"):
            conflicts_expected += 1
        expected = list(case["expected_chunk_ids"])
        case_hits = sum(1 for chunk_id in expected if chunk_id in hit_ids)
        labeled_hits += case_hits
        labeled_needed += len(expected)
        bucket = strata.setdefault(
            case["stratum"],
            {"cases": 0, "passed": 0, "labeled_hits": 0, "labeled_needed": 0},
        )
        bucket["cases"] += 1
        bucket["passed"] += 0 if reasons else 1
        bucket["labeled_hits"] += case_hits
        bucket["labeled_needed"] += len(expected)
        results.append(
            {
                "id": case["id"],
                "stratum": case["stratum"],
                "ok": not reasons,
                "reasons": reasons,
                "hit_ids": hit_ids,
                "status": result.status,
            }
        )
    failed = [item for item in results if not item["ok"]]
    return {
        "dataset_version": dataset["dataset_version"],
        "source": dataset.get("source"),
        "path": "llama-qdrant-persistent",
        "case_count": len(results),
        "passed_count": len(results) - len(failed),
        "failed": failed,
        "results": results,
        "labeled_hit_rate": (
            labeled_hits / labeled_needed if labeled_needed else None
        ),
        "labeled_hits": labeled_hits,
        "labeled_needed": labeled_needed,
        "forbidden_leaks": leaks,
        "conflicts_expected_cases": conflicts_expected,
        "strata": {
            name: {
                **bucket,
                "labeled_hit_rate": (
                    bucket["labeled_hits"] / bucket["labeled_needed"]
                    if bucket["labeled_needed"]
                    else None
                ),
            }
            for name, bucket in sorted(strata.items())
        },
        "gate": "unverified",
    }
