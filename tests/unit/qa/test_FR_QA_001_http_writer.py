"""HTTP draft writer. Endpoint/model stay injected, not frozen."""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes import StaticRetriever, ok_retriever
from pivot.qa.errors import WriterError
from pivot.qa.orchestrator import QaOrchestrator
from pivot.qa.ports import EvidenceHit, RetrievalResult
from pivot.qa.writer import FailoverDraftWriter, HttpDraftWriter
from pivot.retrieval.fakes import ScriptedJsonHttpClient
from pivot.retrieval.providers import JsonHttpError
from pivot.runs.service import RunService
from pivot.stream.events import FORBIDDEN_PAYLOAD_KEYS

_SRC = Path(__file__).resolve().parents[3] / "api" / "src" / "pivot" / "qa"

ALLOWED_HIT = EvidenceHit(
    chunk_id="chk_a",
    document_id="doc_a",
    version_id="ver_a",
    text="迟到三次以上记为旷工",
    locator="page=1",
    external_llm_allowed=True,
)

FORBIDDEN_HIT = EvidenceHit(
    chunk_id="chk_a",
    document_id="doc_a",
    version_id="ver_a",
    text="迟到三次以上记为旷工",
    locator="page=1",
    external_llm_allowed=False,
)


def _chat(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def _writer(client, **overrides) -> HttpDraftWriter:
    values = dict(
        endpoint="https://llm.test/v1/chat/completions",
        model="injected-chat-model",
        api_key="secret-llm-key",
        timeout_seconds=1.5,
    )
    values.update(overrides)
    return HttpDraftWriter(client, **values)


def test_FR_QA_001_http_writer_posts_injected_model_and_messages():
    client = ScriptedJsonHttpClient([_chat("书面警告。")])
    markdown, claims, citations = _writer(client).draft("迟到怎么处理", (ALLOWED_HIT,))
    assert markdown == "书面警告。"
    assert claims
    assert citations[0]["chunk_id"] == "chk_a"
    call = client.calls[0]
    assert call["url"] == "https://llm.test/v1/chat/completions"
    assert call["payload"]["model"] == "injected-chat-model"
    assert call["payload"]["messages"][0]["role"] == "system"
    assert "迟到怎么处理" in call["payload"]["messages"][1]["content"]
    assert "迟到三次以上记为旷工" in call["payload"]["messages"][1]["content"]
    assert call["headers"]["Authorization"] == "Bearer secret-llm-key"
    assert call["timeout"] == 1.5


def test_FR_QA_001_http_writer_uses_injected_auth_header():
    client = ScriptedJsonHttpClient([_chat("ok")])
    _writer(client, auth_header="api-key", auth_scheme=None).draft(
        "迟到怎么处理", (ALLOWED_HIT,)
    )
    assert client.calls[0]["headers"] == {"api-key": "secret-llm-key"}
    assert "Authorization" not in client.calls[0]["headers"]


def test_FR_QA_001_http_writer_does_not_hardcode_vendor():
    src = (_SRC / "writer.py").read_text(encoding="utf-8")
    lowered = src.lower()
    assert "siliconflow" not in lowered
    assert "deepseek" not in lowered
    assert "openai.com" not in lowered
    assert "mimo-v2.5" not in lowered
    assert "deepseek-flash" not in lowered
    assert "timeout=30" not in src.replace(" ", "")


def test_FR_QA_002_http_writer_citations_stay_in_evidence():
    client = ScriptedJsonHttpClient(
        [
            _chat(
                '{"markdown":"迟到三次以上记为旷工。","claims":[{"text":"迟到三次以上记为旷工","evidence_index":0}]}'
            )
        ]
    )
    markdown, claims, citations = _writer(client).draft("迟到怎么处理", (ALLOWED_HIT,))
    assert "旷工" in markdown
    assert all(item["chunk_id"] == "chk_a" for item in citations)
    assert all(item["document_id"] == "doc_a" for item in citations)


def test_FR_QA_002_http_writer_drops_out_of_candidate_citations():
    client = ScriptedJsonHttpClient(
        [
            _chat(
                '{"markdown":"董事会秘密。","claims":['
                '{"text":"invented","chunk_id":"chk_outside"},'
                '{"text":"迟到三次以上记为旷工","evidence_index":0}'
                "]}"
            )
        ]
    )
    _, claims, citations = _writer(client).draft("迟到怎么处理", (ALLOWED_HIT,))
    assert all(item["chunk_id"] == "chk_a" for item in citations)
    assert all("invented" not in item["text"] for item in claims)
    assert claims[0]["text"] == "迟到三次以上记为旷工"


def test_FR_QA_003_http_writer_skips_http_when_external_llm_not_allowed():
    client = ScriptedJsonHttpClient([_chat("should not send")])
    with pytest.raises(WriterError) as caught:
        _writer(client).draft("迟到怎么处理", (FORBIDDEN_HIT,))
    assert caught.value.code == "EXTERNAL_LLM_NOT_ALLOWED"
    assert client.calls == []
    assert "secret-llm-key" not in str(caught.value)


def test_FR_QA_001_http_writer_timeout_is_provider_timeout():
    client = ScriptedJsonHttpClient(error=JsonHttpError("slow", timeout=True))
    with pytest.raises(WriterError) as caught:
        _writer(client).draft("迟到怎么处理", (ALLOWED_HIT,))
    assert caught.value.code == "PROVIDER_TIMEOUT"


def test_FR_QA_001_http_writer_429_is_rate_limited():
    client = ScriptedJsonHttpClient(error=JsonHttpError("limited", status=429))
    with pytest.raises(WriterError) as caught:
        _writer(client).draft("迟到怎么处理", (ALLOWED_HIT,))
    assert caught.value.code == "PROVIDER_RATE_LIMITED"


def test_FR_QA_001_http_writer_5xx_is_temporary():
    client = ScriptedJsonHttpClient(error=JsonHttpError("upstream", status=503))
    with pytest.raises(WriterError) as caught:
        _writer(client).draft("迟到怎么处理", (ALLOWED_HIT,))
    assert caught.value.code == "PROVIDER_TEMPORARY_ERROR"


def test_FR_QA_001_http_writer_does_not_leak_api_key():
    client = ScriptedJsonHttpClient(error=RuntimeError("secret-llm-key exploded"))
    with pytest.raises(WriterError) as caught:
        _writer(client).draft("迟到怎么处理", (ALLOWED_HIT,))
    assert "secret-llm-key" not in str(caught.value)
    assert "secret-llm-key" not in repr(caught.value)


def test_FR_QA_001_http_writer_falls_back_on_primary_timeout():
    client = ScriptedJsonHttpClient(
        [_chat("ignored")],
        handler=lambda url, payload, headers, timeout: (
            (_ for _ in ()).throw(JsonHttpError("slow", timeout=True))
            if "primary" in url
            else _chat("备用书面警告")
        ),
    )
    primary = _writer(
        client,
        endpoint="https://primary.test/v1/chat/completions",
        model="primary-model",
        api_key="secret-primary-key",
    )
    fallback = _writer(
        client,
        endpoint="https://fallback.test/v1/chat/completions",
        model="fallback-model",
        api_key="secret-fallback-key",
        auth_header="api-key",
    )
    writer = FailoverDraftWriter(primary, fallback)
    markdown, _, _ = writer.draft("迟到怎么处理", (ALLOWED_HIT,))
    assert markdown == "备用书面警告"
    assert client.calls[0]["url"] == "https://primary.test/v1/chat/completions"
    assert client.calls[1]["url"] == "https://fallback.test/v1/chat/completions"
    assert client.calls[1]["payload"]["model"] == "fallback-model"
    assert client.calls[1]["headers"] == {"api-key": "secret-fallback-key"}


def test_FR_QA_001_http_writer_does_not_fallback_on_not_allowed():
    client = ScriptedJsonHttpClient([_chat("no")])
    writer = FailoverDraftWriter(
        _writer(client, endpoint="https://primary.test/v1/chat"),
        _writer(client, endpoint="https://fallback.test/v1/chat"),
    )
    with pytest.raises(WriterError) as caught:
        writer.draft("迟到怎么处理", (FORBIDDEN_HIT,))
    assert caught.value.code == "EXTERNAL_LLM_NOT_ALLOWED"
    assert client.calls == []


def test_FR_QA_001_http_writer_fallback_uses_separate_endpoint_and_key():
    src = (_SRC / "writer.py").read_text(encoding="utf-8")
    assert "PIVOT_LLM_FALLBACK" not in src
    assert "secret-primary-key" not in src


def test_FR_QA_005_http_writer_events_do_not_expose_prompt():
    client = ScriptedJsonHttpClient([_chat("书面警告。")])
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_http",
        request_id="req_http",
    )
    retriever = StaticRetriever(RetrievalResult(status="ok", evidence=(ALLOWED_HIT,)))
    QaOrchestrator(retriever, writer=_writer(client)).execute(
        bundle, runs.log(bundle.run.id), "req_http"
    )
    assert bundle.run.state == "answered"
    assert bundle.run.answer_markdown == "书面警告。"
    for _name, data in runs.log(bundle.run.id).replay():
        payload = data["payload"]
        assert FORBIDDEN_PAYLOAD_KEYS.isdisjoint(payload)
        blob = str(payload).lower()
        assert "system" not in payload
        assert "thinking" not in blob
        assert "secret-llm-key" not in blob
        assert "answer only from the provided evidence" not in blob


def test_FR_QA_003_http_writer_run_refuses_without_outbound_when_not_allowed():
    client = ScriptedJsonHttpClient([_chat("no")])
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_deny",
        request_id="req_deny",
    )
    retriever = StaticRetriever(RetrievalResult(status="ok", evidence=(FORBIDDEN_HIT,)))
    QaOrchestrator(retriever, writer=_writer(client)).execute(
        bundle, runs.log(bundle.run.id), "req_deny"
    )
    assert bundle.run.state == "refused"
    assert bundle.run.error_code == "EXTERNAL_LLM_NOT_ALLOWED"
    assert bundle.run.answer_markdown is None
    assert client.calls == []


def test_FR_QA_001_local_writer_still_answers_without_http():
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_local",
        request_id="req_local",
    )
    QaOrchestrator(ok_retriever()).execute(bundle, runs.log(bundle.run.id), "req_local")
    assert bundle.run.state == "answered"
    assert "旷工" in (bundle.run.answer_markdown or "")
