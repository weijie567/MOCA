from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.business.schemas import (
    BusinessFactResultV1,
    BusinessMetricFiltersV1,
    BusinessMetricFreshnessV1,
    BusinessMetricQueryInput,
    BusinessMetricResultV1,
    BusinessMetricScopeV1,
    BusinessMetricTimeRangeV1,
)
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


def _metric_result_payload(**overrides):
    computed_at = datetime.now(UTC)
    payload = {
        "metric_id": "merchant_refund_rate",
        "status": "ok",
        "value": None,
        "rate": 0.25,
        "numerator": 1,
        "denominator": 4,
        "unit": "ratio",
        "display_value": "25.00%",
        "scope": {
            "tenant_id": "tenant-001",
            "merchant_ids": ["merchant-001"],
            "scope_label": "当前权限范围",
        },
        "time_range": {
            "start_at": "2026-07-01T00:00:00Z",
            "end_at": "2026-07-08T00:00:00Z",
            "preset": "this_week",
            "timezone": "Asia/Shanghai",
        },
        "filters": {"merchant_id": "merchant-001", "status_filter": []},
        "freshness": {
            "data_freshness_at": None,
            "computed_at": computed_at.isoformat(),
            "source_system": "demo_business_db",
        },
        "formula": "distinct refunded orders / total orders",
        "caveats": [],
        "no_leak_status": "not_applicable",
    }
    payload.update(overrides)
    return payload


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


def test_business_fact_ref_accepts_business_metric_resource_type():
    ref = _business_fact_ref(resource_type="business_metric", resource_id="merchant_refund_rate")

    assert ref.resource_type == "business_metric"


def test_metric_query_input_is_strict_and_rejects_authority_fields():
    query = BusinessMetricQueryInput.model_validate(
        {
            "metric_id": "order_count",
            "time_preset": "today",
            "merchant_id": "merchant-001",
            "status_filter": ["paid"],
        }
    )

    assert query.metric_id == "order_count"
    assert query.time_preset == "today"
    assert query.status_filter == ["paid"]

    for payload in (
        {"metric_id": "order_count", "tenant_id": "tenant-attacker"},
        {"metric_id": "order_count", "merchant_scope": ["*"]},
        {"metric_id": "order_count", "merchant_id": "*"},
    ):
        with pytest.raises(ValidationError):
            BusinessMetricQueryInput.model_validate(payload)


def test_business_metric_result_is_strict_and_serializes_nested_contracts():
    result = BusinessMetricResultV1.model_validate(_metric_result_payload())

    assert isinstance(result.scope, BusinessMetricScopeV1)
    assert isinstance(result.time_range, BusinessMetricTimeRangeV1)
    assert isinstance(result.filters, BusinessMetricFiltersV1)
    assert isinstance(result.freshness, BusinessMetricFreshnessV1)
    assert result.model_dump(mode="json")["freshness"]["computed_at"].endswith("+00:00")

    with pytest.raises(ValidationError):
        BusinessMetricResultV1.model_validate(_metric_result_payload(raw_sql="select * from orders"))


def test_refund_rate_zero_denominator_metric_result_is_non_computable_not_zero_percent():
    result = BusinessMetricResultV1.model_validate(
        _metric_result_payload(
            status="non_computable",
            value=None,
            rate=None,
            numerator=0,
            denominator=0,
            display_value="暂无可计算退款率",
            caveats=["当前范围内没有订单，无法计算退款率。"],
        )
    )

    assert result.denominator == 0
    assert result.rate is None
    assert result.value is None
    assert result.display_value == "暂无可计算退款率"


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
def test_public_business_imports_do_not_trigger_tool_platform_cycle(module_name: str) -> None:
    subprocess.run([sys.executable, "-c", f"import {module_name}"], check=True)


def test_business_query_contracts_are_reexported_for_compatibility() -> None:
    from src.business.query.schemas import BusinessQuerySpec as CanonicalBusinessQuerySpec
    from src.business.query.schemas import metric_input_to_business_query as canonical_metric_mapping
    from src.business.schemas import BusinessQuerySpec, metric_input_to_business_query

    assert BusinessQuerySpec is CanonicalBusinessQuerySpec
    assert metric_input_to_business_query is canonical_metric_mapping
