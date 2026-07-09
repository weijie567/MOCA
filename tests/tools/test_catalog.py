from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.business.query.registry import BUSINESS_QUERY_REGISTRY
from src.business.query.schemas import BusinessQueryResultV1, BusinessQuerySpec
from src.tools.catalog import _IDENTIFIER_SCHEMAS, RegisteredTool, ToolCatalog, ToolDescriptor, investigate_tool_names
from src.tools.contracts import ToolCallContext
from src.tools.executors.memory import _case_memory_request
from src.tools.validation import SUPPORTED_JSON_SCHEMA_KEYS, _validate_json_value


TPH01_OUTPUT_SCHEMA_TOOL_NAMES = frozenset(
    {
        "get_order",
        "get_refund_case",
        "get_ticket",
        "get_logistics",
        "get_merchant_risk",
        "business_query",
        "query_business_metric",
        "search_policy",
        "search_sop",
        "search_case_memory",
    }
)

NO_DATA_OUTPUT_SCHEMA = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
GENERIC_OBJECT_SCHEMA = {"type": "object"}

EXPECTED_OUTPUT_PROPERTY_KEYS = {
    "get_order": {
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
    },
    "get_refund_case": {
        "refund_case_no",
        "merchant_id",
        "status",
        "reason_code",
        "reason_text",
        "requested_amount",
        "approved_amount",
    },
    "get_ticket": {"ticket_no", "merchant_id", "status", "channel", "summary"},
    "query_business_metric": {
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
    },
    "business_query": {
        "schema_version",
        "operation",
        "resource",
        "status",
        "rows",
        "answer_context",
        "cursor",
        "scope",
    },
    "search_policy": {"retrieval_status", "best_score", "threshold", "summary"},
}
NO_DATA_OUTPUT_SCHEMA_TOOL_NAMES = frozenset({"get_logistics", "get_merchant_risk", "search_sop"})


def _context() -> ToolCallContext:
    return ToolCallContext(
        tenant_id="tenant-1",
        user_id="user-1",
        role="support_agent",
        permissions=["tool:get_order"],
        merchant_scope={"merchant_ids": ["*"]},
        thread_id="thread-1",
        run_id="run-1",
        trace_id="trace-1",
        request_id="request-1",
        tool_call_id="tool-call-1",
        caller_node="investigate",
    )


def _descriptor(name: str) -> ToolDescriptor:
    return next(descriptor for descriptor in ToolCatalog().descriptors() if descriptor.name == name)


def _unsupported_schema_keywords(schema: dict[str, object], *, path: str = "$") -> list[str]:
    unsupported = [f"{path}.{key}" for key in schema if key not in SUPPORTED_JSON_SCHEMA_KEYS]

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for property_name, property_schema in properties.items():
            if isinstance(property_schema, dict):
                unsupported.extend(
                    _unsupported_schema_keywords(property_schema, path=f"{path}.properties.{property_name}")
                )

    items = schema.get("items")
    if isinstance(items, dict):
        unsupported.extend(_unsupported_schema_keywords(items, path=f"{path}.items"))

    return unsupported


def _valid_order_payload() -> dict[str, object]:
    return {
        "order_no": "ORD-1",
        "merchant_id": "merchant-1",
        "status": "paid",
        "amount": "88.00",
        "currency": "CNY",
        "buyer_name": "buyer-1",
        "item_name": "Refund protection package",
        "paid_at": None,
        "delivered_at": None,
        "relation_hints": {
            "has_active_refund": False,
            "latest_refund_case_id": None,
            "has_open_ticket": True,
            "latest_ticket_id": "TICKET-1",
        },
    }


def _valid_case_memory_item() -> dict[str, object]:
    return {
        "case_memory_id": "case-memory-1",
        "excerpt": "Reviewed refund timeout precedent.",
        "applicability": None,
        "outcome": None,
        "caveats": None,
        "score": 0.91,
        "policy_refs": [{"doc_key": "refund_policy", "chunk_id": "chunk-1"}],
        "source_refs": [{"source_system": "demo_refunds_db", "resource_id": "REF-1"}],
    }


def _valid_action_output_payload() -> dict[str, object]:
    draft_outcome = {
        "schema_version": "draft_outcome.v1",
        "status": "not_executed_demo",
        "external_side_effect": False,
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "draft_id": "draft-1",
        "created_at": "2026-07-02T00:00:00Z",
    }
    return {
        "draft_id": "draft-1",
        "idempotency_key": "idem-1",
        "status": "draft_created",
        "created": True,
        "idempotent_reused": False,
        "action_draft": {
            "schema_version": "action_draft.v2",
            "tenant_id": "tenant-1",
            "run_id": "run-1",
            "draft_id": "draft-1",
            "proposed_action": {
                "action_type": "issue_coupon",
                "target_id": "refund-1",
                "amount": "50",
            },
            "action_payload_hash": "sha256:" + "1" * 64,
            "approval_ref": "approval-1",
            "approval_revision_ref": "approval_request/approval-1@rev1",
            "safety_snapshot_ref": "snapshot:test",
            "safety_snapshot_hash": "sha256:" + "2" * 64,
            "target_id": "refund-1",
            "target_merchant_id": "merchant-1",
            "target_merchant_ref": {"target_merchant_id": "merchant-1"},
            "business_fact_refs": [{"resource_type": "refund_case", "resource_id": "refund-1"}],
            "verified_evidence_refs": [{"doc_key": "refund_policy", "chunk_id": "chunk-1"}],
            "claim_verification_ref": "claim-verification-1",
            "claim_verification_summary": {"overall_status": "verified"},
            "risk_decision_ref": "risk-decision-1",
            "risk_decision": {"risk_level": "high"},
            "auto_allowed_binding_ref": None,
            "idempotency_key": "idem-1",
            "status": "draft_created",
            "execution_mode": "demo",
            "draft_version": 1,
            "lifecycle_status": "active",
            "retention_policy": "phase14_demo_draft",
            "draft_outcome": draft_outcome,
            "created_at": "2026-07-02T00:00:00Z",
        },
        "draft_outcome": draft_outcome,
        "execution_mode": "demo",
        "action_result": {
            "status": "draft_created",
            "data": {"draft_id": "draft-1", "draft_outcome": draft_outcome},
            "error": {},
            "compatibility": "Phase 14 deprecated compatibility output",
        },
    }


def test_catalog_registry_derives_identifier_schemas_without_drift() -> None:
    descriptors = ToolCatalog().descriptors()

    assert _IDENTIFIER_SCHEMAS == {descriptor.name: descriptor.input_schema for descriptor in descriptors}


def test_scoped_tools_declare_real_output_schemas() -> None:
    scoped_schemas = {
        descriptor.name: descriptor.output_schema
        for descriptor in ToolCatalog().descriptors()
        if descriptor.name in TPH01_OUTPUT_SCHEMA_TOOL_NAMES
    }

    assert set(scoped_schemas) == TPH01_OUTPUT_SCHEMA_TOOL_NAMES
    for name, schema in scoped_schemas.items():
        assert schema != GENERIC_OBJECT_SCHEMA, name
        assert schema.get("type") == "object", name
        assert schema.get("additionalProperties") is False, name

    for name in sorted(NO_DATA_OUTPUT_SCHEMA_TOOL_NAMES):
        assert scoped_schemas[name] == NO_DATA_OUTPUT_SCHEMA

    for name, property_keys in EXPECTED_OUTPUT_PROPERTY_KEYS.items():
        schema = scoped_schemas[name]
        assert set(schema["properties"]) == property_keys
        assert set(schema["required"]) == property_keys

    order_relation_hints = scoped_schemas["get_order"]["properties"]["relation_hints"]
    assert order_relation_hints["additionalProperties"] is False
    assert set(order_relation_hints["properties"]) == {
        "has_active_refund",
        "latest_refund_case_id",
        "has_open_ticket",
        "latest_ticket_id",
    }
    assert set(order_relation_hints["required"]) == set(order_relation_hints["properties"])

    memory_item_schema = scoped_schemas["search_case_memory"]["properties"]["items"]["items"]
    assert scoped_schemas["search_case_memory"]["required"] == ["items"]
    assert memory_item_schema["additionalProperties"] is False
    assert set(memory_item_schema["properties"]) == {
        "case_memory_id",
        "excerpt",
        "applicability",
        "outcome",
        "caveats",
        "score",
        "policy_refs",
        "source_refs",
    }
    assert set(memory_item_schema["required"]) == set(memory_item_schema["properties"])


def test_query_business_metric_descriptor_is_read_only_and_strict() -> None:
    descriptor = _descriptor("query_business_metric")

    assert descriptor.kind == "read"
    assert descriptor.side_effect == "read_only"
    assert descriptor.required_permission == "tool:query_business_metric"
    assert descriptor.caller_allowlist == ["investigate"]
    assert descriptor.executor == "business"
    assert descriptor.resource_type == "business_metric"
    assert descriptor.input_schema["additionalProperties"] is False
    assert "tenant_id" not in descriptor.input_schema["properties"]
    assert "merchant_scope" not in descriptor.input_schema["properties"]
    assert descriptor.input_schema["properties"]["metric_id"]["enum"] == [
        "order_count",
        "refund_case_count",
        "pending_ticket_count",
        "coupon_record_count",
        "merchant_refund_rate",
    ]
    assert descriptor.output_schema["additionalProperties"] is False
    assert descriptor.output_schema != GENERIC_OBJECT_SCHEMA


def test_business_query_descriptor_is_read_only_strict_and_registry_derived() -> None:
    descriptor = _descriptor("business_query")

    assert descriptor.kind == "read"
    assert descriptor.side_effect == "read_only"
    assert descriptor.required_permission == "tool:business_query"
    assert descriptor.caller_allowlist == ["investigate"]
    assert descriptor.executor == "business"
    assert descriptor.resource_type == "business_query"
    assert descriptor.exposure == "planner_visible"
    assert descriptor.input_schema["additionalProperties"] is False
    assert descriptor.output_schema["additionalProperties"] is False
    assert descriptor.output_schema != GENERIC_OBJECT_SCHEMA

    properties = descriptor.input_schema["properties"]
    assert descriptor.input_schema["required"] == ["operation", "resource"]
    assert set(properties) <= set(BusinessQuerySpec.model_fields)
    assert set(properties["operation"]["enum"]) == BUSINESS_QUERY_REGISTRY.operation_ids()
    assert set(properties["resource"]["enum"]) == BUSINESS_QUERY_REGISTRY.resource_ids()
    assert set(properties["metric_id"]["enum"]) == BUSINESS_QUERY_REGISTRY.metric_ids()
    assert set(properties["time_preset"]["enum"]) == BUSINESS_QUERY_REGISTRY.time_preset_ids()
    assert properties["filters"]["additionalProperties"] is False
    assert properties["cursor"]["type"] == ["object", "null"]
    assert properties["cursor"]["additionalProperties"] is False
    assert set(properties["sort"]["properties"]) == {"field", "direction"}

    for forbidden in ("tenant_id", "merchant_scope", "raw_sql", "where"):
        assert forbidden not in properties


def test_business_query_schema_rejects_authority_sql_and_raw_cursor_fields() -> None:
    schema = _descriptor("business_query").input_schema
    valid_payload = {
        "operation": "aggregate",
        "resource": "order",
        "metric_id": "order_count",
        "time_preset": "this_week",
        "filters": {"status_filter": ["paid"]},
    }

    _validate_json_value(valid_payload, schema)

    for payload in (
        valid_payload | {"tenant_id": "tenant-attacker"},
        valid_payload | {"merchant_scope": {"merchant_ids": ["*"]}},
        valid_payload | {"raw_sql": "select * from orders"},
        valid_payload | {"where": {"tenant_id": "tenant-attacker"}},
        valid_payload | {"filters": {"status_filter": ["paid"], "where": {"status": "paid"}}},
        valid_payload | {"filters": {"status_filter": ["paid"], "arbitrary": {"status": "paid"}}},
        valid_payload | {"cursor": "raw-cursor-token"},
    ):
        with pytest.raises((TypeError, ValueError)):
            _validate_json_value(payload, schema)


def test_business_query_output_schema_matches_result_contract_shape() -> None:
    descriptor = _descriptor("business_query")
    schema = descriptor.output_schema

    assert set(schema["properties"]) == set(BusinessQueryResultV1.model_fields)
    assert set(schema["required"]) == set(BusinessQueryResultV1.model_fields)
    assert set(schema["properties"]["operation"]["enum"]) == BUSINESS_QUERY_REGISTRY.operation_ids()
    assert set(schema["properties"]["resource"]["enum"]) == BUSINESS_QUERY_REGISTRY.resource_ids()
    assert set(schema["properties"]["status"]["enum"]) == {
        "ok",
        "partial",
        "empty",
        "permission_denied",
        "invalid_request",
        "unavailable",
    }
    assert schema["properties"]["rows"]["items"]["type"] == "object"
    assert schema["properties"]["answer_context"]["type"] == ["object", "null"]


def test_query_business_metric_schema_enums_are_registry_derived() -> None:
    source = Path("src/tools/catalog.py").read_text()
    descriptor = _descriptor("query_business_metric")

    assert "BUSINESS_QUERY_REGISTRY" in source
    assert set(descriptor.input_schema["properties"]["metric_id"]["enum"]) == BUSINESS_QUERY_REGISTRY.metric_ids()
    assert set(descriptor.input_schema["properties"]["time_preset"]["enum"]) == BUSINESS_QUERY_REGISTRY.time_preset_ids()
    assert '"order_count",' not in source
    assert '"current_snapshot"],' not in source


def test_action_output_schema_is_strict_after_action_output_hardening() -> None:
    descriptor = _descriptor("create_coupon_grant_draft")

    assert descriptor.output_schema != GENERIC_OBJECT_SCHEMA
    assert descriptor.output_schema["additionalProperties"] is False
    assert set(descriptor.output_schema["properties"]) == {
        "draft_id",
        "idempotency_key",
        "status",
        "created",
        "idempotent_reused",
        "action_draft",
        "draft_outcome",
        "execution_mode",
        "action_result",
    }
    assert set(descriptor.output_schema["required"]) == set(descriptor.output_schema["properties"])
    assert descriptor.kind == "write"
    assert descriptor.exposure == "node_only"


def test_action_output_schema_accepts_current_action_draft_payload() -> None:
    _validate_json_value(_valid_action_output_payload(), _descriptor("create_coupon_grant_draft").output_schema)


def test_action_output_schema_rejects_invalid_action_draft_payloads() -> None:
    unexpected_raw = {**_valid_action_output_payload(), "raw_tool_output": {"secret": "must-not-pass"}}

    missing_required = deepcopy(_valid_action_output_payload())
    del missing_required["action_draft"]["draft_outcome"]  # type: ignore[index]

    nested_raw = deepcopy(_valid_action_output_payload())
    nested_raw["action_result"]["data"]["raw_payload"] = "must-not-pass"  # type: ignore[index]

    for payload in (unexpected_raw, missing_required, nested_raw):
        with pytest.raises((TypeError, ValueError)):
            _validate_json_value(payload, _descriptor("create_coupon_grant_draft").output_schema)


def test_descriptor_table_is_single_source_for_investigate_names_and_resource_types() -> None:
    descriptors = ToolCatalog().descriptors()
    investigate_names = investigate_tool_names(descriptors)

    assert investigate_names
    assert "create_coupon_grant_draft" not in investigate_names
    assert investigate_names == investigate_tool_names()
    assert {descriptor.resource_type for descriptor in descriptors} <= {
        "order",
        "refund_case",
        "ticket",
        "logistics",
        "merchant_risk",
        "business_metric",
        None,
    }


def test_tph01_scoped_output_schema_tool_names_match_registered_tools() -> None:
    descriptors = ToolCatalog().descriptors()
    registered_scoped_names = {
        descriptor.name
        for descriptor in descriptors
        if descriptor.kind in {"read", "retrieval"} and descriptor.exposure == "planner_visible"
    }
    scoped_descriptors = [_descriptor(name) for name in sorted(TPH01_OUTPUT_SCHEMA_TOOL_NAMES)]
    action_descriptor = _descriptor("create_coupon_grant_draft")

    assert registered_scoped_names == TPH01_OUTPUT_SCHEMA_TOOL_NAMES
    assert {descriptor.kind for descriptor in scoped_descriptors} <= {"read", "retrieval"}
    assert all(descriptor.exposure == "planner_visible" for descriptor in scoped_descriptors)
    assert action_descriptor.name not in TPH01_OUTPUT_SCHEMA_TOOL_NAMES
    assert action_descriptor.kind == "write"
    assert action_descriptor.exposure == "node_only"


def test_default_catalog_does_not_register_executable_adapters() -> None:
    catalog = ToolCatalog()

    assert all(tool.adapter is None for tool in catalog._tools.values())


def test_duplicate_descriptor_name_is_rejected() -> None:
    descriptor = _descriptor("get_order")

    with pytest.raises(ValueError, match="Duplicate tool registry entry"):
        ToolCatalog([RegisteredTool(descriptor=descriptor), RegisteredTool(descriptor=descriptor)])


def test_action_descriptor_is_node_only_and_requires_idempotency() -> None:
    descriptor = _descriptor("create_coupon_grant_draft")

    assert descriptor.kind == "write"
    assert descriptor.exposure == "node_only"
    assert descriptor.caller_allowlist == ["action_draft"]
    assert descriptor.requires_idempotency_key is True


def test_search_case_memory_descriptor_names_reviewed_case_memory_store() -> None:
    descriptor = _descriptor("search_case_memory")

    assert "reviewed case memory" in descriptor.description
    assert "reviewed case store" in descriptor.description
    assert "session-derived" not in descriptor.description.lower()


def test_search_case_memory_context_scopes_do_not_require_case_id() -> None:
    assert "case_id" not in ToolCallContext.model_fields
    with pytest.raises(ValidationError):
        ToolCallContext(
            **_context().model_dump(),
            case_id="refund-case-must-not-be-tool-context",
        )

    tenant_id = str(uuid4())
    context = _context().model_copy(
        update={
            "tenant_id": tenant_id,
            "merchant_scope": {"merchant_ids": ["merchant-a", "*"]},
        }
    )

    request = _case_memory_request(query=" reviewed precedent ", context=context)

    assert request is not None
    assert request.tenant_id == UUID(tenant_id)
    assert request.query == "reviewed precedent"
    assert request.query_embedding is None
    assert request.scopes == [
        ("tenant", tenant_id),
        ("user", context.user_id),
        ("thread", context.thread_id),
        ("merchant", "merchant-a"),
    ]


def test_all_descriptor_schemas_use_only_supported_validation_keywords() -> None:
    failures = []
    for descriptor in ToolCatalog().descriptors():
        for schema_name, schema in (
            ("input_schema", descriptor.input_schema),
            ("output_schema", descriptor.output_schema),
        ):
            failures.extend(
                f"{descriptor.name}.{schema_name}:{path}"
                for path in _unsupported_schema_keywords(schema)
            )

    assert failures == []


def test_json_schema_helper_accepts_valid_input() -> None:
    _validate_json_value({"order_no": "ORD-1"}, _descriptor("get_order").input_schema)


@pytest.mark.parametrize(
    ("value", "schema"),
    [
        ({}, _descriptor("get_order").input_schema),
        ({"order_no": ""}, _descriptor("get_order").input_schema),
        ({"order_no": 123}, _descriptor("get_order").input_schema),
    ],
)
def test_json_schema_helper_rejects_invalid_input(value: object, schema: dict) -> None:
    with pytest.raises((TypeError, ValueError)):
        _validate_json_value(value, schema)


def test_json_schema_helper_accepts_nullable_union_and_null() -> None:
    _validate_json_value(None, {"type": "null"})
    _validate_json_value(None, {"type": ["string", "null"]})
    _validate_json_value("x", {"type": ["string", "null"], "minLength": 1})
    _validate_json_value("x", {"type": ["string", "integer"], "minLength": 1})


def test_json_schema_helper_rejects_nullable_union_mismatches() -> None:
    with pytest.raises((TypeError, ValueError)):
        _validate_json_value(123, {"type": ["string", "null"]})
    with pytest.raises((TypeError, ValueError)):
        _validate_json_value("", {"type": ["string", "null"], "minLength": 1})


def test_json_schema_helper_enforces_string_max_length() -> None:
    _validate_json_value("abc", {"type": "string", "maxLength": 3})

    with pytest.raises(ValueError, match="String is too long"):
        _validate_json_value("abcd", {"type": "string", "maxLength": 3})


def test_json_schema_helper_enforces_numeric_bounds() -> None:
    valid_cases = [
        (1, {"type": "integer", "minimum": 1}),
        (10, {"type": "integer", "maximum": 10}),
        (4, {"type": "integer", "exclusiveMaximum": 5}),
        (1.1, {"type": "number", "exclusiveMinimum": 1}),
        (1.5, {"type": "number", "minimum": 1, "maximum": 2}),
    ]
    invalid_cases = [
        (0, {"type": "integer", "minimum": 1}),
        (11, {"type": "integer", "maximum": 10}),
        (5, {"type": "integer", "exclusiveMaximum": 5}),
        (1.0, {"type": "number", "exclusiveMinimum": 1}),
        (2.0, {"type": "number", "exclusiveMaximum": 2}),
    ]

    for value, schema in valid_cases:
        _validate_json_value(value, schema)

    for value, schema in invalid_cases:
        with pytest.raises(ValueError):
            _validate_json_value(value, schema)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_json_schema_helper_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(ValueError, match="Expected finite number"):
        _validate_json_value(value, {"type": "number"})


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("get_order", _valid_order_payload()),
        (
            "get_refund_case",
            {
                "refund_case_no": "REF-1",
                "merchant_id": "merchant-1",
                "status": "requested",
                "reason_code": "late_delivery",
                "reason_text": "Delivery was late",
                "requested_amount": "20.00",
                "approved_amount": None,
            },
        ),
        (
            "get_ticket",
            {
                "ticket_no": "TICKET-1",
                "merchant_id": "merchant-1",
                "status": "open",
                "channel": "chat",
                "summary": "Buyer asks for refund help",
            },
        ),
        (
            "search_policy",
            {
                "retrieval_status": "partial_evidence",
                "best_score": 0.77,
                "threshold": 0.65,
                "summary": None,
            },
        ),
        ("search_case_memory", {"items": [_valid_case_memory_item()]}),
        ("get_logistics", {}),
        ("get_merchant_risk", {}),
        ("search_sop", {}),
    ],
)
def test_output_schema_helper_accepts_current_tool_payloads(name: str, payload: dict[str, object]) -> None:
    _validate_json_value(payload, _descriptor(name).output_schema)


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("get_order", {**_valid_order_payload(), "raw_payload": {"secret": "must-not-pass"}}),
        (
            "get_ticket",
            {
                "ticket_no": "TICKET-1",
                "merchant_id": "merchant-1",
                "status": "open",
                "channel": "chat",
            },
        ),
        (
            "search_policy",
            {
                "retrieval_status": "unsupported_status",
                "best_score": 0.77,
                "threshold": 0.65,
                "summary": None,
            },
        ),
        (
            "search_case_memory",
            {"items": [{**_valid_case_memory_item(), "raw_tool_payload": "must-not-pass"}]},
        ),
        ("get_logistics", {"tracking_no": "TRACK-1"}),
        ("get_merchant_risk", {"merchant_id": "merchant-1"}),
        ("search_sop", {"query": "refund sop"}),
    ],
)
def test_output_schema_helper_rejects_invalid_tool_payloads(name: str, payload: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        _validate_json_value(payload, _descriptor(name).output_schema)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_output_schema_helper_rejects_non_finite_search_policy_best_score(value: float) -> None:
    payload = {
        "retrieval_status": "partial_evidence",
        "best_score": value,
        "threshold": 0.65,
        "summary": None,
    }

    with pytest.raises(ValueError, match="Expected finite number"):
        _validate_json_value(payload, _descriptor("search_policy").output_schema)


@pytest.mark.asyncio
async def test_declaration_only_invoke_fails_closed_without_adapter_execution() -> None:
    adapter = AsyncMock()
    catalog = ToolCatalog([RegisteredTool(descriptor=_descriptor("get_order"), adapter=adapter)])

    result = await catalog.invoke("get_order", {"order_no": "ORD-1"}, _context(), AsyncMock())

    assert result.status == "unavailable"
    assert result.error is not None
    assert result.error.code == "TOOL_REGISTRY_DECLARATION_ONLY"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_tool_returns_not_found_with_integer_latency() -> None:
    result = await ToolCatalog([]).invoke("unknown", {}, _context(), AsyncMock())

    assert result.status == "not_found"
    assert result.data is None
    assert isinstance(result.latency_ms, int)
