"""2026-11-03 local-real-deps defect 2 residual: /search BM25 leg.

The leg used to be a startup snapshot: bootstrap scrolled the base
collection once at assembly, so documents ingested after startup
did not enter the leg until the next restart. LiveBm25Retriever
rebuilds from the base collection on every search() instead, so
ingest, claim/move, delete and supersede are visible without a
restart, in any process, with no persistent sparse index and no
in-process add() that a Celery worker could miss.

The base collection is never cleaned on delete or supersede
(IndexPublisher has no delete; request_delete only flips DB
flags), so a rebuilt leg must filter by live version facts, or
stale points with stale ready/current payload flags would keep
being served. That filter is part of the implementation, not a
test-only guard, and it is exercised here by flipping the live
facts while the payload list stays unchanged.
"""

from __future__ import annotations

import time

from pivot.retrieval.bm25 import LiveBm25Retriever
from pivot.retrieval.fakes import KeywordRetriever
from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService
from pivot.retrieval.tokenize import SimpleLexTokenizer


class _Facts:
    def __init__(self) -> None:
        self.by_version: dict[str, dict] = {}

    def set(self, version_id, *, library_id, folder_id=None, live=True) -> None:
        self.by_version[version_id] = {
            "library_id": library_id,
            "folder_id": folder_id,
            "live": live,
        }

    def library_id_for(self, version_id):
        entry = self.by_version.get(version_id)
        return entry["library_id"] if entry else None

    def folder_id_for(self, version_id):
        entry = self.by_version.get(version_id)
        return entry["folder_id"] if entry else None

    def version_is_live(self, version_id):
        entry = self.by_version.get(version_id)
        return bool(entry and entry["live"])


def _payload(chunk_id, version_id, document_id, text, *, library_id="dept_old"):
    return {
        "chunk_id": chunk_id,
        "version_id": version_id,
        "document_id": document_id,
        "payload": {
            "chunk_id": chunk_id,
            "version_id": version_id,
            "document_id": document_id,
            "text": text,
            "title": "doc",
            "library_id": library_id,
            "ready": True,
            "current": True,
            "allowed": True,
        },
    }


def _retriever(payloads, facts):
    return LiveBm25Retriever(
        lambda: tuple(payloads),
        SimpleLexTokenizer(),
        k1=1.2,
        b=0.75,
        library_id_for=facts.library_id_for,
        folder_id_for=facts.folder_id_for,
        version_is_live=facts.version_is_live,
        source="bm25",
    )


def _service(bm25):
    return RetrievalService(
        corpus=(),
        dense=KeywordRetriever((), "dense"),
        bm25=bm25,
        policy=RetrievalPolicy(dense_k=5, bm25_k=5, rrf_k=60, evidence_limit=5),
        reranker=None,
    )


def test_live_rebuild_sees_new_ingest_without_restart():
    facts = _Facts()
    facts.set("ver_1", library_id="dept_old")
    payloads = [_payload("chk_1", "ver_1", "doc_1", "alpha beta")]
    retriever = _retriever(payloads, facts)
    assert [hit.chunk_id for hit in retriever.search("alpha", 5)] == ["chk_1"]
    # Ingest after the first search: no restart, no add() call.
    facts.set("ver_2", library_id="dept_old")
    payloads.append(_payload("chk_2", "ver_2", "doc_2", "gamma delta"))
    hits = retriever.search("gamma", 5)
    assert [hit.chunk_id for hit in hits] == ["chk_2"]
    assert retriever.resolve("chk_2") is not None


def test_live_rebuild_reflects_claim_move_without_restart():
    facts = _Facts()
    facts.set("ver_1", library_id="dept_old")
    payloads = [_payload("chk_1", "ver_1", "doc_1", "alpha beta")]
    retriever = _retriever(payloads, facts)
    assert retriever.search("alpha", 5)
    assert retriever.resolve("chk_1").library_id == "dept_old"
    # Claim/move: the payload library stays stale, live facts move.
    facts.set("ver_1", library_id="dept_new")
    assert retriever.search("alpha", 5)
    assert retriever.resolve("chk_1").library_id == "dept_new"
    # And the service filter now sees the new library, not the old one.
    outcome = _service(retriever).retrieve(
        RetrievalQuery(
            "alpha", "user_1", library_ids=("dept_new",), visible_folder_ids=()
        )
    )
    assert outcome.status == "ok"
    assert [item.chunk_id for item in outcome.evidence] == ["chk_1"]


def test_live_rebuild_drops_deleted_chunk():
    facts = _Facts()
    facts.set("ver_1", library_id="dept_old")
    payloads = [_payload("chk_1", "ver_1", "doc_1", "alpha beta")]
    retriever = _retriever(payloads, facts)
    assert retriever.search("alpha", 5)
    # Delete: the point stays in the base collection (stale flags),
    # only the live facts change.
    facts.set("ver_1", library_id="dept_old", live=False)
    assert retriever.search("alpha", 5) == ()
    assert retriever.resolve("chk_1") is None


def test_live_rebuild_drops_superseded_version_chunk():
    facts = _Facts()
    facts.set("ver_1", library_id="dept_old")
    facts.set("ver_2", library_id="dept_old")
    payloads = [
        _payload("chk_1", "ver_1", "doc_1", "alpha beta"),
        _payload("chk_2", "ver_2", "doc_1", "gamma delta"),
    ]
    retriever = _retriever(payloads, facts)
    assert [hit.chunk_id for hit in retriever.search("alpha", 5)] == ["chk_1"]
    # Supersede: the old point stays, only its version stops being live.
    facts.set("ver_1", library_id="dept_old", live=False)
    assert retriever.search("alpha", 5) == ()
    assert [hit.chunk_id for hit in retriever.search("gamma", 5)] == ["chk_2"]


def test_live_rebuild_restart_consistent():
    facts = _Facts()
    facts.set("ver_1", library_id="dept_old")
    facts.set("ver_2", library_id="dept_old")
    payloads = [
        _payload("chk_1", "ver_1", "doc_1", "alpha beta"),
        _payload("chk_2", "ver_2", "doc_2", "gamma delta"),
    ]
    before = [hit.chunk_id for hit in _retriever(payloads, facts).search("gamma", 5)]
    # A restart is a fresh wrapper over the same payloads and facts.
    after = [hit.chunk_id for hit in _retriever(payloads, facts).search("gamma", 5)]
    assert before == after == ["chk_2"]


def test_service_bm25_leg_nonempty_and_rrf_not_dense_only():
    facts = _Facts()
    facts.set("ver_1", library_id="dept_old")
    payloads = [_payload("chk_1", "ver_1", "doc_1", "alpha beta")]
    retriever = _retriever(payloads, facts)
    # The dense leg is empty on purpose: if the BM25 leg were empty
    # too, RRF would have nothing to fuse and the outcome would be
    # empty. A non-empty outcome here proves the BM25 leg fired.
    assert retriever.search("alpha", 5) != ()
    service = _service(retriever)
    outcome = service.retrieve(
        RetrievalQuery(
            "alpha", "user_1", library_ids=("dept_old",), visible_folder_ids=()
        )
    )
    assert outcome.status == "ok"
    assert [item.chunk_id for item in outcome.evidence] == ["chk_1"]
    assert any(
        note.provider == "bm25" and note.status == "ok"
        for note in service.provider_calls
    )


def test_live_rebuild_failure_degrades_to_empty_bm25_leg():
    state = {"fail": True}
    facts = _Facts()
    facts.set("ver_1", library_id="dept_old")
    payloads = [_payload("chk_1", "ver_1", "doc_1", "alpha beta")]

    def _load():
        if state["fail"]:
            raise RuntimeError("qdrant unavailable")
        return tuple(payloads)

    retriever = LiveBm25Retriever(
        _load,
        SimpleLexTokenizer(),
        k1=1.2,
        b=0.75,
        library_id_for=facts.library_id_for,
        folder_id_for=facts.folder_id_for,
        version_is_live=facts.version_is_live,
        source="bm25",
    )
    assert retriever.search("alpha", 5) == ()
    assert retriever.resolve("chk_1") is None
    # The service degrades to empty, it does not fail the whole query.
    outcome = _service(retriever).retrieve(
        RetrievalQuery(
            "alpha", "user_1", library_ids=("dept_old",), visible_folder_ids=()
        )
    )
    assert outcome.status == "empty"
    # Recovery on the next query, once the store is back.
    state["fail"] = False
    assert [hit.chunk_id for hit in retriever.search("alpha", 5)] == ["chk_1"]


def test_live_rebuild_manual_add_still_works():
    facts = _Facts()
    retriever = LiveBm25Retriever(
        lambda: (),
        SimpleLexTokenizer(),
        k1=1.2,
        b=0.75,
        library_id_for=facts.library_id_for,
        folder_id_for=facts.folder_id_for,
        version_is_live=facts.version_is_live,
        source="bm25",
    )
    from pivot.retrieval.models import ChunkRecord

    retriever.add(
        (
            ChunkRecord(
                chunk_id="chk_manual",
                version_id="ver_manual",
                document_id="doc_manual",
                text="alpha beta",
                title="doc",
                library_id="dept_old",
            ),
        )
    )
    assert [hit.chunk_id for hit in retriever.search("alpha", 5)] == ["chk_manual"]


def test_live_rebuild_performance_16_100_1000():
    facts = _Facts()
    payloads = []
    for index in range(1000):
        version_id = f"ver_{index}"
        facts.set(version_id, library_id="dept_old")
        payloads.append(
            _payload(
                f"chk_{index}",
                version_id,
                f"doc_{index}",
                f"commonword term{index} filler",
            )
        )
    timings = {}
    for size in (16, 100, 1000):
        facts_small = _Facts()
        small = payloads[:size]
        for item in small:
            facts_small.set(
                item["payload"]["version_id"], library_id="dept_old"
            )
        small_retriever = _retriever(small, facts_small)
        started = time.perf_counter()
        hits = small_retriever.search("commonword", 5)
        timings[size] = time.perf_counter() - started
        assert len(hits) == 5
    # Generous bound: this is a correctness-plus-scale smoke test,
    # the measured numbers for the PR description come from the
    # benchmark run, not from this assertion.
    assert timings[1000] < 5.0
    assert timings[100] < 5.0
    assert timings[16] < 5.0
