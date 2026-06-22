from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.platform.trusted_context import MerchantScopeV1, TrustedContext


TRUSTED_CONTEXT_FIELDS = {
    "schema_version",
    "tenant_id",
    "user_id",
    "role",
    "permissions",
    "merchant_scope",
    "session_id",
    "thread_id",
    "run_id",
    "trace_id",
    "locale",
}

PROJECTION_LOCAL_FIELDS = {
    "request_id": "request-1",
    "tool_call_id": "tool-call-1",
    "caller_node": "investigate",
    "deadline_at": "2026-06-22T12:00:00Z",
    "attempt": 2,
    "max_attempts": 3,
    "idempotency_key": "run-1:tool:1",
    "approval_ref": "approval-1",
    "safety_snapshot_ref": "safety-1",
    "policy_snapshot_ref": "policy-snapshot-1",
    "effective_at": "2026-06-22T12:00:00Z",
    "channel": "agent_runs",
    "policy_version": "policy.v1",
    "model_version": "model.v1",
    "tool_version": "tool.v2",
    "artifact_ref": "artifact-1",
    "artifact_refs": ["artifact-1"],
}


def _trusted_context_payload() -> dict:
    return {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "role": "support",
        "permissions": ["tool:get_order", "knowledge:search"],
        "merchant_scope": MerchantScopeV1(merchant_ids=["merchant-1"]),
        "session_id": "session-1",
        "thread_id": "thread-1",
        "run_id": "run-1",
        "trace_id": "trace-1",
        "locale": "zh-CN",
    }


def test_trusted_context_exact_field_set() -> None:
    context = TrustedContext.model_validate(_trusted_context_payload())

    assert set(TrustedContext.model_fields) == TRUSTED_CONTEXT_FIELDS
    assert set(context.model_dump()) == TRUSTED_CONTEXT_FIELDS


def test_trusted_context_schema_version_is_v1() -> None:
    context = TrustedContext.model_validate(_trusted_context_payload())

    assert context.schema_version == "trusted_context.v1"
    assert context.model_dump()["schema_version"] == "trusted_context.v1"


@pytest.mark.parametrize(("field", "value"), sorted(PROJECTION_LOCAL_FIELDS.items()))
def test_trusted_context_rejects_projection_local_fields(field: str, value: object) -> None:
    payload = _trusted_context_payload() | {field: value}

    with pytest.raises(ValidationError):
        TrustedContext.model_validate(payload)
