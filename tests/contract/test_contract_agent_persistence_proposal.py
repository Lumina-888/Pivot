"""ND-AGENT-04-A shape checks only, not fencing/PG/recovery acceptance."""

import json
from datetime import datetime
from functools import lru_cache

import jsonschema
import pytest


@pytest.fixture(scope="module")
def persistence_schema(repo_root):
    path = repo_root / "spec/contracts/proposals/agent-persistence.schema.json"
    assert path.is_file(), "ND-AGENT-04-A proposed schema is missing (Red)"
    return json.loads(path.read_text(encoding="utf-8"))


FORMAT_CHECKER = jsonschema.FormatChecker()


@FORMAT_CHECKER.checks("date-time", raises=ValueError)
def valid_utc_timestamp(value):
    # jsonschema's optional RFC3339 checker is absent from the baseline environment.
    if not isinstance(value, str):
        return True
    if not value.endswith("Z"):
        return False
    offset = datetime.fromisoformat(value).utcoffset()
    return offset is not None and offset.total_seconds() == 0


@lru_cache(maxsize=6)
def component_validator(schema_json, component):
    document = {**json.loads(schema_json), "$ref": f"#/$defs/{component}"}
    jsonschema.Draft202012Validator.check_schema(document)
    return jsonschema.Draft202012Validator(document, format_checker=FORMAT_CHECKER)


def validate(schema, component, body):
    component_validator(json.dumps(schema), component).validate(body)


def test_FR_AGENT_006_lease_token_shape(persistence_schema):
    validate(
        persistence_schema,
        "LeaseToken",
        {
            "run_id": "run_001",
            "executor_id": "executor_001",
            "fencing_token": 2,
            "state_version": 7,
            "expires_at": "2026-10-03T12:00:00Z",
        },
    )


SAMPLES = {
    "LeaseToken": {
        "run_id": "run_001",
        "executor_id": "executor_001",
        "fencing_token": 2,
        "state_version": 7,
        "expires_at": "2026-10-03T12:00:00Z",
    },
    "CheckpointBinding": {
        "run_id": "run_001",
        "thread_id": "thread_001",
        "checkpoint_id": "checkpoint_001",
        "fencing_token": 2,
        "state_version": 7,
        "execution_epoch": 1,
        "budget_ledger_version": 4,
        "versions": {
            "graph": "graph-fixture-1",
            "state": "state-fixture-1",
            "prompt": "prompt-fixture-1",
            "tools": "tools-fixture-1",
            "model": "model-fixture-1",
            "dependency_lock": "lock-fixture-1",
            "budget_policy": "budget-unit-fake-only",
        },
    },
    "ResultCommitReceipt": {
        "run_id": "run_001",
        "result_id": "result_001",
        "message_id": "msg_001",
        "terminal_state": "answered",
        "state_version": 8,
        "committed_at": "2026-10-03T12:00:00Z",
    },
    "OutboxRecord": {
        "event_id": "event_001",
        "run_id": "run_001",
        "publication_key": "result-completed-001",
        "seq": 9,
        "event": "completed",
        "projection_version": "projection-fixture-1",
        "committed_at": "2026-10-03T12:00:00Z",
    },
    "ProviderAttempt": {
        "run_id": "run_001",
        "action_id": "action_001",
        "attempt_id": "attempt_001",
        "reservation_id": "reservation_001",
        "fencing_token": 2,
        "request_id": "req_001",
        "role": "planner",
        "model_version": "model-fixture-1",
        "pricing_version": "pricing-fixture-1",
        "dispatch_state": "dispatching",
        "usage_status": "unreconciled",
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost_microunits": None,
        "currency": "USD",
    },
    "GovernancePolicy": {
        "policy_id": "governance-unit-fake-only",
        "approval_ref": "unit_fake_only",
        "lease_duration_ms": 1000,
        "renew_interval_ms": 100,
        "checkpoint_retention_seconds": 3600,
        "resume_input_retention_seconds": 3600,
        "tombstone_retention_seconds": 7200,
        "backup_retention_seconds": 7200,
        "encryption_key_ref": "fixture-key-reference",
        "access_policy_ref": "fixture-access-policy",
        "deletion_policy_ref": "fixture-deletion-policy",
        "backup_policy_ref": "fixture-backup-policy",
    },
}


@pytest.mark.parametrize("component", list(SAMPLES)[1:])
def test_FR_AGENT_006_persistence_metadata_shape(persistence_schema, component):
    validate(persistence_schema, component, SAMPLES[component])


@pytest.mark.parametrize(
    ("component", "field"),
    [(component, field) for component, body in SAMPLES.items() for field in body],
)
def test_FR_AGENT_006_persistence_requires_metadata(persistence_schema, component, field):
    body = {key: value for key, value in SAMPLES[component].items() if key != field}
    with pytest.raises(jsonschema.ValidationError):
        validate(persistence_schema, component, body)


@pytest.mark.parametrize("component", SAMPLES)
@pytest.mark.parametrize("field", ["api_key", "reasoning", "principal", "raw_prompt", "url"])
def test_FR_AGENT_006_metadata_rejects_private_fields(persistence_schema, component, field):
    body = {**SAMPLES[component], field: "private-canary"}
    with pytest.raises(jsonschema.ValidationError):
        validate(persistence_schema, component, body)


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "2", None])
def test_FR_AGENT_006_fencing_token_requires_positive_integer(persistence_schema, value):
    body = {**SAMPLES["LeaseToken"], "fencing_token": value}
    with pytest.raises(jsonschema.ValidationError):
        validate(persistence_schema, "LeaseToken", body)


@pytest.mark.parametrize("value", ["", " \t\n", "x" * 129, 1, None])
def test_FR_AGENT_006_thread_requires_opaque_id_shape(persistence_schema, value):
    body = {**SAMPLES["CheckpointBinding"], "thread_id": value}
    with pytest.raises(jsonschema.ValidationError):
        validate(persistence_schema, "CheckpointBinding", body)


@pytest.mark.parametrize(
    "field", ["graph", "state", "prompt", "tools", "model", "dependency_lock", "budget_policy"]
)
def test_FR_AGENT_006_checkpoint_requires_fixed_versions(persistence_schema, field):
    versions = dict(SAMPLES["CheckpointBinding"]["versions"])
    del versions[field]
    body = {**SAMPLES["CheckpointBinding"], "versions": versions}
    with pytest.raises(jsonschema.ValidationError):
        validate(persistence_schema, "CheckpointBinding", body)


@pytest.mark.parametrize("value", [None, "", " \t", 1, {}])
def test_FR_AGENT_006_checkpoint_rejects_invalid_version(persistence_schema, value):
    versions = {**SAMPLES["CheckpointBinding"]["versions"], "graph": value}
    with pytest.raises(jsonschema.ValidationError):
        validate(
            persistence_schema,
            "CheckpointBinding",
            {**SAMPLES["CheckpointBinding"], "versions": versions},
        )


def test_FR_AGENT_006_versions_reject_private_reasoning(persistence_schema):
    versions = {**SAMPLES["CheckpointBinding"]["versions"], "reasoning": "private-canary"}
    with pytest.raises(jsonschema.ValidationError):
        validate(
            persistence_schema,
            "CheckpointBinding",
            {**SAMPLES["CheckpointBinding"], "versions": versions},
        )


@pytest.mark.parametrize(
    "value",
    [
        "2026-10-03",
        "2026-10-03T12:00:00",
        "2026-10-03T12:00:00+08:00",
        "2026-02-30T12:00:00Z",
        "2026-13-03T12:00:00Z",
    ],
)
def test_FR_AGENT_006_lease_timestamp_requires_valid_utc(persistence_schema, value):
    with pytest.raises(jsonschema.ValidationError):
        validate(persistence_schema, "LeaseToken", {**SAMPLES["LeaseToken"], "expires_at": value})


@pytest.mark.parametrize("state", ["received", "verifying", "waiting_for_user", "resuming"])
def test_FR_QA_002_commit_receipt_requires_terminal_state(persistence_schema, state):
    with pytest.raises(jsonschema.ValidationError):
        validate(
            persistence_schema,
            "ResultCommitReceipt",
            {**SAMPLES["ResultCommitReceipt"], "terminal_state": state},
        )


@pytest.mark.parametrize("state", ["answered", "uncertain", "refused", "failed", "cancelled"])
def test_FR_QA_002_commit_receipt_accepts_known_terminal_shape(persistence_schema, state):
    validate(
        persistence_schema,
        "ResultCommitReceipt",
        {**SAMPLES["ResultCommitReceipt"], "terminal_state": state},
    )


@pytest.mark.parametrize(
    "event",
    [
        "run_started",
        "stage",
        "token",
        "citation",
        "warning",
        "completed",
        "uncertain",
        "refused",
        "failed",
        "cancelled",
    ],
)
def test_FR_STREAM_002_outbox_accepts_existing_event_names(persistence_schema, event):
    validate(persistence_schema, "OutboxRecord", {**SAMPLES["OutboxRecord"], "event": event})


@pytest.mark.parametrize("event", ["agent", "tools", "raw_checkpoint", "thinking"])
def test_FR_STREAM_002_outbox_rejects_internal_event_names(persistence_schema, event):
    with pytest.raises(jsonschema.ValidationError):
        validate(persistence_schema, "OutboxRecord", {**SAMPLES["OutboxRecord"], "event": event})


@pytest.mark.parametrize("value", [0, -1, True, "1"])
def test_FR_STREAM_002_outbox_seq_requires_positive_integer(persistence_schema, value):
    with pytest.raises(jsonschema.ValidationError):
        validate(persistence_schema, "OutboxRecord", {**SAMPLES["OutboxRecord"], "seq": value})


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens", "estimated_cost_microunits"])
def test_FR_AGENT_004_unreconciled_usage_cannot_be_zero(persistence_schema, field):
    body = {**SAMPLES["ProviderAttempt"], field: 0}
    with pytest.raises(jsonschema.ValidationError):
        validate(persistence_schema, "ProviderAttempt", body)


def test_FR_AGENT_004_reported_usage_shape(persistence_schema):
    body = {
        **SAMPLES["ProviderAttempt"],
        "dispatch_state": "returned",
        "usage_status": "reported",
        "input_tokens": 100,
        "output_tokens": 50,
        "estimated_cost_microunits": 200,
    }
    validate(persistence_schema, "ProviderAttempt", body)


@pytest.mark.parametrize("value", [None, -1, True, 0.5, "100"])
def test_FR_AGENT_004_reported_usage_requires_integer_units(persistence_schema, value):
    body = {
        **SAMPLES["ProviderAttempt"],
        "usage_status": "reported",
        "input_tokens": 100,
        "output_tokens": 50,
        "estimated_cost_microunits": value,
    }
    with pytest.raises(jsonschema.ValidationError):
        validate(persistence_schema, "ProviderAttempt", body)


@pytest.mark.parametrize(
    "field",
    [
        "lease_duration_ms",
        "renew_interval_ms",
        "checkpoint_retention_seconds",
        "resume_input_retention_seconds",
        "tombstone_retention_seconds",
        "backup_retention_seconds",
    ],
)
@pytest.mark.parametrize("value", [0, -1, True])
def test_FR_AGENT_006_governance_rejects_invalid_limits(persistence_schema, field, value):
    with pytest.raises(jsonschema.ValidationError):
        validate(
            persistence_schema, "GovernancePolicy", {**SAMPLES["GovernancePolicy"], field: value}
        )


def test_FR_AGENT_006_persistence_proposal_is_unpublished(persistence_schema, openapi_doc):
    assert persistence_schema["x-status"] == "proposed"
    assert openapi_doc["info"]["version"] == "0.1.0"
    assert "LeaseToken" not in openapi_doc["components"]["schemas"]
    assert "CheckpointBinding" not in openapi_doc["components"]["schemas"]
