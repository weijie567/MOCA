from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.business_tools.schemas import (
    BusinessFactRefV1,
    ToolCallContext,
    ToolResultV2,
)
from src.knowledge.schemas import EvidenceRefV1


TOOL_RESULT_STATUSES = [
    "success",
    "partial_success",
    "not_found",
    "permission_denied",
    "timeout",
    "unavailable",
    "conflict",
    "invalid_request",
    "invalid_response",
    "error",
]


def _complete_result_payload(**overrides):
    payload = {
        "data": None,
        "summary": "",
        "source_system": "business_tool_facade",
        "data_freshness_at": None,
        "error": None,
        "retryable": False,
        "retry_after_ms": None,
        "latency_ms": 0,
        "audit_ref": None,
    }
    payload.update(overrides)
    return payload


def _complete_context_payload(**overrides):
    payload = {
        "tenant_id": "tenant-001",
        "user_id": "user-001",
        "role": "support_agent",
        "permissions": ["tool:get_order"],
        "merchant_scope": {"merchant_ids": ["merchant-001"]},
        "thread_id": "thread-001",
        "run_id": "run-001",
        "trace_id": "trace-001",
        "request_id": "request-001",
        "tool_call_id": "tool-call-001",
        "caller_node": "investigate",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("status", TOOL_RESULT_STATUSES)
def test_tool_result_accepts_all_contract_statuses(status: str):
    result = ToolResultV2.model_validate(_complete_result_payload(status=status))

    assert result.status == status
    assert result.latency_ms == 0


def test_tool_result_rejects_unknown_status():
    with pytest.raises(ValidationError):
        ToolResultV2.model_validate(_complete_result_payload(status="pending"))


def test_business_fact_ref_is_not_coercible_to_policy_evidence_ref():
    business_ref = BusinessFactRefV1(
        tenant_id="tenant-001",
        source_system="orders",
        resource_type="order",
        resource_id="order-001",
        resource_version=None,
        data_freshness_at=None,
        retrieved_at=datetime.now(UTC),
    )

    with pytest.raises(ValidationError):
        EvidenceRefV1.model_validate(business_ref.model_dump())


def test_tool_result_and_context_defaults_are_contract_defaults():
    result = ToolResultV2.model_validate(_complete_result_payload(status="success"))
    context = ToolCallContext.model_validate(_complete_context_payload())

    assert result.policy_evidence_refs == []
    assert result.business_fact_refs == []
    assert result.audit_ref is None
    assert result.latency_ms == 0
    assert context.attempt == context.max_attempts == 1


def test_tool_result_requires_latency_ms():
    payload = _complete_result_payload(status="success")
    payload.pop("latency_ms")

    with pytest.raises(ValidationError):
        ToolResultV2.model_validate(payload)


def test_tool_call_context_rejects_untrusted_extra_fields():
    with pytest.raises(ValidationError):
        ToolCallContext.model_validate(
            _complete_context_payload(arguments={"tenant_id": "attacker-controlled"})
        )
