"""Dual-path retrieval comparison harness for the LlamaIndex backend (L2).

Runs the synthetic Golden Set v0.2 corpus and cases through both QA retrieval
paths and records hit sets, ordering, and expectation outcomes per case.

Native path: the existing Golden Set evaluation wiring (RetrievalService with
KeywordRetriever on both channels). LlamaIndex path: LlamaIndexRetriever over
an in-memory index built by the L1 builder from payloads derived from the
same corpus records, with authorization facts derived from the same records.

Harness-only parameters (BowEmbedder dimension, BM25 k1/b) are test values in
the same sense as the Golden Set policy sizes: not TBD-P0, not production
settings. The dense cutoff mirrors the production wiring (no cutoff).
Version conflicts are not compared: neither QA-level result carries them.
Not GATE-P0 verified.
"""

from __future__ import annotations

import zlib
from typing import Any

from golden_set import corpus_records
from pivot.retrieval.fakes import KeywordRetriever
from pivot.retrieval.llama_embeddings import PivotEmbedding
from pivot.retrieval.llama_index_builder import build_llama_index
from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
from pivot.retrieval.models import ChunkRecord, RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService
from pivot.retrieval.tokenize import SimpleLexTokenizer

BOW_DIMENSION = 256
BM25_K1 = 1.2
BM25_B = 0.75
DENSE_SCORE_CUTOFF = 0.0


class BowEmbedder:
    """Deterministic bag-of-words embedder: token-hash buckets, L2 normalized.

    Gives the dense channel token-overlap semantics comparable to the Fake
    keyword baseline, unlike HashingQueryEmbedder whose vectors ignore text
    content beyond a short prefix.
    """

    def __init__(self, dimension: int = BOW_DIMENSION) -> None:
        self._dimension = dimension
        self._tokenizer = SimpleLexTokenizer()

    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * self._dimension
            for token in self._tokenizer.tokenize(text):
                vector[zlib.crc32(token.encode("utf-8")) % self._dimension] += 1.0
            norm = sum(value * value for value in vector) ** 0.5
            if norm == 0.0:
                vector[0] = 1.0
            else:
                vector = [value / norm for value in vector]
            vectors.append(vector)
        return vectors


def corpus_payloads(records: tuple[ChunkRecord, ...]) -> list[dict[str, Any]]:
    """Map corpus records to the vector payload shape the L1 builder consumes.

    Eval corpora predate libraries and are public by construction, so a
    record without a library maps to the public library here.
    """
    return [
        {
            "chunk_id": record.chunk_id,
            "version_id": record.version_id,
            "document_id": record.document_id,
            "text": record.text,
            "locator": f"golden:{record.chunk_id}",
            "library_id": record.library_id or "pub",
            "ready": record.ready,
            "current": record.current,
            "allowed": record.allowed,
            "expired": record.expired,
            "deleted": record.deleted,
            "index_generation": record.index_generation,
            "embedding_model_version": record.embedding_model_version,
            "retrieval_config_version": record.retrieval_config_version,
        }
        for record in records
    ]


def _native_service(records, policy) -> RetrievalService:
    return RetrievalService(
        corpus=records,
        dense=KeywordRetriever(records, "dense"),
        bm25=KeywordRetriever(records, "bm25"),
        policy=policy,
    )


def _llama_retriever(records, policy) -> LlamaIndexRetriever:
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
    index = build_llama_index(
        corpus_payloads(records),
        embed_model=PivotEmbedding(
            BowEmbedder(), model_name="bow-harness", dimension=BOW_DIMENSION
        ),
        external_llm_allowed=lambda version_id: external_allowed[version_id],
    )
    return LlamaIndexRetriever(
        index,
        policy=policy,
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=BM25_K1,
        bm25_b=BM25_B,
        dense_score_cutoff=DENSE_SCORE_CUTOFF,
        authorize=lambda principal, document, version: (document, version) in authorized,
    )


def _expectation_reasons(case: dict[str, Any], hit_ids: list[str]) -> list[str]:
    reasons: list[str] = []
    if case["expect_refuse"]:
        if hit_ids:
            reasons.append(f"expected empty, got {hit_ids}")
    else:
        missing = [
            chunk_id for chunk_id in case["expected_chunk_ids"] if chunk_id not in hit_ids
        ]
        if missing:
            reasons.append(f"missing {missing} in {hit_ids}")
    leaked = [chunk_id for chunk_id in case["forbidden_chunk_ids"] if chunk_id in hit_ids]
    if leaked:
        reasons.append(f"leaked {leaked}")
    return reasons


def compare(
    dataset: dict[str, Any], *, policy: RetrievalPolicy
) -> dict[str, Any]:
    """Run every case through both paths; classify per-case differences."""
    records = corpus_records(dataset)
    native = _native_service(records, policy)
    llama = _llama_retriever(records, policy)
    rows: list[dict[str, Any]] = []
    labeled_needed = 0
    labeled_hits = {"native": 0, "llama": 0}
    for case in dataset["cases"]:
        native_outcome = native.retrieve(
            RetrievalQuery(
                text=case["question"],
                principal_id=case["principal_id"],
                scope_type=case["scope_type"],
                scope_document_id=case["scope_document_id"],
                prompt=case.get("prompt") or "",
            )
        )
        native_hits = [item.chunk_id for item in native_outcome.evidence]
        llama_result = llama.retrieve(
            case["question"],
            scope_type=case["scope_type"],
            scope_document_id=case["scope_document_id"],
            principal_id=case["principal_id"],
        )
        llama_hits = [hit.chunk_id for hit in llama_result.evidence]
        if set(native_hits) != set(llama_hits):
            diff_class = "set"
        elif native_hits != llama_hits:
            diff_class = "order"
        else:
            diff_class = "none"
        expected = list(case["expected_chunk_ids"])
        labeled_needed += len(expected)
        labeled_hits["native"] += sum(1 for chunk_id in expected if chunk_id in native_hits)
        labeled_hits["llama"] += sum(1 for chunk_id in expected if chunk_id in llama_hits)
        rows.append(
            {
                "id": case["id"],
                "stratum": case["stratum"],
                "native_status": native_outcome.status,
                "llama_status": llama_result.status,
                "native_hits": native_hits,
                "llama_hits": llama_hits,
                "native_reasons": _expectation_reasons(case, native_hits),
                "llama_reasons": _expectation_reasons(case, llama_hits),
                "diff_class": diff_class,
            }
        )
    return {
        "dataset_version": dataset["dataset_version"],
        "case_count": len(rows),
        "policy": {
            "dense_k": policy.dense_k,
            "bm25_k": policy.bm25_k,
            "rrf_k": policy.rrf_k,
            "evidence_limit": policy.evidence_limit,
        },
        "native_failed": [row["id"] for row in rows if row["native_reasons"]],
        "llama_failed": [row["id"] for row in rows if row["llama_reasons"]],
        "labeled_hit_rate": {
            side: (hits / labeled_needed if labeled_needed else None)
            for side, hits in labeled_hits.items()
        },
        "diff_counts": {
            kind: sum(1 for row in rows if row["diff_class"] == kind)
            for kind in ("none", "order", "set")
        },
        "results": rows,
    }
