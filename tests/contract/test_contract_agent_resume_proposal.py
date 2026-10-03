"""ND-AGENT-03-A proposal checks, not runtime authorization/resume acceptance."""

import json

import jsonschema
import pytest


@pytest.fixture(scope="module")
def proposal_schema(repo_root):
    path = repo_root / "spec/contracts/proposals/agent-resume.schema.json"
    assert path.is_file(), "ND-AGENT-03-A proposed schema is missing (Red)"
    return json.loads(path.read_text(encoding="utf-8"))


def validator(schema, component):
    document = {**schema, "$ref": f"#/$defs/{component}"}
    jsonschema.Draft202012Validator.check_schema(document)
    return jsonschema.Draft202012Validator(document)


def test_FR_AGENT_007_resume_request_shape(proposal_schema):
    validator(proposal_schema, "ResumeRequest").validate(
        {
            "clarification_id": "clarify_001",
            "answer": "Use the current policy.",
            "idempotency_key": "resume_001",
        }
    )


@pytest.mark.parametrize("field", ["clarification_id", "answer", "idempotency_key"])
@pytest.mark.parametrize("value", [None, True, 7, [], {}, "", " \t\n"])
def test_FR_AGENT_007_resume_request_rejects_invalid_fields(proposal_schema, field, value):
    body = {
        "clarification_id": "clarify_001",
        "answer": "Use the current policy.",
        "idempotency_key": "resume_001",
    }
    body[field] = value
    with pytest.raises(jsonschema.ValidationError):
        validator(proposal_schema, "ResumeRequest").validate(body)


@pytest.mark.parametrize("field", ["clarification_id", "answer", "idempotency_key"])
def test_FR_AGENT_007_resume_request_requires_fields(proposal_schema, field):
    body = {
        "clarification_id": "clarify_001",
        "answer": "Use the current policy.",
        "idempotency_key": "resume_001",
    }
    del body[field]
    with pytest.raises(jsonschema.ValidationError):
        validator(proposal_schema, "ResumeRequest").validate(body)


@pytest.mark.parametrize(
    "field",
    [
        "principal_id",
        "owner_id",
        "scope_type",
        "scope_document_id",
        "thread_id",
        "checkpoint_id",
        "run_id",
        "conversation_id",
        "budget",
        "clarification_count",
    ],
)
def test_FR_AGENT_007_resume_request_rejects_trusted_context(proposal_schema, field):
    body = {
        "clarification_id": "clarify_001",
        "answer": "Use the current policy.",
        "idempotency_key": "resume_001",
        field: "forged",
    }
    with pytest.raises(jsonschema.ValidationError):
        validator(proposal_schema, "ResumeRequest").validate(body)


def test_FR_AGENT_007_resume_receipt_shape(proposal_schema):
    validator(proposal_schema, "ResumeAccepted").validate(
        {
            "run_id": "run_001",
            "message_id": "msg_001",
            "clarification_id": "clarify_001",
            "state": "resuming",
            "request_id": "req_001",
        }
    )


def test_FR_AGENT_007_clarification_view_shape(proposal_schema):
    validator(proposal_schema, "Clarification").validate(
        {"clarification_id": "clarify_001", "prompt": "Which policy version?"}
    )


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "AUTH_INVALID_CREDENTIALS", False),
        (403, "AUTH_FORBIDDEN", False),
        (404, "RESOURCE_NOT_FOUND", False),
        (409, "IDEMPOTENCY_CONFLICT", False),
        (409, "RESUME_NOT_ALLOWED", False),
        (409, "CLARIFICATION_MISMATCH", False),
        (409, "RUN_CANCELLED", False),
        (409, "RUN_TIMEOUT", False),
        (422, "INVALID_RESUME_REQUEST", False),
        (503, "PROVIDER_TEMPORARY_ERROR", True),
    ],
)
def test_FR_AGENT_007_resume_error_mapping_shape(proposal_schema, status, code, retryable):
    validator(proposal_schema, "ResumeFailure").validate(
        {
            "http_status": status,
            "body": {
                "code": code,
                "message": "Request cannot be accepted.",
                "request_id": "req_001",
                "details": {},
                "retryable": retryable,
            },
        }
    )


@pytest.mark.parametrize("state", ["waiting_for_user", "retrieving", "answered", None])
def test_FR_AGENT_007_resume_receipt_is_not_current_state(proposal_schema, state):
    body = {
        "run_id": "run_001",
        "message_id": "msg_001",
        "clarification_id": "clarify_001",
        "state": state,
        "request_id": "req_001",
    }
    with pytest.raises(jsonschema.ValidationError):
        validator(proposal_schema, "ResumeAccepted").validate(body)


@pytest.mark.parametrize("field", ["thread_id", "observation", "tool_calls", "reasoning"])
def test_FR_AGENT_007_clarification_view_rejects_private_fields(proposal_schema, field):
    with pytest.raises(jsonschema.ValidationError):
        validator(proposal_schema, "Clarification").validate(
            {"clarification_id": "clarify_001", "prompt": "Which version?", field: "private"}
        )


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (200, "RESUME_NOT_ALLOWED", False),
        (403, "IDEMPOTENCY_CONFLICT", False),
        (409, "RESUME_NOT_ALLOWED", True),
        (503, "PROVIDER_TEMPORARY_ERROR", False),
        (409, "UNKNOWN_CODE", False),
    ],
)
def test_FR_AGENT_007_resume_error_rejects_wrong_mapping(proposal_schema, status, code, retryable):
    with pytest.raises(jsonschema.ValidationError):
        validator(proposal_schema, "ResumeFailure").validate(
            {
                "http_status": status,
                "body": {
                    "code": code,
                    "message": "Cannot resume.",
                    "request_id": "req_001",
                    "details": {},
                    "retryable": retryable,
                },
            }
        )


def test_FR_AGENT_007_resume_error_details_cannot_leak_context(proposal_schema):
    with pytest.raises(jsonschema.ValidationError):
        validator(proposal_schema, "ResumeFailure").validate(
            {
                "http_status": 404,
                "body": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Resource unavailable.",
                    "request_id": "req_001",
                    "retryable": False,
                    "details": {"owner_id": "other_user"},
                },
            }
        )


def test_FR_AGENT_007_resume_proposal_is_unpublished(proposal_schema, openapi_doc):
    assert proposal_schema["x-status"] == "proposed"
    assert openapi_doc["info"]["version"] == "0.1.0"
    assert "/runs/{id}/resume" not in openapi_doc["paths"]
    codes = openapi_doc["components"]["schemas"]["Error"]["properties"]["code"]["enum"]
    assert {"RESUME_NOT_ALLOWED", "CLARIFICATION_MISMATCH", "INVALID_RESUME_REQUEST"}.isdisjoint(
        codes
    )
