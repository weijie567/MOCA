from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any

import pytest

from src.business.query.registry import BUSINESS_QUERY_REGISTRY, BusinessQueryRegistry


EXPECTED_OPERATIONS = frozenset({"aggregate", "list", "detail", "breakdown", "compare"})
EXPECTED_RESOURCES = frozenset({"order", "refund_case", "ticket", "coupon_record", "merchant_metric"})
EXPECTED_METRIC_RESOURCES = {
    "order_count": "order",
    "refund_case_count": "refund_case",
    "pending_ticket_count": "ticket",
    "coupon_record_count": "coupon_record",
    "merchant_refund_rate": "merchant_metric",
}
EXPECTED_TIME_PRESETS = frozenset(
    {"today", "this_week", "this_month", "this_quarter", "this_year", "current_snapshot"}
)


def test_business_query_registry_exports_singleton_and_read_taxonomy() -> None:
    registry = BUSINESS_QUERY_REGISTRY

    assert isinstance(registry, BusinessQueryRegistry)
    assert registry.operation_ids() == EXPECTED_OPERATIONS
    assert registry.resource_ids() == EXPECTED_RESOURCES
    assert "draft" not in registry.operation_ids()
    assert "execute" not in registry.operation_ids()


def test_business_query_registry_metric_resource_and_time_compatibility() -> None:
    registry = BUSINESS_QUERY_REGISTRY

    assert registry.metric_ids() == frozenset(EXPECTED_METRIC_RESOURCES)
    for metric_id, resource_id in EXPECTED_METRIC_RESOURCES.items():
        metric = registry.metric_descriptor(metric_id)
        assert metric.resource_id == resource_id

    assert registry.compatibility_resource_type("coupon_record_count") == "action_draft"
    assert registry.compatibility_resource_type("order_count") == "order"

    assert registry.time_preset_ids() == EXPECTED_TIME_PRESETS
    assert registry.metric_accepts_time_preset("pending_ticket_count", "current_snapshot") is True
    assert registry.default_time_preset_for_metric("pending_ticket_count") == "current_snapshot"
    for metric_id in EXPECTED_METRIC_RESOURCES:
        if metric_id != "pending_ticket_count":
            assert registry.metric_accepts_time_preset(metric_id, "current_snapshot") is False


def test_business_query_registry_exposes_safe_field_allowlists() -> None:
    registry = BUSINESS_QUERY_REGISTRY

    assert "order_no" in registry.field_ids_for_resource("order", purpose="list")
    assert "order_no" in registry.field_ids_for_resource("order", purpose="prompt")
    assert "status" in registry.field_ids_for_resource("refund_case", purpose="list")
    assert "ticket_no" in registry.field_ids_for_resource("ticket", purpose="detail")
    assert "coupon_record_no" in registry.field_ids_for_resource("coupon_record", purpose="list")
    assert "metric_id" in registry.field_ids_for_resource("merchant_metric", purpose="prompt")

    for resource_id in EXPECTED_RESOURCES:
        assert registry.field_ids_for_resource(resource_id, purpose="list")
        assert registry.field_ids_for_resource(resource_id, purpose="prompt")


def test_business_query_registry_descriptors_are_immutable() -> None:
    registry = BUSINESS_QUERY_REGISTRY

    with pytest.raises(TypeError):
        registry.metrics()["order_count"] = registry.metric_descriptor("order_count")  # type: ignore[index]

    metric = registry.metric_descriptor("order_count")
    with pytest.raises(AttributeError):
        metric.resource_id = "ticket"  # type: ignore[misc]

    assert isinstance(metric.status_allowlist, frozenset)
    assert isinstance(metric.accepted_time_presets, frozenset)
    assert isinstance(registry.field_ids_for_resource("order", purpose="list"), frozenset)


def test_business_query_registry_is_data_only_allowlist_facts() -> None:
    registry = BUSINESS_QUERY_REGISTRY
    forbidden_field_names = {
        "sql",
        "statement",
        "orm_expression",
        "tenant_id",
        "merchant_scope",
        "raw_cursor",
        "projection_template",
        "frontend_label",
        "layout",
    }
    forbidden_text = (
        "select ",
        " from ",
        " where ",
        "tenant_id",
        "merchant_scope",
        "raw_cursor",
        "layout",
    )

    for descriptor in registry.all_descriptors():
        assert is_dataclass(descriptor)
        for field in fields(descriptor):
            assert field.name not in forbidden_field_names
            value = getattr(descriptor, field.name)
            _assert_data_only_value(value, forbidden_text)


def _assert_data_only_value(value: Any, forbidden_text: tuple[str, ...]) -> None:
    assert not callable(value)
    if isinstance(value, str):
        lowered = value.lower()
        assert not any(token in lowered for token in forbidden_text)
    elif isinstance(value, (tuple, frozenset)):
        for item in value:
            _assert_data_only_value(item, forbidden_text)
    elif isinstance(value, dict):
        for key, item in value.items():
            _assert_data_only_value(key, forbidden_text)
            _assert_data_only_value(item, forbidden_text)
    else:
        assert value is None or isinstance(value, (bool, int))
