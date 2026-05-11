from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Merchant, Order, RefundCase
from src.agent.tools.get_refund_case import get_refund_case


def _patch_repo(monkeypatch: pytest.MonkeyPatch, result=None):
    repo = SimpleNamespace(get_by_case_no=AsyncMock(return_value=result))
    monkeypatch.setattr("src.agent.tools.get_refund_case.RefundRepository", lambda session: repo)
    return repo


@pytest.mark.asyncio
async def test_get_refund_case_not_found(monkeypatch):
    _patch_repo(monkeypatch, result=None)

    result = await get_refund_case("RF-MISSING", str(uuid4()), str(uuid4()), "support_agent", AsyncMock())

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "REFUND_CASE_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_refund_case_success(monkeypatch):
    refund_case = SimpleNamespace(
        order_id=uuid4(),
        refund_case_no="RF-001",
        status="reviewing",
        reason_code="timeout",
        reason_text="退款超时",
        requested_amount=Decimal("199.00"),
        approved_amount=None,
    )
    _patch_repo(monkeypatch, result=refund_case)

    result = await get_refund_case("RF-001", str(uuid4()), str(uuid4()), "support_agent", AsyncMock())

    assert result["status"] == "success"
    assert "refund_case_no" in result["data"]


@pytest.mark.asyncio
async def test_get_refund_case_forbids_other_same_tenant_merchant(session: AsyncSession, seeded_session):
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
        order_no="ORD-RF-SAME-TENANT",
        buyer_name="其他商户用户",
        item_name="键盘",
        amount=Decimal("299.00"),
        currency="CNY",
        status="delivered",
    )
    session.add(other_order)
    await session.flush()
    refund_case = RefundCase(
        id=uuid4(),
        tenant_id=tenant.id,
        order_id=other_order.id,
        refund_case_no="RF-SAME-TENANT-OTHER",
        reason_code="timeout",
        reason_text="退款超时",
        status="reviewing",
        requested_amount=Decimal("299.00"),
    )
    session.add(refund_case)
    await session.flush()

    result = await get_refund_case(
        "RF-SAME-TENANT-OTHER",
        str(tenant.id),
        str(merchant_user.id),
        "merchant",
        session,
    )

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "FORBIDDEN"
    assert result["error"]["should_stop"] is True
