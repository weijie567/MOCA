from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.investigate import _project_tool_result
from src.business.service import (
    BUSINESS_READ_TOOLS,
    BusinessReadToolDefinition,
    BusinessToolService,
    _merchant_scope_allows,
)
from src.integrations.demo_business.authz import merchant_can_access
from src.tools.contracts import ToolCallContext, ToolError, ToolResultV2
from src.tools.executors.business import BusinessToolExecutor


def _context(**updates: object) -> ToolCallContext:
    values: dict[str, object] = {
        "tenant_id": "tenant-09",
        "user_id": "user-09",
        "role": "support",
        "permissions": ["tool:get_order", "tool:get_refund_case", "tool:get_ticket"],
        "merchant_scope": {"merchant_ids": ["*"]},
        "thread_id": "thread-09",
        "run_id": "run-09",
        "trace_id": "trace-09",
        "request_id": "request-09",
        "tool_call_id": "tool-call-09",
        "caller_node": "investigate",
    }
    values.update(updates)
    return ToolCallContext.model_validate(values)


def _result(
    status: str = "success",
    *,
    data: dict | None = None,
    retryable: bool = False,
    code: str | None = None,
) -> ToolResultV2:
    error = None
    if code is not None:
        error = ToolError(code=code, safe_message=f"Safe {code}", retryable=retryable, source="adapter")
    return ToolResultV2(
        status=status,
        data={"id": "resource-09"} if status == "success" and data is None else data,
        summary=f"{status} result",
        source_system="test_business_db",
        data_freshness_at=None,
        error=error,
        retryable=retryable,
        latency_ms=1,
        audit_ref=None,
    )


@pytest.mark.asyncio
async def test_retry_cap_reuses_stable_tool_call_id_and_session() -> None:
    adapter = AsyncMock(
        side_effect=[
            _result("timeout", data=None, retryable=True, code="DB_TIMEOUT"),
            _result(),
        ]
    )
    session = AsyncMock(spec=AsyncSession)
    ctx = _context(max_attempts=2)

    result = await BusinessToolService(session, adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        ctx,
    )

    assert result.status == "success"
    assert adapter.call_count == 2
    attempts = [call.args[1].attempt for call in adapter.await_args_list]
    tool_call_ids = [call.args[1].tool_call_id for call in adapter.await_args_list]
    assert attempts == [1, 2]
    assert tool_call_ids == [ctx.tool_call_id, ctx.tool_call_id]
    assert all(call.args[2] is session for call in adapter.await_args_list)


@pytest.mark.asyncio
async def test_attempt_exhausted_does_not_invoke_adapter() -> None:
    adapter = AsyncMock(return_value=_result())

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(attempt=3, max_attempts=2),
    )

    assert result.error is not None
    assert result.error.code == "MAX_ATTEMPTS_EXHAUSTED"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_merchant_scope_denied_before_adapter() -> None:
    adapter = AsyncMock(return_value=_result())

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(merchant_scope={}),
    )

    assert result.status == "permission_denied"
    assert result.error is not None
    assert result.error.code == "EMPTY_MERCHANT_SCOPE"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_does_not_repeat_permission_check() -> None:
    adapter = AsyncMock(return_value=_result())

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(permissions=[]),
    )

    assert result.status == "success"
    adapter.assert_awaited_once()


def test_unknown_category_scope_denied() -> None:
    assert not _merchant_scope_allows(
        {"merchant_ids": ["*"], "categories": ["food"]},
        category="electronics",
    )


def test_merchant_scope_no_widening_denied() -> None:
    assert not _merchant_scope_allows({"merchant_ids": ["merchant-1"]}, merchant_id="merchant-2")


@pytest.mark.asyncio
async def test_merchant_can_access_rejects_forged_admin_context(session: AsyncSession, seeded_session) -> None:
    tenant = seeded_session["tenant"]
    user = seeded_session["users"]["cs_zhang"]
    merchant = seeded_session["second_merchant"]

    assert not await merchant_can_access(
        session,
        tenant_id=tenant.id,
        user_id="not-a-uuid",
        role="admin",
        merchant_id=merchant.id,
    )
    assert not await merchant_can_access(
        session,
        tenant_id=tenant.id,
        user_id=str(user.id),
        role="admin",
        merchant_id=merchant.id,
    )


def test_business_read_tool_definitions_drive_executor_support() -> None:
    service = BusinessToolService(AsyncMock())
    executor = BusinessToolExecutor(AsyncMock(), service=service)

    assert {name for name in BUSINESS_READ_TOOLS if executor.has_tool(name)} == set(BUSINESS_READ_TOOLS)


@pytest.mark.asyncio
async def test_custom_business_read_definition_drives_invoke_and_fetch_context() -> None:
    class DemoInput(BaseModel):
        demo_no: str

    adapter = AsyncMock(return_value=_result(data={"demo_no": "DEMO-09"}))
    service = BusinessToolService(
        AsyncMock(),
        tools={
            "get_demo": BusinessReadToolDefinition(
                input_model=DemoInput,
                adapter=adapter,
                slot_name="demo_id",
                resource_name="demo",
                argument_name="demo_no",
            )
        },
    )

    assert service.has_tool("get_demo")
    assert BusinessToolExecutor(AsyncMock(), service=service).has_tool("get_demo")

    result = await service.invoke_tool("get_demo", {"demo_no": "DEMO-09"}, _context())
    context = await service.fetch_context({"demo_id": "DEMO-09"}, "refund_troubleshooting", _context())

    assert result.status == "success"
    assert context.facts == {"demo": {"demo_no": "DEMO-09"}}
    assert adapter.await_count == 2


@pytest.mark.asyncio
async def test_real_read_input_does_not_fabricate_merchant_id_or_category() -> None:
    adapter = AsyncMock(return_value=_result())

    await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(),
    )

    dispatched_input = adapter.await_args.args[0]
    assert dispatched_input.model_dump() == {"order_no": "ORD-09"}
    assert not hasattr(dispatched_input, "merchant_id")
    assert not hasattr(dispatched_input, "category")
    # Resource ownership for these reads remains enforced by raw merchant_can_access.


@pytest.mark.asyncio
async def test_fetch_context_mixed_results_is_partial_and_lists_missing_fact() -> None:
    adapters = {
        "get_order": AsyncMock(return_value=_result(data={"order_no": "ORD-09"})),
        "get_ticket": AsyncMock(return_value=_result("not_found", data=None, code="NOT_FOUND")),
    }

    context = await BusinessToolService(AsyncMock(), adapters=adapters).fetch_context(
        {"order_id": "ORD-09", "ticket_id": "T-09"},
        "refund_troubleshooting",
        _context(),
    )

    assert context.status == "partial"
    assert context.facts == {"order": {"order_no": "ORD-09"}}
    assert context.missing_required_facts == ["ticket"]
    assert context.errors[0].code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_fetch_context_all_success_is_complete() -> None:
    adapters = {
        "get_order": AsyncMock(return_value=_result(data={"order_no": "ORD-09"})),
        "get_refund_case": AsyncMock(return_value=_result(data={"refund_case_no": "RF-09"})),
        "get_ticket": AsyncMock(return_value=_result(data={"ticket_no": "T-09"})),
    }

    context = await BusinessToolService(AsyncMock(), adapters=adapters).fetch_context(
        {"order_id": "ORD-09", "refund_case_id": "RF-09", "ticket_id": "T-09"},
        "refund_troubleshooting",
        _context(),
    )

    assert context.status == "complete"
    assert set(context.facts) == {"order", "refund_case", "ticket"}
    assert context.missing_required_facts == []
    assert all(adapter.await_count == 1 for adapter in adapters.values())


@pytest.mark.asyncio
async def test_fetch_context_no_success_is_insufficient() -> None:
    adapters = {"get_refund_case": AsyncMock(return_value=_result("not_found", data=None, code="NOT_FOUND"))}

    context = await BusinessToolService(AsyncMock(), adapters=adapters).fetch_context(
        {"refund_case_id": "RF-09"},
        "refund_troubleshooting",
        _context(),
    )

    assert context.status == "insufficient"
    assert context.facts == {}
    assert context.missing_required_facts == ["refund_case"]


@pytest.mark.asyncio
async def test_fetch_context_uses_distinct_tool_call_id_per_logical_read() -> None:
    adapters = {
        "get_order": AsyncMock(return_value=_result()),
        "get_refund_case": AsyncMock(return_value=_result()),
        "get_ticket": AsyncMock(return_value=_result()),
    }

    await BusinessToolService(AsyncMock(), adapters=adapters).fetch_context(
        {"order_id": "ORD-09", "refund_case_id": "RF-09", "ticket_id": "T-09"},
        "refund_troubleshooting",
        _context(),
    )

    tool_call_ids = [call.args[1].tool_call_id for adapter in adapters.values() for call in adapter.await_args_list]
    assert len(set(tool_call_ids)) == 3


@pytest.mark.asyncio
async def test_fetch_context_cross_merchant_permission_denied_has_no_business_facts(
    session: AsyncSession, seeded_session
) -> None:
    tenant = seeded_session["tenant"]
    user = seeded_session["users"]["cs_zhang"]
    merchant = seeded_session["merchant"]

    context = await BusinessToolService.with_default_registry(session).fetch_context(
        {"order_id": "ORD-TEST-002"},
        "refund_troubleshooting",
        _context(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            role=user.role,
            merchant_scope={"merchant_ids": [str(merchant.id)]},
        ),
    )

    assert context.status == "insufficient"
    assert context.facts == {}
    assert context.business_fact_refs == []
    assert context.missing_required_facts == ["order"]
    assert len(context.tool_results) == 1
    denied_result = context.tool_results[0]
    assert denied_result.status == "permission_denied"
    assert denied_result.business_fact_refs == []
    assert denied_result.data is None
    assert denied_result.error is not None
    assert denied_result.error.code == "FORBIDDEN"
    prompt_summary = _project_tool_result(
        tool_call_id="tool-call-denied",
        tool_result_id="tool-result-denied",
        tool_name="get_order",
        result=denied_result,
        raw_result_ref=None,
    )
    assert prompt_summary.business_fact_refs == []
    assert "ORD-TEST-002" not in prompt_summary.prompt_summary
    assert "Order read succeeded" not in prompt_summary.prompt_summary
    serialized_context = context.model_dump_json()
    assert "ORD-TEST-002" not in serialized_context
    assert "Order read succeeded" not in serialized_context


@pytest.mark.asyncio
async def test_adapter_exception_returns_safe_tool_result() -> None:
    adapter = AsyncMock(side_effect=RuntimeError("RAW-SERVICE-SECRET"))

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(),
    )

    assert result.status == "error"
    assert result.data is None
    assert result.error is not None
    assert result.error.code == "ADAPTER_ERROR"
    assert "RAW-SERVICE-SECRET" not in str(result.model_dump())


@pytest.mark.asyncio
async def test_with_default_registry_invokes_real_adapter_with_mocked_raw_get_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_get_order = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "order_no": "ORD-09",
                "status": "paid",
                "amount": "88.00",
                "currency": "CNY",
                "buyer_name": "Demo Buyer",
                "item_name": "Demo Item",
                "paid_at": None,
                "delivered_at": None,
                "relation_hints": {
                    "has_active_refund": False,
                    "latest_refund_case_id": None,
                    "has_open_ticket": False,
                    "latest_ticket_id": None,
                },
            },
            "error": {},
        }
    )
    monkeypatch.setattr("src.business.adapters.get_order", raw_get_order)
    session = AsyncMock(spec=AsyncSession)

    result = await BusinessToolService.with_default_registry(session).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(),
    )

    assert result.status == "success"
    assert result.data is not None
    assert result.data["order_no"] == "ORD-09"
    raw_get_order.assert_awaited_once_with("ORD-09", "tenant-09", "user-09", "support", session)
