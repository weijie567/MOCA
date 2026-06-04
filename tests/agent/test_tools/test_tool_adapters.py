from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agent.tools.contracts import ToolInvocationContext
from src.agent.tools.adapters import (
    GetOrderInput,
    GetRefundCaseInput,
    GetTicketInput,
    SearchPolicyInput,
    get_order_adapter,
    get_refund_case_adapter,
    get_ticket_adapter,
    search_policy_adapter,
)


def _context() -> ToolInvocationContext:
    return ToolInvocationContext(
        tenant_id="tenant-1",
        user_id="user-1",
        role="support_agent",
        session=object(),
        caller="investigator",
    )


@pytest.mark.asyncio
async def test_get_order_adapter_forwards_context_and_order_no(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = AsyncMock(return_value={"status": "success", "data": {"order_no": "ORD-001"}, "error": {}})
    monkeypatch.setattr("src.agent.tools.adapters.get_order", tool)
    context = _context()

    result = await get_order_adapter(GetOrderInput(order_no="ORD-001"), context)

    assert result["status"] == "success"
    tool.assert_awaited_once_with("ORD-001", context.tenant_id, context.user_id, context.role, context.session)


@pytest.mark.asyncio
async def test_get_refund_case_adapter_forwards_context_and_case_no(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = AsyncMock(return_value={"status": "success", "data": {"refund_case_no": "RF-001"}, "error": {}})
    monkeypatch.setattr("src.agent.tools.adapters.get_refund_case", tool)
    context = _context()

    result = await get_refund_case_adapter(GetRefundCaseInput(refund_case_no="RF-001"), context)

    assert result["status"] == "success"
    tool.assert_awaited_once_with("RF-001", context.tenant_id, context.user_id, context.role, context.session)


@pytest.mark.asyncio
async def test_get_ticket_adapter_forwards_context_and_ticket_id(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = AsyncMock(return_value={"status": "success", "data": {"ticket_no": "T-001"}, "error": {}})
    monkeypatch.setattr("src.agent.tools.adapters.get_ticket", tool)
    context = _context()

    result = await get_ticket_adapter(GetTicketInput(ticket_id="T-001"), context)

    assert result["status"] == "success"
    tool.assert_awaited_once_with("T-001", context.tenant_id, context.user_id, context.role, context.session)


@pytest.mark.asyncio
async def test_search_policy_adapter_forwards_context_and_search_options(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = AsyncMock(return_value={"status": "success", "data": {"retrieval_status": "hit"}, "error": {}})
    monkeypatch.setattr("src.agent.tools.adapters.search_policy", tool)
    context = _context()

    result = await search_policy_adapter(
        SearchPolicyInput(query="refund rule", top_k=3, doc_type="refund", risk_level="medium"),
        context,
    )

    assert result["status"] == "success"
    tool.assert_awaited_once_with(
        "refund rule",
        context.tenant_id,
        context.user_id,
        context.role,
        context.session,
        top_k=3,
        doc_type="refund",
        risk_level="medium",
    )
