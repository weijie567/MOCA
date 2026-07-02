from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.tools.catalog import _IDENTIFIER_SCHEMAS, RegisteredTool, ToolCatalog, ToolDescriptor
from src.tools.contracts import ToolCallContext
from src.tools.validation import _validate_json_value


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


def _catalog_investigate_tool_names() -> frozenset[str]:
    return frozenset(
        descriptor.name
        for descriptor in ToolCatalog().descriptors()
        if "investigate" in descriptor.caller_allowlist
        and descriptor.kind != "write"
        and descriptor.exposure == "planner_visible"
    )


def test_catalog_registry_derives_identifier_schemas_without_drift() -> None:
    descriptors = ToolCatalog().descriptors()

    assert _IDENTIFIER_SCHEMAS == {descriptor.name: descriptor.input_schema for descriptor in descriptors}
    assert all(descriptor.output_schema == {"type": "object"} for descriptor in descriptors)


def test_descriptor_table_is_single_source_for_investigate_names_and_resource_types() -> None:
    descriptors = ToolCatalog().descriptors()
    investigate_names = _catalog_investigate_tool_names()

    assert investigate_names
    assert "create_coupon_grant_draft" not in investigate_names
    assert investigate_names == {
        descriptor.name
        for descriptor in descriptors
        if "investigate" in descriptor.caller_allowlist
        and descriptor.kind != "write"
        and descriptor.exposure == "planner_visible"
    }
    assert {descriptor.resource_type for descriptor in descriptors} <= {
        "order",
        "refund_case",
        "ticket",
        "logistics",
        "merchant_risk",
        None,
    }


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
