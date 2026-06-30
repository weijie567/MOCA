from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.business.adapters import (
    GetOrderInput,
    GetRefundCaseInput,
    GetTicketInput,
    get_order_adapter,
    get_refund_case_adapter,
    get_ticket_adapter,
)
from src.tools.contracts import ToolCallContext


def _context() -> ToolCallContext:
    return ToolCallContext(
        tenant_id="tenant-09",
        user_id="user-09",
        role="support_agent",
        permissions=["tool:get_order", "tool:get_refund_case", "tool:get_ticket"],
        merchant_scope={"merchant_ids": ["*"]},
        thread_id="thread-09",
        run_id="run-09",
        trace_id="trace-09",
        request_id="request-09",
        tool_call_id="tool-call-09",
        caller_node="investigate",
    )


def _order_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "order_no": "ORD-09",
        "merchant_id": "merchant-09",
        "status": "paid",
        "amount": "88.00",
        "currency": "CNY",
        "buyer_name": "Demo Buyer",
        "item_name": "Demo Item",
        "paid_at": "2026-06-12T10:00:00+00:00",
        "delivered_at": None,
        "relation_hints": {
            "has_active_refund": False,
            "latest_refund_case_id": None,
            "has_open_ticket": False,
            "latest_ticket_id": None,
        },
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_code", "expected_status", "expected_source", "retryable"),
    [
        ("FORBIDDEN", "permission_denied", "caller", False),
        ("ORDER_NOT_FOUND", "not_found", "upstream", False),
        ("DB_TIMEOUT", "timeout", "adapter", True),
        ("VALIDATION_ERROR", "invalid_request", "caller", False),
        ("DB_ERROR", "error", "adapter", False),
    ],
)
async def test_raw_error_code_maps_deterministically(
    monkeypatch: pytest.MonkeyPatch,
    error_code: str,
    expected_status: str,
    expected_source: str,
    retryable: bool,
) -> None:
    raw_tool = AsyncMock(
        return_value={
            "status": "error",
            "data": {},
            "error": {"error_code": error_code, "message": "unsafe raw message", "retryable": retryable},
        }
    )
    monkeypatch.setattr("src.business.adapters.get_order", raw_tool)

    result = await get_order_adapter(GetOrderInput(order_no="ORD-09"), _context(), AsyncMock())

    assert result.status == expected_status
    assert result.error is not None
    assert result.error.source == expected_source
    assert result.retryable is retryable
    assert isinstance(result.latency_ms, int)
    assert "unsafe raw message" not in str(result.model_dump())


@pytest.mark.asyncio
async def test_invalid_response_discards_raw_upstream_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_tool = AsyncMock(
        return_value={
            "status": "success",
            "data": {"order_no": "ORD-09", "secret": "RAW-UPSTREAM-SECRET-09"},
            "error": {},
        }
    )
    monkeypatch.setattr("src.business.adapters.get_order", raw_tool)

    result = await get_order_adapter(GetOrderInput(order_no="ORD-09"), _context(), AsyncMock())

    assert result.status == "invalid_response"
    assert result.data is None
    assert "RAW-UPSTREAM-SECRET-09" not in str(result.model_dump())
    assert isinstance(result.latency_ms, int)


@pytest.mark.asyncio
async def test_order_success_projects_data_and_business_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_tool = AsyncMock(return_value={"status": "success", "data": _order_data(), "error": {}})
    monkeypatch.setattr("src.business.adapters.get_order", raw_tool)
    ctx = _context()
    session = AsyncMock()

    result = await get_order_adapter(GetOrderInput(order_no="ORD-09"), ctx, session)

    assert result.status == "success"
    assert result.data == _order_data()
    assert result.policy_evidence_refs == []
    assert len(result.business_fact_refs) == 1
    assert result.business_fact_refs[0].resource_type == "order"
    assert result.business_fact_refs[0].resource_id == "ORD-09"
    assert result.business_fact_refs[0].tenant_id == ctx.tenant_id
    assert isinstance(result.latency_ms, int)
    raw_tool.assert_awaited_once_with("ORD-09", ctx.tenant_id, ctx.user_id, ctx.role, session)


@pytest.mark.asyncio
async def test_refund_success_uses_refund_business_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_tool = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "refund_case_no": "RF-09",
                "merchant_id": "merchant-09",
                "status": "open",
                "reason_code": "DAMAGED",
                "reason_text": "Item damaged",
                "requested_amount": "88.00",
                "approved_amount": None,
            },
            "error": {},
        }
    )
    monkeypatch.setattr("src.business.adapters.get_refund_case", raw_tool)

    result = await get_refund_case_adapter(GetRefundCaseInput(refund_case_no="RF-09"), _context(), AsyncMock())

    assert result.status == "success"
    assert result.policy_evidence_refs == []
    assert result.business_fact_refs[0].resource_type == "refund_case"
    assert result.business_fact_refs[0].resource_id == "RF-09"
    assert isinstance(result.latency_ms, int)


@pytest.mark.asyncio
async def test_ticket_success_uses_ticket_business_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_tool = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "ticket_no": "T-09",
                "merchant_id": "merchant-09",
                "status": "open",
                "channel": "chat",
                "summary": "Refund question",
            },
            "error": {},
        }
    )
    monkeypatch.setattr("src.business.adapters.get_ticket", raw_tool)

    result = await get_ticket_adapter(GetTicketInput(ticket_id="T-09"), _context(), AsyncMock())

    assert result.status == "success"
    assert result.policy_evidence_refs == []
    assert result.business_fact_refs[0].resource_type == "ticket"
    assert result.business_fact_refs[0].resource_id == "T-09"
    assert isinstance(result.latency_ms, int)
