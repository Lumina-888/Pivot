"""契约测试：Worker 内部契约（SPEC §5.7）。

status ∈ {ok, insufficient, failed} 的分支约束：
- ok：必须携带 content 与 citations，error_code 必须为 null；
- insufficient：不得携带非空 error_code（输出不足而非失败）；
- failed：必须携带非空 error_code 与 trace；
- confidence 可为 number 或 null；trace 必须含 stage/duration_ms；
- 未知 status / 多余字段被拒绝。
"""

import pytest

from conftest import validate

WORKER_OK = {
    "status": "ok",
    "content": {"answer": "迟到 3 次以上记为旷工"},
    "citations": [],
    "confidence": None,
    "error_code": None,
    "trace": {"stage": "draft", "duration_ms": 120},
}

WORKER_INSUFFICIENT = {
    "status": "insufficient",
    "content": None,
    "citations": [],
    "confidence": None,
    "error_code": None,
    "trace": {"stage": "retrieve", "duration_ms": 40},
}

WORKER_FAILED = {
    "status": "failed",
    "content": None,
    "citations": [],
    "confidence": None,
    "error_code": "PROVIDER_TIMEOUT",
    "trace": {"stage": "draft", "duration_ms": 900},
}


def test_worker_ok_example_validates(worker_schema):
    validate(WORKER_OK, worker_schema)


def test_worker_insufficient_example_validates(worker_schema):
    validate(WORKER_INSUFFICIENT, worker_schema)


def test_worker_failed_example_validates(worker_schema):
    validate(WORKER_FAILED, worker_schema)


def test_worker_ok_with_error_code_rejected(worker_schema):
    bad = dict(WORKER_OK, error_code="PROVIDER_TIMEOUT")
    with pytest.raises(Exception):
        validate(bad, worker_schema)


def test_worker_failed_without_error_code_rejected(worker_schema):
    bad = {k: v for k, v in WORKER_FAILED.items() if k != "error_code"}
    with pytest.raises(Exception):
        validate(bad, worker_schema)


def test_worker_unknown_status_rejected(worker_schema):
    bad = dict(WORKER_OK, status="pending")
    with pytest.raises(Exception):
        validate(bad, worker_schema)


def test_worker_trace_required_fields(worker_schema):
    bad = dict(WORKER_OK)
    bad["trace"] = {"stage": "draft"}  # 缺 duration_ms
    with pytest.raises(Exception):
        validate(bad, worker_schema)


def test_worker_confidence_typing(worker_schema):
    bad = dict(WORKER_OK, confidence="high")
    with pytest.raises(Exception):
        validate(bad, worker_schema)


def test_worker_extra_field_rejected(worker_schema):
    bad = dict(WORKER_OK, provider_logs="secret")
    with pytest.raises(Exception):
        validate(bad, worker_schema)


def test_worker_status_enum_matches_spec(worker_schema):
    """SPEC §5.7：status ∈ {ok, insufficient, failed}。"""
    statuses = {branch["properties"]["status"]["const"] for branch in worker_schema["oneOf"]}
    assert statuses == {"ok", "insufficient", "failed"}
