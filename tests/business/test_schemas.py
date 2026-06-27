from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.business.schemas import BusinessFactResultV1
from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import (
    BusinessFactRefV1,
    ToolCallContext,
    ToolError,
    ToolResultV2,
)


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

BUSINESS_FACT_RESULT_STATUSES = [
    "ok",
    "partial",
    "not_found",
    "permission_denied",
    "stale",
    "unavailable",
    "invalid_request",
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


def _business_fact_ref(resource_type: str = "order", resource_id: str = "ORD-001") -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id="tenant-001",
        source_system="orders",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_version=None,
        data_freshness_at=None,
        retrieved_at=datetime.now(UTC),
    )


def _complete_business_fact_payload(**overrides):
    payload = {
        "tenant_id": "tenant-001",
        "status": "ok",
        "fact": {"order_no": "ORD-001", "status": "paid"},
        "business_fact_refs": [_business_fact_ref()],
        "source_system": "demo_orders_db",
        "scope_check_result": "allowed",
        "missing_required_facts": [],
        "safe_errors": [],
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


@pytest.mark.parametrize("status", BUSINESS_FACT_RESULT_STATUSES)
def test_business_fact_result_accepts_all_contract_statuses(status: str):
    payload = _complete_business_fact_payload(
        status=status,
        fact=None if status != "ok" else {"order_no": "ORD-001"},
        business_fact_refs=[] if status != "ok" else [_business_fact_ref()],
        scope_check_result="denied" if status == "permission_denied" else "allowed",
        safe_errors=[
            ToolError(
                code="BUSINESS_FACT_PERMISSION_DENIED",
                safe_message="Business resource unavailable for this request",
                retryable=False,
                source="caller",
            )
        ]
        if status == "permission_denied"
        else [],
    )

    result = BusinessFactResultV1.model_validate(payload)

    assert result.status == status


def test_business_fact_result_is_strict_and_requires_normative_fields():
    with pytest.raises(ValidationError):
        BusinessFactResultV1.model_validate(_complete_business_fact_payload(extra="not allowed"))

    missing_source = _complete_business_fact_payload()
    missing_source.pop("source_system")
    with pytest.raises(ValidationError):
        BusinessFactResultV1.model_validate(missing_source)


def test_business_fact_result_explicit_null_metadata_is_dumped():
    result = BusinessFactResultV1.model_validate(_complete_business_fact_payload())

    dumped = result.model_dump()
    assert dumped["resource_version"] is None
    assert dumped["data_freshness_at"] is None


def test_business_fact_ref_is_not_coercible_to_policy_evidence_ref():
    business_ref = _business_fact_ref(resource_id="order-001")

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
        ToolCallContext.model_validate(_complete_context_payload(arguments={"tenant_id": "attacker-controlled"}))


@pytest.mark.parametrize("module_name", ["src.business", "src.business.schemas", "src.business.service"])
def test_public_business_imports_do_not_trigger_tool_manager_cycle(module_name: str) -> None:
    subprocess.run([sys.executable, "-c", f"import {module_name}"], check=True)
