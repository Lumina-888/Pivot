from __future__ import annotations

import pytest
from pivot.runs.errors import RunError
from pivot.runs.service import RunService


def test_FR_STREAM_001_same_key_and_params_return_same_run():
    service = RunService()
    first = service.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    second = service.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_1",
        request_id="req_2",
    )
    assert first.run.id == second.run.id
    assert first.run.message_id == second.run.message_id


def test_FR_STREAM_001_same_key_different_params_conflict():
    service = RunService()
    service.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    with pytest.raises(RunError) as error:
        service.create(
            conversation_id="conv_1",
            owner_id="usr_a",
            question="另一问题",
            idempotency_key="idem_1",
            request_id="req_2",
        )
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
