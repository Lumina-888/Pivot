"""Opt-in uvicorn SSE long connection. Not GATE-P0 verified."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path

import pytest
from harness import Pipeline, RetrievalBridge
from pivot.http import create_app
from pivot.qa.orchestrator import QaOrchestrator
from pivot.qa.writer import EvidenceJoinWriter
from pivot.stream.events import TERMINAL_EVENTS

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "sse-long-connection.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_GROUPED = _ROOT / "ops" / "run_grouped_tests.py"


class _SlowJoinWriter:
    def __init__(self, delay_s: float = 0.15) -> None:
        self._inner = EvidenceJoinWriter()
        self._delay_s = delay_s

    def draft(self, question: str, hits):
        time.sleep(self._delay_s)
        return self._inner.draft(question, hits)


def _require_sse_live() -> None:
    if os.environ.get("PIVOT_REQUIRE_SSE_LIVE") == "1":
        return
    pytest.skip("set PIVOT_REQUIRE_SSE_LIVE=1 to run uvicorn SSE long connection")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_FR_STREAM_002_sse_live_is_opt_in():
    grouped = _GROUPED.read_text(encoding="utf-8")
    assert "PIVOT_REQUIRE_SSE_LIVE" not in grouped
    assert "uvicorn" in grouped.lower()
    assert "does not start" in grouped.lower() or "不启动" in grouped.lower()


def test_GATE_P0_004_not_verified_by_sse_long_connection():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-004" in evidence
    assert "unverified" in evidence.lower()
    assert "sse" in evidence.lower() or "长连接" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-004" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")


def test_FR_STREAM_002_uvicorn_keeps_sse_open_until_terminal():
    _require_sse_live()
    import httpx
    import uvicorn

    pipeline = Pipeline()
    pipeline.ingest_policy_pdf("usr_alice")
    retrieval = pipeline.retrieval_for_ready_chunks()
    qa = QaOrchestrator(RetrievalBridge(retrieval), writer=_SlowJoinWriter())
    app = create_app(
        auth=pipeline.auth,
        retrieval=retrieval,
        runs=pipeline.runs,
        qa=qa,
    )
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 8
    while time.time() < deadline and not server.started:
        time.sleep(0.05)
    assert server.started
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10.0) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={"username": "alice", "password": "correct-password"},
                headers={"X-Request-ID": "req_live_login"},
            )
            assert login.status_code == 200
            token = login.json()["access_token"]
            created = client.post(
                "/api/v1/runs",
                json={
                    "conversation_id": "conv_alice",
                    "question": "late three times written warning?",
                    "idempotency_key": "idem-live",
                },
                headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_live_run"},
            )
            assert created.status_code == 200
            assert created.json()["initial_state"]["state"] == "received"
            run_id = created.json()["run_id"]
            names: list[str] = []
            with client.stream(
                "GET",
                f"/api/v1/runs/{run_id}/events",
                headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_live_sse"},
            ) as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers["content-type"]
                assert response.headers.get("x-accel-buffering", "").lower() == "no"
                buffer = ""
                for chunk in response.iter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        block, buffer = buffer.split("\n\n", 1)
                        name = ""
                        data_raw = ""
                        for line in block.splitlines():
                            if line.startswith("event:"):
                                name = line.split(":", 1)[1].strip()
                            elif line.startswith("data:"):
                                data_raw = line.split(":", 1)[1].strip()
                        if not name:
                            continue
                        names.append(name)
                        if data_raw:
                            payload = json.loads(data_raw)
                            assert "thinking" not in str(payload)
                            assert "SYSTEM_PROMPT" not in str(payload)
                        if name in TERMINAL_EVENTS:
                            break
                    if names and names[-1] in TERMINAL_EVENTS:
                        break
            assert names[0] == "run_started"
            assert names[-1] in TERMINAL_EVENTS
            assert sum(1 for name in names if name in TERMINAL_EVENTS) == 1
    finally:
        server.should_exit = True
        thread.join(timeout=5)
