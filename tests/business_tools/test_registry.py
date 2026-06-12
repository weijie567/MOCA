from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.business_tools.registry import RegisteredTool, ToolDescriptor, ToolRegistry
from src.business_tools.schemas import ToolCallContext, ToolResultV2


def _context(
    *,
    caller_node: str = "investigate",
    permissions: list[str] | None = None,
) -> ToolCallContext:
    return ToolCallContext(
        tenant_id="tenant-1",
        user_id="user-1",
        role="support_agent",
        permissions=["tool:get_order"] if permissions is None else permissions,
        merchant_scope={"merchant_ids": ["*"]},
        thread_id="thread-1",
        run_id="run-1",
        trace_id="trace-1",
        request_id="request-1",
        tool_call_id="tool-call-1",
        caller_node=caller_node,
    )


def _descriptor(name: str) -> ToolDescriptor:
    return next(descriptor for descriptor in ToolRegistry().descriptors() if descriptor.name == name)


def _registered_tool(
    name: str = "get_order",
    *,
    adapter: AsyncMock | None = None,
    output_schema: dict | None = None,
) -> RegisteredTool:
    descriptor = _descriptor(name)
    if output_schema is not None:
        descriptor = descriptor.model_copy(update={"output_schema": output_schema})
    return RegisteredTool(descriptor=descriptor, adapter=adapter)


def _success_result(data: dict | None = None) -> ToolResultV2:
    return ToolResultV2(
        status="success",
        data={"order_no": "ORD-1"} if data is None else data,
        summary="Order loaded",
        source_system="demo_orders_db",
        data_freshness_at=None,
        latency_ms=1,
        audit_ref=None,
    )


@pytest.mark.asyncio
async def test_unknown_tool_returns_not_found_with_integer_latency() -> None:
    result = await ToolRegistry([]).invoke("unknown", {}, _context(), AsyncMock(spec=AsyncSession))

    assert result.status == "not_found"
    assert result.data is None
    assert isinstance(result.latency_ms, int)


@pytest.mark.asyncio
async def test_write_tool_is_blocked_before_adapter_execution() -> None:
    adapter = AsyncMock(return_value=_success_result())
    registry = ToolRegistry([_registered_tool("create_coupon_grant_draft", adapter=adapter)])

    result = await registry.invoke(
        "create_coupon_grant_draft",
        {"merchant_id": "merchant-1", "amount": 10},
        _context(permissions=["tool:create_coupon_grant_draft"]),
        AsyncMock(spec=AsyncSession),
    )

    assert result.status == "permission_denied"
    assert result.error is not None
    assert result.error.code == "WRITE_TOOL_BLOCKED"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_caller_mismatch_is_denied_before_adapter_execution() -> None:
    adapter = AsyncMock(return_value=_success_result())
    registry = ToolRegistry([_registered_tool(adapter=adapter)])

    result = await registry.invoke("get_order", {"order_no": "ORD-1"}, _context(caller_node="planner"), AsyncMock())

    assert result.status == "permission_denied"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_permission_is_denied_before_adapter_execution() -> None:
    adapter = AsyncMock(return_value=_success_result())
    registry = ToolRegistry([_registered_tool(adapter=adapter)])

    result = await registry.invoke("get_order", {"order_no": "ORD-1"}, _context(permissions=[]), AsyncMock())

    assert result.status == "permission_denied"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_input_returns_invalid_request_before_adapter_execution() -> None:
    adapter = AsyncMock(return_value=_success_result())
    registry = ToolRegistry([_registered_tool(adapter=adapter)])

    result = await registry.invoke("get_order", {}, _context(), AsyncMock())

    assert result.status == "invalid_request"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_call_delegates_once_with_exact_session() -> None:
    adapter = AsyncMock(return_value=_success_result())
    session = AsyncMock(spec=AsyncSession)
    context = _context()
    registry = ToolRegistry([_registered_tool(adapter=adapter)])

    result = await registry.invoke("get_order", {"order_no": "ORD-1"}, context, session)

    assert result.status == "success"
    adapter.assert_awaited_once()
    input_model, called_context, called_session = adapter.await_args.args
    assert input_model.order_no == "ORD-1"
    assert called_context is context
    assert called_session is session


@pytest.mark.asyncio
async def test_adapter_exception_returns_safe_error_without_data() -> None:
    adapter = AsyncMock(side_effect=RuntimeError("RAW-ADAPTER-SECRET"))
    registry = ToolRegistry([_registered_tool(adapter=adapter)])

    result = await registry.invoke("get_order", {"order_no": "ORD-1"}, _context(), AsyncMock())

    assert result.status == "error"
    assert result.data is None
    assert "RAW-ADAPTER-SECRET" not in str(result.model_dump())


@pytest.mark.asyncio
async def test_output_schema_failure_returns_invalid_response_without_raw_data() -> None:
    raw_sentinel = "RAW-REGISTRY-SENTINEL-09"
    adapter = AsyncMock(return_value=_success_result({"unexpected": raw_sentinel}))
    registry = ToolRegistry(
        [
            _registered_tool(
                adapter=adapter,
                output_schema={
                    "type": "object",
                    "properties": {"order_no": {"type": "string"}},
                    "required": ["order_no"],
                    "additionalProperties": False,
                },
            )
        ]
    )

    result = await registry.invoke("get_order", {"order_no": "ORD-1"}, _context(), AsyncMock())

    assert result.status == "invalid_response"
    assert result.data is None
    assert raw_sentinel not in str(result.model_dump())


@pytest.mark.asyncio
async def test_declared_only_tool_returns_unavailable_without_adapter() -> None:
    registry = ToolRegistry([_registered_tool("get_logistics")])

    result = await registry.invoke(
        "get_logistics",
        {"tracking_no": "TRACK-1"},
        _context(permissions=["tool:get_logistics"]),
        AsyncMock(),
    )

    assert result.status == "unavailable"
    assert result.data is None
    assert isinstance(result.latency_ms, int)


def test_descriptor_table_is_single_source_for_investigate_names_and_resource_types() -> None:
    descriptors = ToolRegistry().descriptors()
    investigate_names = {descriptor.name for descriptor in descriptors if "investigate" in descriptor.caller_allowlist}

    assert investigate_names == {
        "get_order",
        "get_refund_case",
        "get_ticket",
        "get_logistics",
        "get_merchant_risk",
        "search_policy",
        "search_sop",
        "search_case_memory",
    }
    assert {descriptor.resource_type for descriptor in descriptors} <= {
        "order",
        "refund_case",
        "ticket",
        "logistics",
        "merchant_risk",
        None,
    }
