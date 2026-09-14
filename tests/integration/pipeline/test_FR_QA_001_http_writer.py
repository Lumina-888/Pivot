"""Runtime HTTP Draft Writer wiring. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path

import pytest
from pivot.documents.ports import VersionRecord
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.http.bootstrap import _RetrievalBridge
from pivot.http.memory import MemoryVersions
from pivot.qa.orchestrator import QaOrchestrator
from pivot.qa.ports import EvidenceHit, RetrievalResult
from pivot.qa.writer import EvidenceJoinWriter, FailoverDraftWriter, HttpDraftWriter
from pivot.retrieval.fakes import KeywordRetriever, ScriptedJsonHttpClient
from pivot.retrieval.models import ChunkRecord
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService
from pivot.runs.service import RunService

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "http-draft-writer.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_WRITER = _ROOT / "api" / "src" / "pivot" / "qa" / "writer.py"
_BOOTSTRAP = _ROOT / "api" / "src" / "pivot" / "http" / "bootstrap.py"

ALLOWED_HIT = EvidenceHit(
    chunk_id="chk_a",
    document_id="doc_a",
    version_id="ver_a",
    text="迟到三次以上记为旷工",
    locator="page=1",
    external_llm_allowed=True,
)


class _StaticRetriever:
    def __init__(self, hit: EvidenceHit) -> None:
        self._hit = hit

    def retrieve(self, question, *, scope_type, scope_document_id, principal_id):
        del question, scope_type, scope_document_id, principal_id
        return RetrievalResult(status="ok", evidence=(self._hit,))


def _settings(**overrides: object) -> RuntimeSettings:
    values: dict[str, object] = {
        "storage": "memory",
        "token_secret": "runtime-test-secret",
        "access_ttl": 60,
        "refresh_ttl": 3600,
        "export_ttl": 3600,
        "download_ttl": 300,
        "export_public_base": "https://files.pivot.test",
        "bootstrap_username": "admin",
        "bootstrap_password": "runtime-admin-password",
        "retrieval_k": 4,
        "argon2_time_cost": 1,
        "argon2_memory_cost": 8,
        "argon2_parallelism": 1,
    }
    values.update(overrides)
    return RuntimeSettings(**values)


def _chat(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def _llm_http_settings(**overrides: object) -> RuntimeSettings:
    values: dict[str, object] = {
        "llm": "http",
        "llm_endpoint": "https://llm.test/v1/chat/completions",
        "llm_model": "injected-chat-model",
        "llm_api_key": "secret-llm-key",
        "json_http_client": ScriptedJsonHttpClient([_chat("书面警告。")]),
    }
    values.update(overrides)
    return _settings(**values)


def test_NFR_OBS_runtime_http_llm_requires_endpoint_model_key():
    with pytest.raises(RuntimeError, match="PIVOT_LLM_ENDPOINT"):
        assemble_runtime(_settings(llm="http"))


def test_NFR_OBS_runtime_http_llm_wires_writer():
    assembly = assemble_runtime(_llm_http_settings())
    assert isinstance(assembly.draft_writer, HttpDraftWriter)
    assert not isinstance(assembly.draft_writer, EvidenceJoinWriter)
    fallback = assemble_runtime(
        _llm_http_settings(
            llm_fallback_endpoint="https://fallback.test/v1/chat/completions",
            llm_fallback_model="injected-fallback-model",
            llm_fallback_api_key="secret-fallback-key",
            llm_fallback_auth_header="api-key",
        )
    )
    assert isinstance(fallback.draft_writer, FailoverDraftWriter)


def test_FR_QA_001_runtime_http_writer_answers():
    assembly = assemble_runtime(_llm_http_settings())
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_runtime",
        owner_id="usr_admin",
        question="迟到怎么处理",
        idempotency_key="idem_runtime_llm",
        request_id="req_runtime_llm",
    )
    QaOrchestrator(
        _StaticRetriever(ALLOWED_HIT), writer=assembly.draft_writer
    ).execute(bundle, runs.log(bundle.run.id), "req_runtime_llm")
    assert bundle.run.state == "answered"
    assert bundle.run.answer_markdown == "书面警告。"
    assert all(item["chunk_id"] == "chk_a" for item in bundle.citations)


def test_FR_QA_003_runtime_http_writer_refuses_when_not_allowed():
    client = ScriptedJsonHttpClient([_chat("should not send")])
    assembly = assemble_runtime(_llm_http_settings(json_http_client=client))
    hit = EvidenceHit(
        chunk_id="chk_a",
        document_id="doc_a",
        version_id="ver_denied",
        text="迟到三次以上记为旷工",
        external_llm_allowed=False,
    )
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_deny",
        owner_id="usr_admin",
        question="迟到怎么处理",
        idempotency_key="idem_deny_llm",
        request_id="req_deny_llm",
    )
    QaOrchestrator(_StaticRetriever(hit), writer=assembly.draft_writer).execute(
        bundle, runs.log(bundle.run.id), "req_deny_llm"
    )
    assert bundle.run.state == "refused"
    assert bundle.run.error_code == "EXTERNAL_LLM_NOT_ALLOWED"
    assert client.calls == []


def test_FR_QA_003_runtime_bridge_reads_version_external_llm_flag():
    store = MemoryVersions()
    store.save(
        VersionRecord(
            id="ver_ok",
            document_id="doc_ok",
            content_sha256="abc",
            storage_key="quarantine/doc_ok/ver_ok",
            state="ready",
            current=True,
            external_llm_allowed=True,
        )
    )
    chunk = ChunkRecord(
        chunk_id="chk_ok",
        version_id="ver_ok",
        document_id="doc_ok",
        text="迟到三次以上记为旷工",
        title="Attendance Policy",
        space="hr",
        ready=True,
        current=True,
        allowed=True,
        index_generation="gen_llm",
        embedding_model_version="hash",
        retrieval_config_version="runtime-injected",
    )
    retrieval = RetrievalService(
        corpus=(chunk,),
        dense=KeywordRetriever((chunk,), "dense"),
        bm25=KeywordRetriever((chunk,), "bm25"),
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=4, evidence_limit=4),
    )
    allowed = _RetrievalBridge(retrieval, store).retrieve(
        "迟到",
        scope_type="global",
        scope_document_id=None,
        principal_id="usr_admin",
    )
    assert allowed.status == "ok"
    assert allowed.evidence[0].external_llm_allowed is True
    store.save(
        VersionRecord(
            id="ver_ok",
            document_id="doc_ok",
            content_sha256="abc",
            storage_key="quarantine/doc_ok/ver_ok",
            state="ready",
            current=True,
            external_llm_allowed=False,
        )
    )
    denied = _RetrievalBridge(retrieval, store).retrieve(
        "迟到",
        scope_type="global",
        scope_document_id=None,
        principal_id="usr_admin",
    )
    assert denied.evidence[0].external_llm_allowed is False


def test_GATE_P0_004_not_verified_by_http_writer():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-004" in evidence
    assert "unverified" in evidence.lower()
    assert "Fake" in evidence or "fake" in evidence.lower()
    writer = _WRITER.read_text(encoding="utf-8").lower()
    assert "deepseek" not in writer
    assert "siliconflow" not in writer
    bootstrap = _BOOTSTRAP.read_text(encoding="utf-8").lower()
    assert "deepseek-flash" not in bootstrap
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-004" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
