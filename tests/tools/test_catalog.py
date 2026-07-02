from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.tools.catalog import _IDENTIFIER_SCHEMAS, RegisteredTool, ToolCatalog, ToolDescriptor, investigate_tool_names
from src.tools.contracts import ToolCallContext
from src.tools.validation import _validate_json_value


TPH01_OUTPUT_SCHEMA_TOOL_NAMES = frozenset(
    {
        "get_order",
        "get_refund_case",
        "get_ticket",
        "get_logistics",
        "get_merchant_risk",
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


def test_action_output_schema_remains_generic_until_action_output_hardening() -> None:
    descriptor = _descriptor("create_coupon_grant_draft")

    assert descriptor.output_schema == GENERIC_OBJECT_SCHEMA
    assert descriptor.kind == "write"
    assert descriptor.exposure == "node_only"


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
