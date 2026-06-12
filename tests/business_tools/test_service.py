from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.business_tools.registry import ToolRegistry
from src.business_tools.schemas import ToolCallContext, ToolError, ToolResultV2
from src.business_tools.service import BusinessToolService, _merchant_scope_allows


def _context(**updates: object) -> ToolCallContext:
    values: dict[str, object] = {
        "tenant_id": "tenant-09",
        "user_id": "user-09",
        "role": "support_agent",
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


def _mock_registry(*results: ToolResultV2) -> Mock:
    registry = Mock(spec=ToolRegistry)
    registry.descriptors.return_value = ToolRegistry().descriptors()
    registry.invoke = AsyncMock(side_effect=list(results))
    return registry


@pytest.mark.asyncio
async def test_retry_cap_reuses_stable_tool_call_id_and_session() -> None:
    registry = _mock_registry(
        _result("timeout", data=None, retryable=True, code="DB_TIMEOUT"),
        _result(),
    )
    session = AsyncMock(spec=AsyncSession)
    ctx = _context(max_attempts=2)

    result = await BusinessToolService(registry, session).invoke_tool("get_order", {"order_no": "ORD-09"}, ctx)

    assert result.status == "success"
    assert registry.invoke.call_count == 2
    attempts = [call.args[2].attempt for call in registry.invoke.await_args_list]
    tool_call_ids = [call.args[2].tool_call_id for call in registry.invoke.await_args_list]
    assert attempts == [1, 2]
    assert tool_call_ids == [ctx.tool_call_id, ctx.tool_call_id]
    assert all(call.args[3] is session for call in registry.invoke.await_args_list)


@pytest.mark.asyncio
async def test_attempt_exhausted_does_not_invoke_registry() -> None:
    registry = _mock_registry()

    result = await BusinessToolService(registry, AsyncMock()).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(attempt=3, max_attempts=2),
    )

    assert result.error is not None
    assert result.error.code == "MAX_ATTEMPTS_EXHAUSTED"
    registry.invoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_merchant_scope_denied_before_registry() -> None:
    registry = _mock_registry()

    result = await BusinessToolService(registry, AsyncMock()).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(merchant_scope={}),
    )

    assert result.status == "permission_denied"
    assert result.error is not None
    assert result.error.code == "EMPTY_MERCHANT_SCOPE"
    registry.invoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_required_permission_denied_before_registry() -> None:
    registry = _mock_registry()

    result = await BusinessToolService(registry, AsyncMock()).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(permissions=[]),
    )

    assert result.status == "permission_denied"
    assert result.error is not None
    assert result.error.code == "PERMISSION_REQUIRED"
    registry.invoke.assert_not_awaited()


def test_unknown_category_scope_denied() -> None:
    assert not _merchant_scope_allows(
        {"merchant_ids": ["*"], "categories": ["food"]},
        category="electronics",
    )


def test_merchant_scope_no_widening_denied() -> None:
    assert not _merchant_scope_allows({"merchant_ids": ["merchant-1"]}, merchant_id="merchant-2")


@pytest.mark.asyncio
async def test_real_read_input_does_not_fabricate_merchant_id_or_category() -> None:
    registry = _mock_registry(_result())

    await BusinessToolService(registry, AsyncMock()).invoke_tool("get_order", {"order_no": "ORD-09"}, _context())

    dispatched_args = registry.invoke.await_args.args[1]
    assert dispatched_args == {"order_no": "ORD-09"}
    assert "merchant_id" not in dispatched_args
    assert "category" not in dispatched_args
    # Resource ownership for these reads remains enforced by raw merchant_can_access.


@pytest.mark.asyncio
async def test_fetch_context_mixed_results_is_partial_and_lists_missing_fact() -> None:
    registry = _mock_registry(_result(data={"order_no": "ORD-09"}), _result("not_found", data=None, code="NOT_FOUND"))

    context = await BusinessToolService(registry, AsyncMock()).fetch_context(
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
    registry = _mock_registry(_result(data={"order_no": "ORD-09"}), _result(data={"ticket_no": "T-09"}))

    context = await BusinessToolService(registry, AsyncMock()).fetch_context(
        {"order_id": "ORD-09", "ticket_id": "T-09"},
        "refund_troubleshooting",
        _context(),
    )

    assert context.status == "complete"
    assert set(context.facts) == {"order", "ticket"}
    assert context.missing_required_facts == []


@pytest.mark.asyncio
async def test_fetch_context_no_success_is_insufficient() -> None:
    registry = _mock_registry(_result("not_found", data=None, code="NOT_FOUND"))

    context = await BusinessToolService(registry, AsyncMock()).fetch_context(
        {"refund_case_id": "RF-09"},
        "refund_troubleshooting",
        _context(),
    )

    assert context.status == "insufficient"
    assert context.facts == {}
    assert context.missing_required_facts == ["refund_case"]


@pytest.mark.asyncio
async def test_fetch_context_uses_distinct_tool_call_id_per_logical_read() -> None:
    registry = _mock_registry(_result(), _result(), _result())

    await BusinessToolService(registry, AsyncMock()).fetch_context(
        {"order_id": "ORD-09", "refund_case_id": "RF-09", "ticket_id": "T-09"},
        "refund_troubleshooting",
        _context(),
    )

    tool_call_ids = [call.args[2].tool_call_id for call in registry.invoke.await_args_list]
    assert len(set(tool_call_ids)) == 3


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
    monkeypatch.setattr("src.business_tools.adapters.get_order", raw_get_order)
    session = AsyncMock(spec=AsyncSession)

    result = await BusinessToolService.with_default_registry(session).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(),
    )

    assert result.status == "success"
    assert result.data is not None
    assert result.data["order_no"] == "ORD-09"
    raw_get_order.assert_awaited_once_with("ORD-09", "tenant-09", "user-09", "support_agent", session)
