from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.tools.get_ticket import get_ticket
from src.db.models import Merchant, Order, Ticket


def _ticket(ticket_no: str = "TK-001"):
    return SimpleNamespace(
        id=uuid4(),
        order_id=uuid4(),
        ticket_no=ticket_no,
        status="open",
        channel="chat",
        summary="用户咨询退款进度",
    )


def _patch_repo(monkeypatch: pytest.MonkeyPatch, *, by_id=None, by_no=None):
    repo = SimpleNamespace(get_by_id=AsyncMock(return_value=by_id), get_by_ticket_no=AsyncMock(return_value=by_no))
    monkeypatch.setattr("src.agent.tools.get_ticket.TicketRepository", lambda session: repo)
    return repo


@pytest.mark.asyncio
async def test_get_ticket_by_ticket_no_success(monkeypatch):
    repo = _patch_repo(monkeypatch, by_no=_ticket("TK-001"))

    result = await get_ticket("TK-001", str(uuid4()), str(uuid4()), "support_agent", AsyncMock())

    assert result["status"] == "success"
    assert result["data"]["ticket_no"] == "TK-001"
    assert "messages" not in result["data"]
    repo.get_by_ticket_no.assert_awaited_once()
    repo.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_ticket_by_uuid_success(monkeypatch):
    ticket_id = uuid4()
    repo = _patch_repo(monkeypatch, by_id=_ticket("TK-UUID"))

    result = await get_ticket(str(ticket_id), str(uuid4()), str(uuid4()), "support_agent", AsyncMock())

    assert result["status"] == "success"
    assert result["data"]["ticket_no"] == "TK-UUID"
    repo.get_by_id.assert_awaited_once()
    repo.get_by_ticket_no.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_ticket_forbids_other_same_tenant_merchant(session: AsyncSession, seeded_session):
    tenant = seeded_session["tenant"]
    merchant_user = seeded_session["users"]["merchant_wang"]
    other_merchant = Merchant(
        id=uuid4(),
        tenant_id=tenant.id,
        merchant_name="Same Tenant Other Shop",
        category="electronics",
        risk_level="low",
    )
    session.add(other_merchant)
    await session.flush()
    other_order = Order(
        id=uuid4(),
        tenant_id=tenant.id,
        merchant_id=other_merchant.id,
        order_no="ORD-TK-SAME-TENANT",
        buyer_name="其他商户用户",
        item_name="键盘",
        amount=Decimal("299.00"),
        currency="CNY",
        status="delivered",
        paid_at=datetime.now(UTC),
        delivered_at=datetime.now(UTC),
    )
    session.add(other_order)
    await session.flush()
    ticket = Ticket(
        id=uuid4(),
        tenant_id=tenant.id,
        order_id=other_order.id,
        ticket_no="TK-SAME-TENANT-OTHER",
        channel="chat",
        status="open",
        summary="其他商户工单",
        messages=[],
    )
    session.add(ticket)
    await session.flush()

    result = await get_ticket(
        "TK-SAME-TENANT-OTHER",
        str(tenant.id),
        str(merchant_user.id),
        "merchant",
        session,
    )

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "FORBIDDEN"
    assert result["error"]["should_stop"] is True
