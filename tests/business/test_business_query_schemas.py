from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.business.query.registry import BUSINESS_QUERY_REGISTRY
from src.business.query.schemas import (
    BusinessQuerySpec,
    BusinessQueryAnswerContext,
    BusinessQueryCursor,
    BusinessQueryFilterSet,
    BusinessQueryResultCursor,
    BusinessQueryResultV1,
    BusinessQueryScopeSummary,
    BusinessQuerySort,
    metric_input_to_business_query,
)
from src.business.schemas import BusinessMetricQueryInput


def _aggregate_payload(metric_id: str = "order_count", **overrides: object) -> dict[str, object]:
    metric = BUSINESS_QUERY_REGISTRY.metric_descriptor(metric_id)
    payload: dict[str, object] = {
        "operation": "aggregate",
        "resource": metric.resource_id,
        "metric_id": metric_id,
        "time_preset": "this_week",
    }
    payload.update(overrides)
    return payload


def _metric_id_for_resource(resource_id: str) -> str:
    for metric in BUSINESS_QUERY_REGISTRY.metrics().values():
        if metric.resource_id == resource_id:
            return metric.id
    raise AssertionError(f"no metric descriptor for resource {resource_id}")


def test_business_query_spec_is_strict_and_rejects_authority_or_raw_query_shapes() -> None:
    spec = BusinessQuerySpec.model_validate(
        _aggregate_payload(
            merchant_id="merchant-001",
            filters={"status_filter": ["paid"]},
        )
    )

    assert spec.operation == "aggregate"
    assert spec.resource == "order"
    assert isinstance(spec.filters, BusinessQueryFilterSet)
    assert spec.filters.status_filter == ["paid"]

    invalid_payloads = (
        _aggregate_payload(tenant_id="tenant-attacker"),
        _aggregate_payload(merchant_scope=["*"]),
        _aggregate_payload(merchant_id="*"),
        _aggregate_payload(raw_sql="select * from orders"),
        _aggregate_payload(where={"status": "paid"}),
        _aggregate_payload(filters={"status_filter": ["paid"], "sql": "select * from orders"}),
        _aggregate_payload(filters={"status_filter": ["paid"], "merchant_scope": ["merchant-001"]}),
        {"operation": "list", "resource": "order", "cursor": "opaque-cursor-string"},
        _aggregate_payload(debug_trace={"raw": True}),
    )
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            BusinessQuerySpec.model_validate(payload)


def test_business_query_spec_rejects_unknown_values_and_invalid_ranges() -> None:
    invalid_payloads = (
        _aggregate_payload(operation="draft"),
        _aggregate_payload(operation="execute"),
        _aggregate_payload(operation="aggregate", resource="logistics"),
        {"operation": "list", "resource": "order", "fields": ["customer_phone"]},
        {"operation": "list", "resource": "order", "filters": {"status_filter": ["refunded"]}},
        {"operation": "list", "resource": "order", "limit": 0},
        {"operation": "list", "resource": "order", "limit": 101},
        _aggregate_payload(
            start_at=datetime(2026, 7, 8, tzinfo=UTC),
            end_at=datetime(2026, 7, 1, tzinfo=UTC),
            time_preset=None,
        ),
        _aggregate_payload(start_at=datetime(2026, 7, 1, tzinfo=UTC)),
    )

    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            BusinessQuerySpec.model_validate(payload)


def test_current_snapshot_validation_is_descriptor_owned() -> None:
    snapshot = BusinessQuerySpec.model_validate(
        _aggregate_payload(
            "pending_ticket_count",
            time_preset="current_snapshot",
        )
    )

    assert snapshot.metric_id == "pending_ticket_count"
    assert snapshot.time_preset == "current_snapshot"

    for event_metric_id in ("order_count", "refund_case_count", "coupon_record_count", "merchant_refund_rate"):
        with pytest.raises(ValidationError):
            BusinessQuerySpec.model_validate(_aggregate_payload(event_metric_id, time_preset="current_snapshot"))


def test_business_query_spec_validates_breakdown_compare_sort_and_cursor_shapes() -> None:
    breakdown = BusinessQuerySpec.model_validate(
        {
            "operation": "breakdown",
            "resource": "order",
            "metric_id": "order_count",
            "time_preset": "this_week",
            "group_by": "status",
        }
    )
    compare = BusinessQuerySpec.model_validate(
        {
            "operation": "compare",
            "resource": "order",
            "metric_id": "order_count",
            "time_preset": "this_week",
            "compare_to": "previous_period",
        }
    )
    listed = BusinessQuerySpec.model_validate(
        {
            "operation": "list",
            "resource": "order",
            "sort": {"field": "created_at", "direction": "desc"},
            "cursor": {"cursor_id": "cur_001", "direction": "next"},
        }
    )

    assert breakdown.group_by == "status"
    assert compare.compare_to == "previous_period"
    assert isinstance(listed.sort, BusinessQuerySort)
    assert isinstance(listed.cursor, BusinessQueryCursor)

    invalid_payloads = (
        {"operation": "breakdown", "resource": "order", "metric_id": "order_count", "time_preset": "this_week"},
        {
            "operation": "breakdown",
            "resource": "order",
            "metric_id": "order_count",
            "time_preset": "this_week",
            "group_by": "merchant_id",
        },
        {
            "operation": "compare",
            "resource": "order",
            "metric_id": "order_count",
            "time_preset": "this_week",
            "compare_to": "last_year",
        },
        {"operation": "list", "resource": "order", "sort": {"field": "amount", "direction": "desc"}},
        {"operation": "list", "resource": "order", "sort": {"field": "created_at", "direction": "asc"}},
    )
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            BusinessQuerySpec.model_validate(payload)


def test_metric_input_maps_to_business_query_spec_for_all_phase61_metrics() -> None:
    metric_payloads = {
        "order_count": {"time_preset": "this_week", "status_filter": ["paid"]},
        "refund_case_count": {"time_preset": "today", "status_filter": ["submitted"]},
        "pending_ticket_count": {},
        "coupon_record_count": {"time_preset": "this_month"},
        "merchant_refund_rate": {"time_preset": "this_week", "merchant_id": "merchant-001"},
    }

    for metric_id, extra_payload in metric_payloads.items():
        metric_input = BusinessMetricQueryInput.model_validate({"metric_id": metric_id, **extra_payload})
        spec = metric_input_to_business_query(metric_input)
        metric = BUSINESS_QUERY_REGISTRY.metric_descriptor(metric_id)

        assert isinstance(spec, BusinessQuerySpec)
        assert spec.operation == "aggregate"
        assert spec.resource == metric.resource_id
        assert spec.metric_id == metric_id
        assert spec.merchant_id == metric_input.merchant_id
        if metric.default_time_preset and "time_preset" not in extra_payload:
            assert spec.time_preset == metric.default_time_preset
        else:
            assert spec.time_preset == metric_input.time_preset
        expected_status = list(metric_input.status_filter or metric.default_status_filter)
        assert spec.filters.status_filter == expected_status


def test_schema_validation_acceptance_tracks_registry_descriptors() -> None:
    registry = BUSINESS_QUERY_REGISTRY

    for operation_id in registry.operation_ids():
        BusinessQuerySpec.model_validate(_sample_payload_for_operation(operation_id))

    for metric_id, metric in registry.metrics().items():
        preset = "current_snapshot" if "current_snapshot" in metric.accepted_time_presets else "this_week"
        BusinessQuerySpec.model_validate(_aggregate_payload(metric_id, time_preset=preset))

    for preset_id in registry.time_preset_ids():
        metric_id = "pending_ticket_count" if preset_id == "current_snapshot" else "order_count"
        BusinessQuerySpec.model_validate(_aggregate_payload(metric_id, time_preset=preset_id))

    for status in registry.statuses().values():
        for value in status.values:
            BusinessQuerySpec.model_validate(
                {"operation": "list", "resource": status.resource_id, "filters": {"status_filter": [value]}}
            )

    for resource_id in registry.resource_ids():
        resource = registry.resource_descriptor(resource_id)
        if resource_id in registry.operations()["list"].compatible_resource_ids:
            for field_id in registry.field_ids_for_resource(resource_id, purpose="list"):
                BusinessQuerySpec.model_validate({"operation": "list", "resource": resource_id, "fields": [field_id]})
        if resource_id in registry.operations()["detail"].compatible_resource_ids:
            for field_id in registry.field_ids_for_resource(resource_id, purpose="detail"):
                BusinessQuerySpec.model_validate(
                    {"operation": "detail", "resource": resource_id, "fields": [field_id], "resource_id": "res-001"}
                )
        for field_id in registry.field_ids_for_resource(resource_id, purpose="prompt"):
            metric_id = _metric_id_for_resource(resource_id)
            BusinessQuerySpec.model_validate(_aggregate_payload(metric_id, fields=[field_id]))

        assert resource.default_limit <= resource.max_limit

    for sort in registry.sorts().values():
        if sort.resource_id in registry.operations()["list"].compatible_resource_ids:
            payload = {
                "operation": "list",
                "resource": sort.resource_id,
                "sort": {"field": sort.field_id, "direction": sort.direction},
            }
        else:
            payload = _aggregate_payload(
                _metric_id_for_resource(sort.resource_id),
                sort={"field": sort.field_id, "direction": sort.direction},
            )
        BusinessQuerySpec.model_validate(payload)


def test_business_query_result_context_and_cursor_models_are_strict() -> None:
    spec = BusinessQuerySpec.model_validate(_aggregate_payload())
    result_cursor = BusinessQueryResultCursor.model_validate(
        {"cursor_id": "cur_001", "has_more": True, "limit": 20, "next_cursor": {"cursor_id": "cur_002"}}
    )
    context = BusinessQueryAnswerContext.model_validate(
        {
            "query_spec": spec.model_dump(mode="json"),
            "result_refs": ["business_fact:order_count"],
            "allowed_drilldowns": ["list"],
            "fields_shown": ["display_value"],
            "cursor": result_cursor.model_dump(mode="json"),
            "scope": {"scope_label": "当前权限范围", "merchant_id": "merchant-001"},
            "time_summary": "本周",
            "filter_summary": "已支付订单",
        }
    )
    result = BusinessQueryResultV1.model_validate(
        {
            "operation": "aggregate",
            "resource": "order",
            "status": "ok",
            "rows": [{"display_value": "3"}],
            "answer_context": context.model_dump(mode="json"),
            "cursor": result_cursor.model_dump(mode="json"),
            "scope": {"scope_label": "当前权限范围"},
        }
    )

    assert isinstance(context.scope, BusinessQueryScopeSummary)
    assert result.schema_version == "business_query_result.v1"
    assert result.cursor.has_more is True

    with pytest.raises(ValidationError):
        BusinessQueryAnswerContext.model_validate(
            {
                "query_spec": spec.model_dump(mode="json"),
                "result_refs": [],
                "allowed_drilldowns": [],
                "fields_shown": [],
                "raw_rows": [{"order_no": "ORD-001"}],
            }
        )


def _sample_payload_for_operation(operation_id: str) -> dict[str, object]:
    if operation_id == "aggregate":
        return _aggregate_payload("order_count")
    if operation_id == "list":
        return {"operation": "list", "resource": "order", "fields": ["order_no"], "limit": 20}
    if operation_id == "detail":
        return {"operation": "detail", "resource": "order", "resource_id": "ORD-001", "fields": ["order_no"]}
    if operation_id == "breakdown":
        return _aggregate_payload("order_count", operation="breakdown", group_by="status")
    if operation_id == "compare":
        return _aggregate_payload("order_count", operation="compare", compare_to="previous_period")
    raise AssertionError(f"unexpected operation descriptor: {operation_id}")
