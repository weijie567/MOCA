from __future__ import annotations

import json

import pytest

from src.business.query.projection import (
    business_query_response_text,
    safe_business_query_api_payload,
    safe_business_query_metadata,
)


def _business_query_result(
    *,
    operation: str = "list",
    rows: list[dict] | None = None,
    status: str = "ok",
    resource: str = "order",
) -> dict:
    query_spec = {
        "operation": operation,
        "resource": resource,
        "time_preset": "this_week",
        "fields": ["order_no", "status"],
        "limit": 20,
    }
    if operation == "aggregate":
        query_spec["metric_id"] = "order_count"
    if operation == "breakdown":
        query_spec.update({"metric_id": "order_count", "group_by": "status"})
    if operation == "compare":
        query_spec.update({"metric_id": "order_count", "compare_to": "previous_period"})
    if operation == "detail":
        query_spec.update({"resource_id": "ORD-BQ-001", "fields": ["order_no", "status", "amount"]})
    return {
        "schema_version": "business_query_result.v1",
        "operation": operation,
        "resource": resource,
        "status": status,
        "rows": rows if rows is not None else [{"order_no": "ORD-BQ-001", "status": "paid"}],
        "answer_context": {
            "schema_version": "business_query_answer_context.v1",
            "query_spec": query_spec,
            "result_refs": ["ORD-BQ-001"],
            "allowed_drilldowns": ["detail"] if operation == "list" else ["list"] if operation == "aggregate" else [],
            "fields_shown": query_spec.get("fields", []),
            "scope": {"scope_label": "当前权限范围"},
            "time_summary": "本周",
            "filter_summary": "status=paid",
        },
        "cursor": {
            "schema_version": "business_query_result_cursor.v1",
            "cursor_id": "cursor-current-raw-should-not-leak",
            "has_more": True,
            "limit": 20,
            "next_cursor": {"cursor_id": "cursor-next-raw-should-not-leak", "direction": "next"},
        },
        "scope": {"scope_label": "当前权限范围"},
    }


def test_business_query_api_payload_allowlists_fields_and_strips_raw_rows() -> None:
    payload = _business_query_result(
        rows=[
            {
                "order_no": "ORD-BQ-001",
                "status": "paid",
                "amount": "99.00",
                "tenant_id": "TENANT-SHOULD-NOT-LEAK",
                "merchant_scope": {"merchant_ids": ["MERCHANT-SHOULD-NOT-LEAK"]},
                "raw_payload": {"customer_phone": "13800000000"},
                "raw_args": {"sql": "SELECT * FROM orders"},
                "routing_hints": {"route": "debug"},
            }
        ]
    )

    projected = safe_business_query_api_payload(payload)

    assert set(projected) == {
        "operation",
        "resource_label",
        "result_label",
        "scope_label",
        "time_label",
        "filters_label",
        "freshness_label",
        "fields_label",
        "safe_reason",
        "rows",
        "row_count",
        "limit",
        "cursor_label",
        "allowed_drilldowns",
        "group_by_label",
        "compare_label",
    }
    assert projected["operation"] == "list"
    assert projected["resource_label"] == "订单"
    assert projected["row_count"] == 1
    assert projected["limit"] == 20
    assert projected["cursor_label"] == "还有更多结果"
    assert projected["rows"] == [{"order_no": "ORD-BQ-001", "status": "paid", "amount": "99.00"}]

    serialized = json.dumps(projected, ensure_ascii=False)
    for forbidden in (
        "TENANT-SHOULD-NOT-LEAK",
        "MERCHANT-SHOULD-NOT-LEAK",
        "13800000000",
        "SELECT * FROM orders",
        "raw_payload",
        "raw_args",
        "routing_hints",
        "merchant_scope",
        "cursor-next-raw-should-not-leak",
    ):
        assert forbidden not in serialized


def test_projected_business_query_payload_rejects_sensitive_values_inside_labels() -> None:
    projected = safe_business_query_api_payload(
        {
            "operation": "list",
            "resource_label": "订单",
            "result_label": "ORD-SECRET-DENIED",
            "scope_label": "MERCHANT-SECRET",
            "time_label": "tenant-001",
            "filters_label": "raw filter payload",
            "freshness_label": "cursor-raw-should-not-leak",
            "fields_label": "merchant_scope.MERCHANT-SECRET",
            "safe_reason": "ok",
            "rows": [{"order_no": "ORD-BQ-001", "status": "paid"}],
            "row_count": 1,
            "limit": 20,
            "cursor_label": "cursor-raw-should-not-leak",
            "allowed_drilldowns": ["detail"],
            "group_by_label": "raw group",
            "compare_label": "ORD-SECRET-DENIED",
        }
    )

    assert projected["resource_label"] == "订单"
    assert projected["result_label"] == ""
    assert projected["scope_label"] == "当前权限范围"
    assert projected["time_label"] == "指定时间范围"
    assert projected["filters_label"] == "无"
    assert projected["freshness_label"] == "当前可用业务数据"
    assert projected["fields_label"] == ""
    assert projected["cursor_label"] == ""
    assert projected["group_by_label"] == ""
    assert projected["compare_label"] == ""
    assert projected["rows"] == [{"order_no": "ORD-BQ-001", "status": "paid"}]

    serialized = json.dumps(projected, ensure_ascii=False)
    for forbidden in (
        "ORD-SECRET-DENIED",
        "MERCHANT-SECRET",
        "tenant-001",
        "raw filter payload",
        "cursor-raw-should-not-leak",
        "merchant_scope",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("operation", "rows", "expected"),
    [
        ("aggregate", [{"metric_id": "order_count", "display_value": "12", "value": 12}], "12"),
        ("list", [{"order_no": f"ORD-BQ-{index:03d}", "status": "paid"} for index in range(1, 8)], "7 条"),
        ("detail", [{"order_no": "ORD-BQ-001", "status": "paid", "amount": "99.00"}], "订单详情"),
        ("breakdown", [{"status": "delivered", "value": 3, "display_value": "3"}], "按状态分组"),
        (
            "compare",
            [{"metric_id": "order_count", "current_value": 5, "previous_value": 2, "delta": 3, "display_value": "5"}],
            "对比",
        ),
    ],
)
def test_business_query_response_text_is_operation_specific_and_prompt_bounded(
    operation: str,
    rows: list[dict],
    expected: str,
) -> None:
    text = business_query_response_text(_business_query_result(operation=operation, rows=rows))

    assert expected in text
    assert "范围：当前权限范围" in text
    assert "时间：本周" in text
    assert "筛选：status=paid" in text
    assert "政策依据" not in text
    assert "RAG" not in text
    assert "ORD-BQ-006" not in text
    assert "ORD-BQ-007" not in text


def test_business_query_denied_detail_uses_no_existence_leak_copy_without_sensitive_id() -> None:
    payload = _business_query_result(operation="detail", rows=[], status="permission_denied")
    payload["answer_context"]["query_spec"]["resource_id"] = "ORD-SECRET-DENIED"

    text = business_query_response_text(payload)
    metadata = safe_business_query_metadata(payload)

    assert text == "当前权限范围内无法提供该业务数据。"
    assert metadata["safe_reason"] == "scope_denied_no_existence_leak"
    serialized = json.dumps(metadata, ensure_ascii=False)
    assert "ORD-SECRET-DENIED" not in serialized


def test_business_query_projection_rejects_unwrapped_tool_result_data_dicts() -> None:
    raw_tool_data = {
        "business_query": _business_query_result(),
        "raw_args": {"sql": "SELECT * FROM orders"},
    }

    with pytest.raises(ValueError, match="normalized business_query"):
        safe_business_query_api_payload(raw_tool_data)
