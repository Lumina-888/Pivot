"""Answer publication regressions through the real QA execution boundary."""

from __future__ import annotations

import json

import pytest
from fakes import StaticRetriever
from pivot.qa.draft import draft_from_evidence
from pivot.qa.orchestrator import QaOrchestrator
from pivot.qa.ports import EvidenceHit, RetrievalResult
from pivot.qa.writer import HttpDraftWriter
from pivot.retrieval.fakes import ScriptedJsonHttpClient
from pivot.runs.service import RunService

HIT = EvidenceHit(
    chunk_id="chk_attendance",
    document_id="doc_attendance",
    version_id="ver_attendance",
    text="Three late arrivals count as an absence.",
    locator="page=1",
    external_llm_allowed=True,
)


def execute_content(content: str, hit: EvidenceHit = HIT, verifier=None):
    client = ScriptedJsonHttpClient(
        [{"choices": [{"message": {"content": content}}]}]
    )
    writer = HttpDraftWriter(
        client,
        endpoint="https://llm.test/v1/chat/completions",
        model="fixture-model",
        api_key="fixture-key",
    )
    return execute_writer(writer, hit, verifier)


def execute_writer(writer, hit=HIT, verifier=None, persist_result=None):
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_safety",
        owner_id="usr_safety",
        question="What is the attendance rule?",
        idempotency_key="idem_safety",
        request_id="req_safety",
    )
    log = runs.log(bundle.run.id)
    QaOrchestrator(
        StaticRetriever(RetrievalResult("ok", (hit,))), writer=writer, verifier=verifier
    ).execute(
        bundle, log, "req_safety",
        persist_result=runs.commit if persist_result is None
        else lambda value: persist_result(value, log),
    )
    return bundle, log


class PreviewWriter:
    def draft(self, question, hits):
        _, claims, citations = draft_from_evidence(hits)
        return "Every employee receives a million-dollar bonus.", claims, citations


class Judge:
    def __init__(self, result):
        self.result = result

    def verify(self, claims, citations, evidence):
        if self.result == "raise":
            raise TimeoutError("judge unavailable")
        # A judge cannot rewrite the facts it was asked to assess.
        if self.result == "mutate":
            claims[0]["text"] = "Million-dollar bonus."
            return "answered"
        return self.result


def test_FR_AGENT_005_commit_failure_never_publishes_answer():
    captured = []

    def persist(bundle, log):
        captured.append((bundle, log))
        raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        execute_writer(PreviewWriter(), persist_result=persist)
    bundle, log = captured[0]
    assert bundle.run.state == "failed"
    assert bundle.run.answer_markdown is None
    assert bundle.claims == []
    assert bundle.citations == []
    assert not any(name in {"token", "citation", "completed"} for name, _ in log.replay())


def test_FR_AGENT_005_publishes_only_after_verified_result_commit():
    observations = []

    def persist(bundle, log):
        observations.append((bundle.run.state, [name for name, _ in log.replay()]))

    bundle, log = execute_writer(PreviewWriter(), persist_result=persist)
    assert observations[0][0] == "answered"
    assert set(observations[0][1]).isdisjoint({"token", "citation", "completed"})
    frames = log.replay()
    assert "".join(data["payload"]["text"] for name, data in frames if name == "token") == HIT.text
    assert frames[-1][0] == "completed"
    assert all(data["stage"] == "answered" for name, data in frames if name == "token")
    assert bundle.run.answer_markdown == HIT.text


def test_FR_AGENT_005_renderer_neutralizes_active_markup():
    hit = EvidenceHit("chk", "doc", "ver", '<script>alert(1)</script> [pay](javascript:evil)')
    bundle, log = execute_writer(PreviewWriter(), hit=hit)
    assert bundle.run.state == "answered"
    assert bundle.run.answer_markdown == (
        r'&lt;script&gt;alert(1)&lt;/script&gt; \[pay\](javascript:evil)'
    )
    assert "<script>" not in str(log.replay())


def test_FR_AGENT_005_renderer_ignores_writer_markdown():
    bundle, _ = execute_writer(PreviewWriter())
    assert bundle.run.state == "answered"
    assert bundle.run.answer_markdown == HIT.text


@pytest.mark.parametrize("result", ["raise", "garbage", True, {"supported": True}, "mutate"])
def test_FR_QA_004_verifier_failure_never_answers(result):
    bundle, log = execute_content(
        json.dumps({"claims": [{"text": HIT.text, "evidence_index": 0}]}),
        verifier=Judge(result),
    )
    assert bundle.run.state == "uncertain"
    assert bundle.run.error_code == "VERIFICATION_UNAVAILABLE"
    assert bundle.run.answer_markdown is None
    assert bundle.claims == []
    assert not any(name in {"token", "citation", "completed"} for name, _ in log.replay())


def test_FR_QA_004_judge_cannot_bypass_support_gate():
    bundle, _ = execute_content(
        json.dumps({"claims": [{"text": "Million-dollar bonus.", "evidence_index": 0}]}),
        verifier=Judge("answered"),
    )
    assert bundle.run.state != "answered"
    assert bundle.run.answer_markdown is None


def test_FR_AGENT_005_unverified_markdown_never_published():
    bundle, log = execute_content("Every employee receives a million-dollar bonus.")
    assert bundle.run.state != "answered"
    assert bundle.run.answer_markdown is None
    assert not any(name in {"token", "citation", "completed"} for name, _ in log.replay())


@pytest.mark.parametrize(
    "payload",
    [
        {"markdown": "Million-dollar bonus."},
        {"claims": []},
        {"claims": [{"text": HIT.text, "evidence_index": 99}]},
        {"claims": [{"text": HIT.text, "evidence_index": True}]},
        {"claims": [{"text": HIT.text, "evidence_index": 0}, None]},
        {"claims": [{"text": HIT.text, "chunk_id": HIT.chunk_id}]},
        {"claims": [{"text": HIT.text, "evidence_index": 0, "support": "supported"}]},
    ],
)
def test_FR_QA_002_invalid_structure_rejects_entire_answer(payload):
    bundle, log = execute_content(json.dumps(payload))
    assert bundle.run.state != "answered"
    assert bundle.run.answer_markdown is None
    assert bundle.claims == []
    assert bundle.citations == []
    assert not any(name in {"token", "citation", "completed"} for name, _ in log.replay())


@pytest.mark.parametrize(
    "evidence,claim",
    [
        ("迟到三次以上记为旷工。", "迟到一次记为旷工。"),
        ("限额为100元。", "限额为1000000元。"),
        ("2026-10-01生效。", "2026-01-01生效。"),
        ("只有审批通过才可报销。", "可报销。"),
        ("不得发放奖金。", "发放奖金。"),
        ("v2版本额度为100元。", "v1版本额度为100元。"),
        ("可以报销。仅限审批通过的员工。", "可以报销。"),
    ],
)
def test_FR_QA_002_unsupported_claim_never_answers(evidence, claim):
    hit = EvidenceHit("chk", "doc", "ver", evidence, external_llm_allowed=True)
    bundle, log = execute_content(
        json.dumps({"claims": [{"text": claim, "evidence_index": 0}]}), hit
    )
    assert bundle.run.state != "answered"
    assert bundle.run.answer_markdown is None
    assert bundle.claims == []
    assert not any(name in {"token", "citation", "completed"} for name, _ in log.replay())
