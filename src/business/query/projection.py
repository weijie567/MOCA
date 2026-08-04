from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.business.query.registry import BUSINESS_QUERY_REGISTRY
from src.business.query.schemas import BusinessQueryResultV1

BUSINESS_QUERY_API_PAYLOAD_FIELDS: tuple[str, ...] = (
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
)

_RESOURCE_LABELS = {
    "order": "订单",
    "refund_case": "退款单",
    "ticket": "工单",
    "coupon_record": "补偿券记录",
    "merchant_metric": "商家指标",
}
_METRIC_LABELS = {
    "order_count": "订单数",
    "refund_case_count": "退款单数",
    "pending_ticket_count": "待处理工单数",
    "coupon_record_count": "补偿券记录数",
    "merchant_refund_rate": "商户退款率",
}
_FIELD_LABELS = {
    "order_no": "订单号",
    "status": "状态",
    "amount": "金额",
    "currency": "币种",
    "item_name": "商品",
    "paid_at": "支付时间",
    "delivered_at": "送达时间",
    "created_at": "创建时间",
    "refund_case_no": "退款单号",
    "ticket_no": "工单号",
    "coupon_record_no": "补偿券记录号",
    "metric_id": "指标",
    "display_value": "结果",
    "computed_at": "计算时间",
}
_TIME_LABELS = {
    "today": "今天",
    "this_week": "本周",
    "this_month": "本月",
    "this_quarter": "本季度",
    "this_year": "今年",
    "current_snapshot": "当前",
}
_SCOPE_LABELS = {
    "authorized_merchants": "当前权限范围",
    "all_authorized_merchants": "当前权限范围",
}
_MAX_PROMPT_ROWS = 5
_MAX_API_ROWS = 20
_SAFE_AGGREGATE_ROW_FIELDS = frozenset(
    {
        "metric_id",
        "metric_label",
        "display_value",
        "value",
        "rate",
        "numerator",
        "denominator",
        "unit",
        "formula",
        "caveats",
    }
)
_SAFE_ANALYTIC_ROW_FIELDS = frozenset(
    {
        "metric_id",
        "metric_label",
        "status",
        "display_value",
        "value",
        "rate",
        "numerator",
        "denominator",
        "current_value",
        "previous_value",
        "delta",
    }
)
_FORBIDDEN_KEY_MARKERS = (
    "raw",
    "tenant",
    "merchant_scope",
    "routing",
    "prompt",
    "tool_arg",
    "stack",
    "debug",
    "cursor_id",
    "next_cursor",
)
_FORBIDDEN_DISPLAY_LABEL_MARKERS = (
    "raw",
    "cursor-",
    "tenant",
    "merchant",
    "ord-secret",
    "secret-denied",
    "should-not-leak",
)


def business_query_response_text(payload: dict[str, Any]) -> str:
    metadata = safe_business_query_metadata(payload)
    if metadata["safe_reason"] == "scope_denied_no_existence_leak":
        return "当前权限范围内无法提供该业务数据。"
    if metadata["safe_reason"] == "empty":
        return "当前权限范围和筛选条件下没有可显示的结果。"

    operation = metadata["operation"]
    lines = [_business_query_first_line(metadata)]
    if operation == "list":
        identifiers = _safe_row_identifiers(metadata["rows"])
        if identifiers:
            lines.append(f"可显示的安全标识：{'、'.join(identifiers[:_MAX_PROMPT_ROWS])}。")
    lines.append(
        f"范围：{metadata['scope_label']}；"
        f"时间：{metadata['time_label']}；"
        f"筛选：{metadata['filters_label']}；"
        f"新鲜度：{metadata['freshness_label']}。"
    )
    return "\n".join(lines)


def safe_business_query_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    if _looks_projected_api_payload(payload):
        return _sanitize_projected_api_payload(payload)

    result = _validate_normalized_business_query(payload)
    query_spec = result.answer_context.query_spec if result.answer_context else None
    rows = _safe_rows(result)
    row_count = len(result.rows)
    cursor = result.cursor or (result.answer_context.cursor if result.answer_context else None)
    limit = cursor.limit if cursor is not None else query_spec.limit if query_spec is not None else max(row_count, 1)
    metadata = {
        "operation": result.operation,
        "resource_label": _resource_label(result.resource),
        "result_label": _result_label(result, rows),
        "scope_label": _scope_label(result),
        "time_label": _time_label(result),
        "filters_label": _filters_label(result),
        "freshness_label": _freshness_label(result),
        "fields_label": _fields_label(result),
        "safe_reason": _safe_reason(result),
        "rows": rows[: min(limit, _MAX_API_ROWS)],
        "row_count": row_count,
        "limit": limit,
        "cursor_label": "还有更多结果" if cursor is not None and cursor.has_more else "",
        "allowed_drilldowns": _allowed_drilldowns(result),
        "group_by_label": _group_by_label(result),
        "compare_label": _compare_label(result),
    }
    return _sanitize_projected_api_payload(metadata)


def safe_business_query_api_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return safe_business_query_metadata(payload)


def _validate_normalized_business_query(payload: dict[str, Any]) -> BusinessQueryResultV1:
    if not isinstance(payload, dict) or "business_query" in payload:
        raise ValueError("expected normalized business_query payload")
    try:
        return BusinessQueryResultV1.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("expected normalized business_query payload") from exc


def _looks_projected_api_payload(payload: dict[str, Any]) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("operation") in BUSINESS_QUERY_REGISTRY.operation_ids()
        and ("resource_label" in payload or "result_label" in payload)
    )


def _sanitize_projected_api_payload(payload: dict[str, Any]) -> dict[str, Any]:
    operation = str(payload.get("operation") or "")
    rows = payload.get("rows")
    safe_rows = _sanitize_projected_rows(rows if isinstance(rows, list) else [])
    safe: dict[str, Any] = {
        "operation": operation if operation in BUSINESS_QUERY_REGISTRY.operation_ids() else "",
        "resource_label": _safe_display_label(payload.get("resource_label")),
        "result_label": _safe_display_label(payload.get("result_label")),
        "scope_label": _safe_display_label(payload.get("scope_label")) or "当前权限范围",
        "time_label": _safe_display_label(payload.get("time_label")) or "指定时间范围",
        "filters_label": _safe_display_label(payload.get("filters_label")) or "无",
        "freshness_label": _safe_display_label(payload.get("freshness_label")) or "当前可用业务数据",
        "fields_label": _safe_display_label(payload.get("fields_label")),
        "safe_reason": _safe_text(payload.get("safe_reason")) or "ok",
        "rows": safe_rows[:_MAX_API_ROWS],
        "row_count": _safe_int(payload.get("row_count"), default=len(safe_rows)),
        "limit": _safe_int(payload.get("limit"), default=max(len(safe_rows), 1)),
        "cursor_label": "还有更多结果" if payload.get("cursor_label") == "还有更多结果" else "",
        "allowed_drilldowns": _safe_text_list(payload.get("allowed_drilldowns")),
        "group_by_label": _safe_display_label(payload.get("group_by_label")),
        "compare_label": _safe_display_label(payload.get("compare_label")),
    }
    return {field: safe[field] for field in BUSINESS_QUERY_API_PAYLOAD_FIELDS}


def _sanitize_projected_rows(rows: list[Any]) -> list[dict[str, Any]]:
    return [_sanitize_row_mapping(row, _safe_projected_row_fields()) for row in rows if isinstance(row, dict)]


def _safe_projected_row_fields() -> frozenset[str]:
    return (
        frozenset(descriptor.id for descriptor in BUSINESS_QUERY_REGISTRY.fields().values() if descriptor.safe_for_ui)
        | _SAFE_AGGREGATE_ROW_FIELDS
        | _SAFE_ANALYTIC_ROW_FIELDS
    )


def _safe_rows(result: BusinessQueryResultV1) -> list[dict[str, Any]]:
    fields = _allowed_row_fields(result)
    return [_sanitize_row_mapping(row, fields) for row in result.rows]


def _allowed_row_fields(result: BusinessQueryResultV1) -> frozenset[str]:
    if result.operation == "aggregate":
        return _SAFE_AGGREGATE_ROW_FIELDS
    if result.operation in {"breakdown", "compare"}:
        return _SAFE_ANALYTIC_ROW_FIELDS
    return BUSINESS_QUERY_REGISTRY.field_ids_for_resource(result.resource, purpose="ui")


def _sanitize_row_mapping(row: dict[str, Any], allowed_fields: frozenset[str]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in row.items():
        if key not in allowed_fields or _is_forbidden_key(key):
            continue
        if isinstance(value, str | int | float | bool) or value is None:
            safe[key] = value
        elif isinstance(value, list):
            safe[key] = [item for item in value if isinstance(item, str | int | float | bool)][:5]
    metric_id = safe.get("metric_id")
    if isinstance(metric_id, str) and metric_id in _METRIC_LABELS:
        safe.setdefault("metric_label", _METRIC_LABELS[metric_id])
    return safe


def _business_query_first_line(metadata: dict[str, Any]) -> str:
    operation = metadata["operation"]
    if operation == "aggregate":
        value = _first_row_value(metadata["rows"]) or metadata["result_label"]
        return f"{value}（{metadata['result_label']}）。"
    if operation == "list":
        return f"找到 {metadata['row_count']} 条{metadata['resource_label']}，本次最多展示 {metadata['limit']} 条。"
    if operation == "detail":
        return f"{metadata['resource_label']}详情可在当前权限范围内提供：{_row_summary(metadata['rows'])}。"
    if operation == "breakdown":
        return f"按{metadata['group_by_label'] or '字段'}分组的{metadata['resource_label']}结果已生成：{_row_summary(metadata['rows'])}。"
    if operation == "compare":
        return f"{metadata['compare_label'] or '业务对比'}结果已生成：{_row_summary(metadata['rows'])}。"
    return metadata["result_label"]


def _result_label(result: BusinessQueryResultV1, rows: list[dict[str, Any]]) -> str:
    query_spec = result.answer_context.query_spec if result.answer_context else None
    if result.operation == "aggregate" and query_spec is not None and query_spec.metric_id:
        return _METRIC_LABELS.get(query_spec.metric_id, "业务汇总")
    if result.operation == "list":
        return f"{_resource_label(result.resource)}列表"
    if result.operation == "detail":
        return f"{_resource_label(result.resource)}详情"
    if result.operation == "breakdown":
        return f"按{_group_by_label(result)}分组"
    if result.operation == "compare":
        return _compare_label(result) or "业务对比"
    return _first_row_value(rows) or _resource_label(result.resource)


def _resource_label(resource: str) -> str:
    return _RESOURCE_LABELS.get(resource, resource)


def _scope_label(result: BusinessQueryResultV1) -> str:
    scope = result.scope or (result.answer_context.scope if result.answer_context else None)
    if scope is None:
        return "当前权限范围"
    return _SCOPE_LABELS.get(scope.scope_label, scope.scope_label or "当前权限范围")


def _time_label(result: BusinessQueryResultV1) -> str:
    if result.answer_context is not None and result.answer_context.time_summary:
        return _TIME_LABELS.get(result.answer_context.time_summary, result.answer_context.time_summary)
    query_spec = result.answer_context.query_spec if result.answer_context else None
    if query_spec is not None and query_spec.time_preset:
        return _TIME_LABELS.get(query_spec.time_preset, query_spec.time_preset)
    return "指定时间范围"


def _filters_label(result: BusinessQueryResultV1) -> str:
    if result.answer_context is not None and result.answer_context.filter_summary:
        return result.answer_context.filter_summary
    query_spec = result.answer_context.query_spec if result.answer_context else None
    if query_spec is not None and query_spec.filters.status_filter:
        return "status=" + ",".join(query_spec.filters.status_filter)
    return "无"


def _freshness_label(result: BusinessQueryResultV1) -> str:
    for row in result.rows:
        freshness = row.get("freshness") if isinstance(row, dict) else None
        if isinstance(freshness, dict):
            value = freshness.get("data_freshness_at") or freshness.get("computed_at")
            if isinstance(value, str) and value:
                return value
    return "当前可用业务数据"


def _fields_label(result: BusinessQueryResultV1) -> str:
    fields = result.answer_context.fields_shown if result.answer_context else []
    labels = [_FIELD_LABELS.get(field, field) for field in fields]
    return "、".join(labels)


def _safe_reason(result: BusinessQueryResultV1) -> str:
    if result.status == "permission_denied":
        return "scope_denied_no_existence_leak"
    if result.status == "empty":
        return "empty"
    return result.status


def _allowed_drilldowns(result: BusinessQueryResultV1) -> list[str]:
    if result.answer_context is None:
        return []
    return _safe_text_list(result.answer_context.allowed_drilldowns)


def _group_by_label(result: BusinessQueryResultV1) -> str:
    query_spec = result.answer_context.query_spec if result.answer_context else None
    if query_spec is None or not query_spec.group_by:
        return ""
    return _FIELD_LABELS.get(query_spec.group_by, query_spec.group_by)


def _compare_label(result: BusinessQueryResultV1) -> str:
    query_spec = result.answer_context.query_spec if result.answer_context else None
    if query_spec is None or not query_spec.compare_to:
        return ""
    if query_spec.compare_to == "previous_period":
        return "与上一周期对比"
    return query_spec.compare_to


def _safe_row_identifiers(rows: list[dict[str, Any]]) -> list[str]:
    identifiers: list[str] = []
    for row in rows:
        for key in ("order_no", "refund_case_no", "ticket_no", "coupon_record_no", "metric_id"):
            value = row.get(key)
            if isinstance(value, str) and value:
                identifiers.append(value)
                break
    return identifiers


def _row_summary(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "无可显示结果"
    parts: list[str] = []
    for row in rows[:_MAX_PROMPT_ROWS]:
        label = _safe_row_identifiers([row])
        if label:
            parts.append(label[0])
            continue
        value = _first_row_value([row])
        if value:
            parts.append(value)
    return "、".join(parts) if parts else "已投影安全字段"


def _first_row_value(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    row = rows[0]
    for key in ("display_value", "value", "current_value"):
        value = row.get(key)
        if isinstance(value, str | int | float):
            return str(value)
    return ""


def _safe_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    if _is_forbidden_text(value):
        return ""
    return value[:240]


def _safe_display_label(value: Any) -> str:
    label = _safe_text(value)
    if not label:
        return ""
    lowered = label.lower()
    if any(marker in lowered for marker in _FORBIDDEN_DISPLAY_LABEL_MARKERS):
        return ""
    return label


def _safe_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(item) for item in value if _safe_text(item)][:10]


def _safe_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value >= 0:
        return value
    return default


def _is_forbidden_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _FORBIDDEN_KEY_MARKERS) or lowered in {"merchant_id", "sql"}


def _is_forbidden_text(value: str) -> bool:
    upper = value.upper()
    return any(token in upper for token in ("SELECT ", " FROM ", " JOIN ", " WHERE ", "INSERT ", "UPDATE ", "DELETE "))


__all__ = [
    "BUSINESS_QUERY_API_PAYLOAD_FIELDS",
    "business_query_response_text",
    "safe_business_query_api_payload",
    "safe_business_query_metadata",
]
