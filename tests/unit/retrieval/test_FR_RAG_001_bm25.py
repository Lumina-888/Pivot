"""stdlib BM25 retriever. Tokenizer/k1/b stay injected, not frozen."""

from __future__ import annotations

from pathlib import Path

from pivot.retrieval.bm25 import Bm25Reranker, Bm25Retriever
from pivot.retrieval.fakes import FailingRetriever, KeywordRetriever
from pivot.retrieval.models import ChunkRecord, RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService
from pivot.retrieval.tokenize import SimpleLexTokenizer

_SRC = Path(__file__).resolve().parents[3] / "api" / "src" / "pivot" / "retrieval"


def _chunk(chunk_id: str, text: str, **overrides) -> ChunkRecord:
    values = dict(
        chunk_id=chunk_id,
        version_id=f"ver_{chunk_id}",
        document_id=f"doc_{chunk_id}",
        text=text,
        title="Attendance Policy",
        space="hr",
        ready=True,
        current=True,
        allowed=True,
        index_generation="gen_bm25",
        embedding_model_version="hash-embed-test",
        retrieval_config_version="bm25-test",
    )
    values.update(overrides)
    return ChunkRecord(**values)


def _retriever(*chunks: ChunkRecord) -> Bm25Retriever:
    retriever = Bm25Retriever(SimpleLexTokenizer(), k1=1.2, b=0.75, source="bm25")
    retriever.add(chunks)
    return retriever


def test_FR_RAG_001_bm25_ranks_by_idf_not_raw_count():
    rare = _chunk("chk_rare", "alpha unique clause")
    spam = _chunk("chk_spam", "warning warning warning warning")
    other = _chunk("chk_other", "warning invoice")
    records = (rare, spam, other)
    keyword = KeywordRetriever(records, "bm25")
    bm25 = _retriever(*records)
    query = "alpha warning"
    assert keyword.search(query, k=2)[0].chunk_id == "chk_spam"
    assert bm25.search(query, k=2)[0].chunk_id == "chk_rare"
    assert bm25.resolve("chk_rare") is not None
    chinese = _retriever(_chunk("chk_policy", "迟到三次以上记为旷工"))
    assert chinese.search("迟到", k=1)[0].chunk_id == "chk_policy"


def test_FR_RAG_001_bm25_uses_injected_k_and_params():
    retriever = _retriever(
        _chunk("chk_0", "迟到 专有 条款"),
        _chunk("chk_1", "迟到 警告"),
        _chunk("chk_2", "报销发票"),
    )
    assert len(retriever.search("迟到", k=1)) == 1
    assert len(retriever.search("迟到", k=3)) == 2
    other = Bm25Retriever(SimpleLexTokenizer(), k1=2.0, b=0.0, source="bm25")
    other.add((_chunk("chk_0", "迟到 专有 条款"), _chunk("chk_1", "迟到 警告")))
    assert other.search("迟到", k=2)[0].chunk_id in {"chk_0", "chk_1"}


def test_FR_RAG_001_bm25_does_not_freeze_tokenizer():
    bm25_src = (_SRC / "bm25.py").read_text(encoding="utf-8")
    tok_src = (_SRC / "tokenize.py").read_text(encoding="utf-8")
    joined = bm25_src + tok_src
    assert "import jieba" not in joined
    assert "from jieba" not in joined
    assert "bge-reranker" not in joined
    assert "top-50" not in joined
    assert "k1=1.5" not in bm25_src
    assert "b=0.75" not in bm25_src


def test_FR_RAG_004_bm25_failure_falls_back_to_dense():
    records = (
        _chunk("chk_policy", "迟到三次以上记为旷工"),
        _chunk("chk_other", "差旅报销需提供发票"),
    )
    service = RetrievalService(
        corpus=records,
        dense=KeywordRetriever(records, "dense"),
        bm25=FailingRetriever(),
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=4, evidence_limit=4),
    )
    outcome = service.retrieve(RetrievalQuery(text="迟到", principal_id="usr_alice"))
    assert outcome.status == "ok"
    assert "bm25_failed" in outcome.warnings
    assert outcome.evidence


def test_FR_RAG_001_bm25_rerank_reorders_candidates():
    reranker = Bm25Reranker(SimpleLexTokenizer(), k1=1.2, b=0.75)
    ranked = reranker.rerank(
        "迟到书面警告",
        ("chk_weak", "chk_strong"),
        {
            "chk_weak": "差旅报销发票",
            "chk_strong": "迟到三次记书面警告",
        },
        2,
    )
    assert ranked[0].chunk_id == "chk_strong"
    assert ranked[0].source == "rerank"
    assert ranked[0].score >= ranked[1].score
