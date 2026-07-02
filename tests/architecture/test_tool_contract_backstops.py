from __future__ import annotations

import inspect
from typing import Any
from typing import cast

import pytest

from src.business.service import BusinessFactService, NO_LEAK_BUSINESS_RESOURCE_MESSAGE
from src.tools.catalog import ToolCatalog, ToolDescriptor
from src.tools.contracts import ToolCallContext, ToolResultV2
from src.tools.executors.business import BusinessToolExecutor
from src.tools.policy import _DOMAIN_SCOPE_CHECK_IDENTIFIERS


def _ctx(*, merchant_scope: dict[str, Any] | None = None) -> ToolCallContext:
    return ToolCallContext(
        tenant_id="tenant-1",
        user_id="user-1",
        role="support",
        permissions=["tool:get_order"],
        merchant_scope={"merchant_ids": ["merchant-1"]} if merchant_scope is None else merchant_scope,
        session_id=None,
        thread_id="thread-1",
        run_id="run-1",
        trace_id="trace-1",
        request_id="request-1",
        tool_call_id="tool-call-1",
        caller_node="investigate",
    )


def _domain_scope_identifiers(descriptor: ToolDescriptor) -> set[str]:
    properties = descriptor.input_schema.get("properties", {})
    return set(properties) & _DOMAIN_SCOPE_CHECK_IDENTIFIERS


def _tool_result() -> ToolResultV2:
    return ToolResultV2(
        status="success",
        data={},
        summary="ok",
        source_system="fake_business_tool_service",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=0,
        audit_ref=None,
    )


def test_domain_scope_marker_tools_route_through_business_fact_boundary() -> None:
    marker_tools = {
        descriptor.name: {
            "identifiers": _domain_scope_identifiers(descriptor),
            "kind": descriptor.kind,
            "executor": descriptor.executor,
            "resource_type": descriptor.resource_type,
            "caller_allowlist": descriptor.caller_allowlist,
        }
        for descriptor in ToolCatalog().descriptors()
        if _domain_scope_identifiers(descriptor)
    }

    assert marker_tools == {
        "get_order": {
            "identifiers": {"order_no"},
            "kind": "read",
            "executor": "business",
            "resource_type": "order",
            "caller_allowlist": ["investigate"],
        },
        "get_refund_case": {
            "identifiers": {"refund_case_no"},
            "kind": "read",
            "executor": "business",
            "resource_type": "refund_case",
            "caller_allowlist": ["investigate"],
        },
        "get_ticket": {
            "identifiers": {"ticket_id"},
            "kind": "read",
            "executor": "business",
            "resource_type": "ticket",
            "caller_allowlist": ["investigate"],
        },
    }


@pytest.mark.asyncio
async def test_business_tool_executor_delegates_to_business_tool_service_boundary() -> None:
    class FakeBusinessToolService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, Any], ToolCallContext]] = []

        def has_tool(self, name: str) -> bool:
            return name == "get_order"

        async def invoke_tool(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
            self.calls.append((name, args, ctx))
            return _tool_result()

    service = FakeBusinessToolService()
    executor = BusinessToolExecutor(session=object(), service=cast(Any, service))

    result = await executor.execute("get_order", {"order_no": "ORD-1"}, _ctx())

    assert result.status == "success"
    assert len(service.calls) == 1
    assert service.calls[0][0] == "get_order"
    assert service.calls[0][1] == {"order_no": "ORD-1"}

    source = inspect.getsource(BusinessToolExecutor)
    assert "invoke_tool" in source
    for forbidden in ("src.repositories", "OrderRepository", "RefundRepository", "TicketRepository"):
        assert forbidden not in source


@pytest.mark.asyncio
async def test_business_fact_service_denies_invalid_scope_before_adapter() -> None:
    calls = []

    async def adapter(input_model: Any, ctx: ToolCallContext, session: Any) -> ToolResultV2:
        calls.append((input_model, ctx, session))
        return _tool_result()

    service = BusinessFactService(session=object(), adapters={"get_order": adapter})

    result = await service.get_order("ORD-SECRET-001", _ctx(merchant_scope={"merchant_ids": []}))

    assert result.status == "permission_denied"
    assert result.scope_check_result == "denied"
    assert result.fact is None
    assert result.business_fact_refs == []
    assert result.safe_errors
    assert result.safe_errors[0].code == "BUSINESS_FACT_PERMISSION_DENIED"
    assert result.safe_errors[0].safe_message == NO_LEAK_BUSINESS_RESOURCE_MESSAGE
    assert calls == []
    assert "ORD-SECRET-001" not in result.model_dump_json()
