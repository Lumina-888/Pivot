from __future__ import annotations

import pytest
from corpus import corpus
from pivot.retrieval.fakes import KeywordRetriever, OverlapReranker
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService


@pytest.fixture
def policy() -> RetrievalPolicy:
    return RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5)


@pytest.fixture
def service(policy: RetrievalPolicy) -> RetrievalService:
    records = corpus()
    return RetrievalService(
        corpus=records,
        dense=KeywordRetriever(records, "dense"),
        bm25=KeywordRetriever(records, "bm25"),
        policy=policy,
        reranker=OverlapReranker(),
    )
