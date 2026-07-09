"""Declarative catalog for all graph-facing tool capabilities."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.business.query.registry import BUSINESS_QUERY_REGISTRY
from src.business.query.schemas import BusinessQueryResultV1, BusinessQuerySpec
from src.tools.contracts import ToolError, ToolResultV2


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    kind: Literal["read", "retrieval", "write"]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: Literal["read", "retrieval", "write"]
    side_effect: Literal["none", "read_only", "retrieval", "write"]
    required_permission: str
    caller_allowlist: list[str]
    event_family: Literal["tool_call_*", "rag_retrieval_*", "action"] | None
    resource_type: str | None
    executor: Literal["business", "knowledge", "memory", "action"] | None = None
    exposure: Literal["planner_visible", "node_only", "internal"] = "planner_visible"
    requires_approval: bool = False
    requires_safety_snapshot: bool = False
    requires_idempotency_key: bool = False


@dataclass(frozen=True)
class RegisteredTool:
    descriptor: ToolDescriptor
    adapter: Any | None = None


_GENERIC_OBJECT_SCHEMA: dict[str, Any] = {"type": "object"}
_NULLABLE_STRING_SCHEMA: dict[str, Any] = {"type": ["string", "null"]}
_NO_DATA_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}
_ORDER_RELATION_HINTS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "has_active_refund": {"type": "boolean"},
        "latest_refund_case_id": _NULLABLE_STRING_SCHEMA,
        "has_open_ticket": {"type": "boolean"},
        "latest_ticket_id": _NULLABLE_STRING_SCHEMA,
    },
    "required": [
        "has_active_refund",
        "latest_refund_case_id",
        "has_open_ticket",
        "latest_ticket_id",
    ],
    "additionalProperties": False,
}
_ORDER_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "order_no": {"type": "string", "minLength": 1},
        "merchant_id": {"type": "string", "minLength": 1},
        "status": {"type": "string", "minLength": 1},
        "amount": {"type": "string", "minLength": 1},
        "currency": {"type": "string", "minLength": 1},
        "buyer_name": {"type": "string", "minLength": 1},
        "item_name": {"type": "string", "minLength": 1},
        "paid_at": _NULLABLE_STRING_SCHEMA,
        "delivered_at": _NULLABLE_STRING_SCHEMA,
        "relation_hints": _ORDER_RELATION_HINTS_OUTPUT_SCHEMA,
    },
    "required": [
        "order_no",
        "merchant_id",
        "status",
        "amount",
        "currency",
        "buyer_name",
        "item_name",
        "paid_at",
        "delivered_at",
        "relation_hints",
    ],
    "additionalProperties": False,
}
_REFUND_CASE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "refund_case_no": {"type": "string", "minLength": 1},
        "merchant_id": {"type": "string", "minLength": 1},
        "status": {"type": "string", "minLength": 1},
        "reason_code": {"type": "string", "minLength": 1},
        "reason_text": {"type": "string", "minLength": 1},
        "requested_amount": {"type": "string", "minLength": 1},
        "approved_amount": _NULLABLE_STRING_SCHEMA,
    },
    "required": [
        "refund_case_no",
        "merchant_id",
        "status",
        "reason_code",
        "reason_text",
        "requested_amount",
        "approved_amount",
    ],
    "additionalProperties": False,
}
_TICKET_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ticket_no": {"type": "string", "minLength": 1},
        "merchant_id": {"type": "string", "minLength": 1},
        "status": {"type": "string", "minLength": 1},
        "channel": {"type": "string", "minLength": 1},
        "summary": {"type": "string", "minLength": 1},
    },
    "required": ["ticket_no", "merchant_id", "status", "channel", "summary"],
    "additionalProperties": False,
}
_SEARCH_POLICY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "retrieval_status": {
            "type": "string",
            "enum": ["strong_evidence", "partial_evidence", "no_evidence", "error"],
        },
        "best_score": {"type": "number"},
        "threshold": {"type": "number"},
        "summary": _NULLABLE_STRING_SCHEMA,
    },
    "required": ["retrieval_status", "best_score", "threshold", "summary"],
    "additionalProperties": False,
}
_BUSINESS_METRIC_ID_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": list(BUSINESS_QUERY_REGISTRY.metrics()),
}
_BUSINESS_METRIC_TIME_PRESET_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": list(BUSINESS_QUERY_REGISTRY.time_presets()),
}
_BUSINESS_METRIC_STATUS_FILTER_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {"type": "string", "minLength": 1},
}
_BUSINESS_METRIC_SCOPE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tenant_id": {"type": "string", "minLength": 1},
        "merchant_ids": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "scope_label": {"type": "string", "minLength": 1},
    },
    "required": ["tenant_id", "merchant_ids", "scope_label"],
    "additionalProperties": False,
}
_BUSINESS_METRIC_TIME_RANGE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "start_at": _NULLABLE_STRING_SCHEMA,
        "end_at": _NULLABLE_STRING_SCHEMA,
        "preset": {"type": ["string", "null"]},
        "timezone": {"type": "string", "minLength": 1},
    },
    "required": ["start_at", "end_at", "preset", "timezone"],
    "additionalProperties": False,
}
_BUSINESS_METRIC_FILTERS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "merchant_id": _NULLABLE_STRING_SCHEMA,
        "status_filter": _BUSINESS_METRIC_STATUS_FILTER_SCHEMA,
    },
    "required": ["merchant_id", "status_filter"],
    "additionalProperties": False,
}
_BUSINESS_METRIC_FRESHNESS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "data_freshness_at": _NULLABLE_STRING_SCHEMA,
        "computed_at": {"type": "string", "minLength": 1},
        "source_system": {"type": "string", "minLength": 1},
    },
    "required": ["data_freshness_at", "computed_at", "source_system"],
    "additionalProperties": False,
}
_BUSINESS_METRIC_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "metric_id": _BUSINESS_METRIC_ID_SCHEMA,
        "status": {
            "type": "string",
            "enum": ["ok", "permission_denied", "invalid_request", "non_computable"],
        },
        "value": {"type": ["number", "null"]},
        "rate": {"type": ["number", "null"]},
        "numerator": {"type": ["integer", "null"]},
        "denominator": {"type": ["integer", "null"]},
        "unit": {"type": "string", "minLength": 1},
        "display_value": {"type": "string", "minLength": 1},
        "scope": _BUSINESS_METRIC_SCOPE_OUTPUT_SCHEMA,
        "time_range": _BUSINESS_METRIC_TIME_RANGE_OUTPUT_SCHEMA,
        "filters": _BUSINESS_METRIC_FILTERS_OUTPUT_SCHEMA,
        "freshness": _BUSINESS_METRIC_FRESHNESS_OUTPUT_SCHEMA,
        "formula": {"type": "string", "minLength": 1},
        "caveats": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "no_leak_status": {
            "type": "string",
            "enum": ["not_applicable", "scope_denied_no_existence_leak"],
        },
    },
    "required": [
        "metric_id",
        "status",
        "value",
        "rate",
        "numerator",
        "denominator",
        "unit",
        "display_value",
        "scope",
        "time_range",
        "filters",
        "freshness",
        "formula",
        "caveats",
        "no_leak_status",
    ],
    "additionalProperties": False,
}
_BUSINESS_QUERY_OPERATION_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": list(BUSINESS_QUERY_REGISTRY.operation_ids()),
}
_BUSINESS_QUERY_RESOURCE_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": list(BUSINESS_QUERY_REGISTRY.resource_ids()),
}
_BUSINESS_QUERY_METRIC_SCHEMA: dict[str, Any] = {
    "type": ["string", "null"],
    "enum": list(BUSINESS_QUERY_REGISTRY.metric_ids()),
}
_BUSINESS_QUERY_TIME_PRESET_SCHEMA: dict[str, Any] = {
    "type": ["string", "null"],
    "enum": list(BUSINESS_QUERY_REGISTRY.time_preset_ids()),
}
_BUSINESS_QUERY_STATUS_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "string",
        "enum": sorted(
            {
                status
                for descriptor in BUSINESS_QUERY_REGISTRY.statuses().values()
                for status in descriptor.values
            }
        ),
        "minLength": 1,
    },
}
_BUSINESS_QUERY_FILTERS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status_filter": _BUSINESS_QUERY_STATUS_SCHEMA,
    },
    "required": [],
    "additionalProperties": False,
}
_BUSINESS_QUERY_FIELD_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "string",
        "enum": sorted({descriptor.id for descriptor in BUSINESS_QUERY_REGISTRY.fields().values()}),
        "minLength": 1,
    },
}
_BUSINESS_QUERY_SORT_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "properties": {
        "field": {
            "type": "string",
            "enum": sorted({descriptor.field_id for descriptor in BUSINESS_QUERY_REGISTRY.sorts().values()}),
            "minLength": 1,
        },
        "direction": {"type": "string", "enum": ["asc", "desc"]},
    },
    "required": ["field", "direction"],
    "additionalProperties": False,
}
_BUSINESS_QUERY_CURSOR_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "properties": {
        "cursor_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "direction": {"type": "string", "enum": ["next", "previous"]},
    },
    "required": ["cursor_id"],
    "additionalProperties": False,
}
_BUSINESS_QUERY_INPUT_PROPERTIES: dict[str, Any] = {
    "operation": _BUSINESS_QUERY_OPERATION_SCHEMA,
    "resource": _BUSINESS_QUERY_RESOURCE_SCHEMA,
    "metric_id": _BUSINESS_QUERY_METRIC_SCHEMA,
    "time_preset": _BUSINESS_QUERY_TIME_PRESET_SCHEMA,
    "start_at": _NULLABLE_STRING_SCHEMA,
    "end_at": _NULLABLE_STRING_SCHEMA,
    "merchant_id": _NULLABLE_STRING_SCHEMA,
    "resource_id": _NULLABLE_STRING_SCHEMA,
    "filters": _BUSINESS_QUERY_FILTERS_SCHEMA,
    "fields": _BUSINESS_QUERY_FIELD_SCHEMA,
    "group_by": {
        "type": ["string", "null"],
        "enum": sorted(
            {
                descriptor.id
                for operation in BUSINESS_QUERY_REGISTRY.operations().values()
                for descriptor in BUSINESS_QUERY_REGISTRY.fields().values()
                if f"{descriptor.resource_id}.{descriptor.id}" in operation.group_by_field_ids
            }
        ),
    },
    "compare_to": {"type": ["string", "null"], "enum": ["previous_period"]},
    "sort": _BUSINESS_QUERY_SORT_SCHEMA,
    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
    "cursor": _BUSINESS_QUERY_CURSOR_SCHEMA,
}
_BUSINESS_QUERY_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        name: schema
        for name, schema in _BUSINESS_QUERY_INPUT_PROPERTIES.items()
        if name in BusinessQuerySpec.model_fields
    },
    "required": ["operation", "resource"],
    "additionalProperties": False,
}
_BUSINESS_QUERY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string", "enum": ["business_query_result.v1"]},
        "operation": _BUSINESS_QUERY_OPERATION_SCHEMA,
        "resource": _BUSINESS_QUERY_RESOURCE_SCHEMA,
        "status": {
            "type": "string",
            "enum": ["ok", "partial", "empty", "permission_denied", "invalid_request", "unavailable"],
        },
        "rows": {"type": "array", "items": {"type": "object"}},
        "answer_context": {"type": ["object", "null"]},
        "cursor": {"type": ["object", "null"]},
        "scope": {"type": ["object", "null"]},
    },
    "required": list(BusinessQueryResultV1.model_fields),
    "additionalProperties": False,
}
_CASE_MEMORY_REF_ARRAY_SCHEMA: dict[str, Any] = {"type": "array", "items": {"type": "object"}}
_CASE_MEMORY_ITEM_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "case_memory_id": {"type": "string", "minLength": 1},
        "excerpt": {"type": "string", "minLength": 1},
        "applicability": _NULLABLE_STRING_SCHEMA,
        "outcome": _NULLABLE_STRING_SCHEMA,
        "caveats": _NULLABLE_STRING_SCHEMA,
        "score": {"type": "number"},
        "policy_refs": _CASE_MEMORY_REF_ARRAY_SCHEMA,
        "source_refs": _CASE_MEMORY_REF_ARRAY_SCHEMA,
    },
    "required": [
        "case_memory_id",
        "excerpt",
        "applicability",
        "outcome",
        "caveats",
        "score",
        "policy_refs",
        "source_refs",
    ],
    "additionalProperties": False,
}
_SEARCH_CASE_MEMORY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": _CASE_MEMORY_ITEM_OUTPUT_SCHEMA},
    },
    "required": ["items"],
    "additionalProperties": False,
}
_DRAFT_OUTCOME_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string", "enum": ["draft_outcome.v1"]},
        "status": {"type": "string", "enum": ["not_executed_demo"]},
        "external_side_effect": {"type": "boolean"},
        "tenant_id": _NULLABLE_STRING_SCHEMA,
        "run_id": _NULLABLE_STRING_SCHEMA,
        "draft_id": _NULLABLE_STRING_SCHEMA,
        "created_at": _NULLABLE_STRING_SCHEMA,
    },
    "required": [
        "schema_version",
        "status",
        "external_side_effect",
        "tenant_id",
        "run_id",
        "draft_id",
        "created_at",
    ],
    "additionalProperties": False,
}
_ACTION_DRAFT_DATA_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string", "enum": ["action_draft.v2"]},
        "tenant_id": {"type": "string", "minLength": 1},
        "run_id": {"type": "string", "minLength": 1},
        "draft_id": {"type": "string", "minLength": 1},
        "proposed_action": {"type": "object"},
        "action_payload_hash": {"type": "string", "minLength": 1},
        "approval_ref": _NULLABLE_STRING_SCHEMA,
        "approval_revision_ref": _NULLABLE_STRING_SCHEMA,
        "safety_snapshot_ref": {"type": "string", "minLength": 1},
        "safety_snapshot_hash": {"type": "string", "minLength": 1},
        "target_id": {"type": "string", "minLength": 1},
        "target_merchant_id": _NULLABLE_STRING_SCHEMA,
        "target_merchant_ref": {"type": ["object", "null"]},
        "business_fact_refs": {"type": "array", "items": {"type": "object"}},
        "verified_evidence_refs": {"type": "array", "items": {"type": "object"}},
        "claim_verification_ref": _NULLABLE_STRING_SCHEMA,
        "claim_verification_summary": {"type": ["object", "null"]},
        "risk_decision_ref": _NULLABLE_STRING_SCHEMA,
        "risk_decision": {"type": ["object", "null"]},
        "auto_allowed_binding_ref": _NULLABLE_STRING_SCHEMA,
        "idempotency_key": {"type": "string", "minLength": 1},
        "status": {"type": "string", "minLength": 1},
        "execution_mode": {"type": "string", "enum": ["demo"]},
        "draft_version": {"type": "integer"},
        "lifecycle_status": {"type": "string", "minLength": 1},
        "retention_policy": {"type": "string", "minLength": 1},
        "draft_outcome": _DRAFT_OUTCOME_OUTPUT_SCHEMA,
        "created_at": _NULLABLE_STRING_SCHEMA,
    },
    "required": [
        "schema_version",
        "tenant_id",
        "run_id",
        "draft_id",
        "proposed_action",
        "action_payload_hash",
        "approval_ref",
        "approval_revision_ref",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
        "target_id",
        "target_merchant_id",
        "target_merchant_ref",
        "business_fact_refs",
        "verified_evidence_refs",
        "claim_verification_ref",
        "claim_verification_summary",
        "risk_decision_ref",
        "risk_decision",
        "auto_allowed_binding_ref",
        "idempotency_key",
        "status",
        "execution_mode",
        "draft_version",
        "lifecycle_status",
        "retention_policy",
        "draft_outcome",
        "created_at",
    ],
    "additionalProperties": False,
}
_ACTION_RESULT_COMPAT_DATA_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "draft_id": {"type": "string", "minLength": 1},
        "draft_outcome": _DRAFT_OUTCOME_OUTPUT_SCHEMA,
    },
    "required": ["draft_id", "draft_outcome"],
    "additionalProperties": False,
}
_ACTION_RESULT_COMPAT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "minLength": 1},
        "data": _ACTION_RESULT_COMPAT_DATA_OUTPUT_SCHEMA,
        "error": _NO_DATA_OUTPUT_SCHEMA,
        "compatibility": {"type": "string", "minLength": 1},
    },
    "required": ["status", "data", "error", "compatibility"],
    "additionalProperties": False,
}
_ACTION_DRAFT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "draft_id": {"type": "string", "minLength": 1},
        "idempotency_key": {"type": "string", "minLength": 1},
        "status": {"type": "string", "minLength": 1},
        "created": {"type": "boolean"},
        "idempotent_reused": {"type": "boolean"},
        "action_draft": _ACTION_DRAFT_DATA_OUTPUT_SCHEMA,
        "draft_outcome": _DRAFT_OUTCOME_OUTPUT_SCHEMA,
        "execution_mode": {"type": "string", "enum": ["demo"]},
        "action_result": _ACTION_RESULT_COMPAT_OUTPUT_SCHEMA,
    },
    "required": [
        "draft_id",
        "idempotency_key",
        "status",
        "created",
        "idempotent_reused",
        "action_draft",
        "draft_outcome",
        "execution_mode",
        "action_result",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class _ToolDeclaration:
    name: str
    kind: Literal["read", "retrieval", "write"]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    side_effect: Literal["read_only", "retrieval", "write"]
    caller_allowlist: tuple[str, ...]
    event_family: Literal["tool_call_*", "rag_retrieval_*", "action"] | None
    resource_type: str | None
    executor: Literal["business", "knowledge", "memory", "action"] | None = None
    description: str = ""
    exposure: Literal["planner_visible", "node_only", "internal"] = "planner_visible"
    requires_approval: bool = False
    requires_safety_snapshot: bool = False
    requires_idempotency_key: bool = False


_TOOL_DECLARATIONS: tuple[_ToolDeclaration, ...] = (
    _ToolDeclaration(
        name="get_order",
        kind="read",
        input_schema={
            "type": "object",
            "properties": {"order_no": {"type": "string", "minLength": 1}},
            "required": ["order_no"],
        },
        output_schema=_ORDER_OUTPUT_SCHEMA,
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="order",
        executor="business",
    ),
    _ToolDeclaration(
        name="get_refund_case",
        kind="read",
        input_schema={
            "type": "object",
            "properties": {"refund_case_no": {"type": "string", "minLength": 1}},
            "required": ["refund_case_no"],
        },
        output_schema=_REFUND_CASE_OUTPUT_SCHEMA,
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="refund_case",
        executor="business",
    ),
    _ToolDeclaration(
        name="get_ticket",
        kind="read",
        input_schema={
            "type": "object",
            "properties": {"ticket_id": {"type": "string", "minLength": 1}},
            "required": ["ticket_id"],
        },
        output_schema=_TICKET_OUTPUT_SCHEMA,
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="ticket",
        executor="business",
    ),
    _ToolDeclaration(
        name="get_logistics",
        kind="read",
        input_schema={
            "type": "object",
            "properties": {"tracking_no": {"type": "string", "minLength": 1}},
            "required": ["tracking_no"],
        },
        output_schema=_NO_DATA_OUTPUT_SCHEMA,
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="logistics",
        executor="business",
    ),
    _ToolDeclaration(
        name="get_merchant_risk",
        kind="read",
        input_schema={
            "type": "object",
            "properties": {"merchant_id": {"type": "string", "minLength": 1}},
            "required": ["merchant_id"],
        },
        output_schema=_NO_DATA_OUTPUT_SCHEMA,
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="merchant_risk",
        executor="business",
    ),
    _ToolDeclaration(
        name="business_query",
        kind="read",
        input_schema=_BUSINESS_QUERY_INPUT_SCHEMA,
        output_schema=_BUSINESS_QUERY_OUTPUT_SCHEMA,
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="business_query",
        executor="business",
        description=(
            "Prepare a scoped read-only business_query request for aggregate, list, "
            "detail, breakdown, or compare business facts."
        ),
    ),
    _ToolDeclaration(
        name="query_business_metric",
        kind="read",
        input_schema={
            "type": "object",
            "properties": {
                "metric_id": _BUSINESS_METRIC_ID_SCHEMA,
                "time_preset": _BUSINESS_METRIC_TIME_PRESET_SCHEMA,
                "start_at": {"type": "string", "minLength": 1},
                "end_at": {"type": "string", "minLength": 1},
                "merchant_id": {"type": "string", "minLength": 1},
                "status_filter": _BUSINESS_METRIC_STATUS_FILTER_SCHEMA,
            },
            "required": ["metric_id"],
            "additionalProperties": False,
        },
        output_schema=_BUSINESS_METRIC_OUTPUT_SCHEMA,
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="business_metric",
        executor="business",
        description="Compute scoped read-only business metrics from authorized MOCA business records.",
    ),
    _ToolDeclaration(
        name="search_policy",
        kind="retrieval",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "primary_intent": {"type": "string", "minLength": 1},
                "merchant_id": {"type": "string", "minLength": 1},
                "max_results": {"type": "integer"},
                "allow_partial_evidence": {"type": "boolean"},
            },
            "required": ["query"],
        },
        output_schema=_SEARCH_POLICY_OUTPUT_SCHEMA,
        side_effect="retrieval",
        caller_allowlist=("investigate",),
        event_family="rag_retrieval_*",
        resource_type=None,
        executor="knowledge",
    ),
    _ToolDeclaration(
        name="search_sop",
        kind="retrieval",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 1}},
            "required": ["query"],
        },
        output_schema=_NO_DATA_OUTPUT_SCHEMA,
        side_effect="retrieval",
        caller_allowlist=("investigate",),
        event_family="rag_retrieval_*",
        resource_type=None,
        executor="knowledge",
    ),
    _ToolDeclaration(
        name="search_case_memory",
        description=(
            "Retrieve reviewed case memory precedents from the reviewed case store. "
            "Returned snippets are contextual only, not policy evidence or action authority."
        ),
        kind="retrieval",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 1}},
            "required": ["query"],
        },
        output_schema=_SEARCH_CASE_MEMORY_OUTPUT_SCHEMA,
        side_effect="retrieval",
        caller_allowlist=("investigate",),
        event_family="rag_retrieval_*",
        resource_type=None,
        executor="memory",
    ),
    _ToolDeclaration(
        name="create_coupon_grant_draft",
        kind="write",
        input_schema={
            "type": "object",
            "properties": {
                "approval_request_id": {"type": "string", "minLength": 1},
                "action_type": {"type": "string", "minLength": 1},
                "payload": {"type": "object"},
                "action_payload_hash": {"type": "string", "minLength": 1},
                "safety_snapshot_ref": {"type": "string", "minLength": 1},
                "safety_snapshot_hash": {"type": "string", "minLength": 1},
                "target_merchant_id": {"type": "string", "minLength": 1},
                "target_merchant_ref": {"type": "object"},
                "business_fact_refs": {"type": "array", "items": {"type": "object"}},
                "verified_evidence_refs": {"type": "array", "items": {"type": "object"}},
                "claim_verification_ref": {"type": "string", "minLength": 1},
                "claim_verification_summary": {"type": "object"},
                "risk_decision_ref": {"type": "string", "minLength": 1},
                "risk_decision": {"type": "object"},
                "auto_allowed_binding": {"type": "object"},
            },
            "required": [
                "action_type",
                "payload",
                "action_payload_hash",
                "safety_snapshot_ref",
                "safety_snapshot_hash",
            ],
        },
        output_schema=_ACTION_DRAFT_OUTPUT_SCHEMA,
        side_effect="write",
        caller_allowlist=("action_draft",),
        event_family="action",
        resource_type=None,
        executor="action",
        exposure="node_only",
        requires_safety_snapshot=True,
        requires_idempotency_key=True,
    ),
)
_IDENTIFIER_SCHEMAS = {declaration.name: declaration.input_schema for declaration in _TOOL_DECLARATIONS}


def _descriptor(declaration: _ToolDeclaration) -> ToolDescriptor:
    return ToolDescriptor(
        name=declaration.name,
        description=declaration.description,
        kind=declaration.kind,
        input_schema=declaration.input_schema,
        output_schema=declaration.output_schema,
        risk_level=declaration.kind,
        side_effect=declaration.side_effect,
        required_permission=f"tool:{declaration.name}",
        caller_allowlist=list(declaration.caller_allowlist),
        event_family=declaration.event_family,
        resource_type=declaration.resource_type,
        executor=declaration.executor,
        exposure=declaration.exposure,
        requires_approval=declaration.requires_approval,
        requires_safety_snapshot=declaration.requires_safety_snapshot,
        requires_idempotency_key=declaration.requires_idempotency_key,
    )


def _default_descriptors() -> list[ToolDescriptor]:
    return [_descriptor(declaration) for declaration in _TOOL_DECLARATIONS]


def investigate_tool_names(descriptors: Iterable[ToolDescriptor] | None = None) -> frozenset[str]:
    source = descriptors if descriptors is not None else _default_descriptors()
    return frozenset(
        descriptor.name
        for descriptor in source
        if "investigate" in descriptor.caller_allowlist
        and descriptor.kind != "write"
        and descriptor.exposure == "planner_visible"
    )


class ToolCatalog:
    def __init__(self, tools: Iterable[RegisteredTool] | None = None) -> None:
        if tools is None:
            registered_tools = [RegisteredTool(descriptor=descriptor) for descriptor in _default_descriptors()]
        else:
            registered_tools = list(tools)

        self._tools: dict[str, RegisteredTool] = {}
        for tool in registered_tools:
            name = tool.descriptor.name
            if name in self._tools:
                raise ValueError(f"Duplicate tool registry entry: {name}")
            self._tools[name] = tool

    def descriptors(self) -> list[ToolDescriptor]:
        return [tool.descriptor for tool in self._tools.values()]

    def descriptor(self, name: str) -> ToolDescriptor | None:
        tool = self._tools.get(name)
        return tool.descriptor if tool else None

    async def invoke(
        self,
        name: str,
        input_data: dict[str, Any],
        ctx: Any,
        session: Any,
    ) -> ToolResultV2:
        """Compatibility shim: the catalog never executes tools."""

        del input_data, ctx, session
        tool = self._tools.get(name)
        if tool is None:
            return self._result(
                "not_found",
                "Requested tool is not registered",
                code="TOOL_NOT_FOUND",
                source="caller",
            )
        return self._result(
            "unavailable",
            "ToolCatalog is declaration-only; use ToolPlatform",
            code="TOOL_REGISTRY_DECLARATION_ONLY",
            source="tool",
        )

    @staticmethod
    def _result(
        status: Literal["not_found", "unavailable"],
        summary: str,
        *,
        code: str,
        source: Literal["caller", "tool"],
    ) -> ToolResultV2:
        return ToolResultV2(
            status=status,
            data=None,
            summary=summary,
            source_system="tool_catalog",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=ToolError(code=code, safe_message=summary, retryable=False, source=source),
            retryable=False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )
