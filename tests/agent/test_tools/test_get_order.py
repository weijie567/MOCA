from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Merchant, Order
from src.integrations.demo_business.orders import get_order


def _order(order_no: str = "ORD-001"):
    return SimpleNamespace(
        merchant_id=uuid4(),
        order_no=order_no,
        status="delivered",
        amount=Decimal("199.00"),
        currency="CNY",
        buyer_name="测试用户",
        item_name="蓝牙耳机",
        paid_at=datetime.now(UTC),
        delivered_at=datetime.now(UTC),
    )


def _patch_repo(monkeypatch: pytest.MonkeyPatch, result=None, side_effect=None):
    repo = SimpleNamespace(get_with_hints=AsyncMock(return_value=result, side_effect=side_effect))
    monkeypatch.setattr("src.integrations.demo_business.orders.OrderRepository", lambda session: repo)
    return repo


@pytest.mark.asyncio
async def test_get_order_not_found(monkeypatch):
    _patch_repo(monkeypatch, result=None)

    result = await get_order("ORD-MISSING", str(uuid4()), str(uuid4()), "support_agent", AsyncMock())

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "ORDER_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_order_success(monkeypatch):
    _patch_repo(
        monkeypatch,
        result={
            "order": _order(),
            "relation_hints": {
                "has_active_refund": True,
                "latest_refund_case_id": uuid4(),
                "has_open_ticket": False,
                "latest_ticket_id": None,
            },
        },
    )

    result = await get_order("ORD-001", str(uuid4()), str(uuid4()), "admin", AsyncMock())

    assert result["status"] == "success"
    assert "order_no" in result["data"]


@pytest.mark.asyncio
async def test_get_order_timeout(monkeypatch):
    _patch_repo(monkeypatch, side_effect=asyncio.TimeoutError)

    result = await get_order("ORD-001", str(uuid4()), str(uuid4()), "admin", AsyncMock())

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "DB_TIMEOUT"
    assert result["error"]["retryable"] is True


@pytest.mark.asyncio
async def test_get_order_no_messages_field(monkeypatch):
    _patch_repo(
        monkeypatch,
        result={
            "order": _order(),
            "relation_hints": {
                "has_active_refund": False,
                "latest_refund_case_id": None,
                "has_open_ticket": False,
                "latest_ticket_id": None,
            },
        },
    )

    result = await get_order("ORD-001", str(uuid4()), str(uuid4()), "admin", AsyncMock())

    assert result["status"] == "success"
    assert "messages" not in result["data"]


@pytest.mark.asyncio
async def test_get_order_forbids_other_same_tenant_merchant(session: AsyncSession, seeded_session):
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
        order_no="ORD-SAME-TENANT-OTHER",
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

    result = await get_order(
        "ORD-SAME-TENANT-OTHER",
        str(tenant.id),
        str(merchant_user.id),
        "merchant",
        session,
    )

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "FORBIDDEN"
    assert result["error"]["should_stop"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("user_key", ["cs_zhang", "approval_manager", "merchant_wang"])
async def test_get_order_allows_same_merchant_business_users(session: AsyncSession, seeded_session, user_key):
    tenant = seeded_session["tenant"]
    user = seeded_session["users"][user_key]

    result = await get_order("ORD-TEST-001", str(tenant.id), str(user.id), user.role, session)

    assert result["status"] == "success"
    assert result["data"]["order_no"] == "ORD-TEST-001"


@pytest.mark.asyncio
@pytest.mark.parametrize("user_key", ["cs_zhang", "approval_manager", "merchant_wang"])
async def test_get_order_denies_other_same_tenant_merchant_for_business_users(
    session: AsyncSession, seeded_session, user_key
):
    tenant = seeded_session["tenant"]
    user = seeded_session["users"][user_key]

    result = await get_order("ORD-TEST-002", str(tenant.id), str(user.id), user.role, session)

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "FORBIDDEN"
    assert result["error"]["should_stop"] is True


@pytest.mark.asyncio
async def test_get_order_allows_admin_other_same_tenant_merchant(session: AsyncSession, seeded_session):
    tenant = seeded_session["tenant"]
    admin = seeded_session["users"]["admin_user"]

    result = await get_order("ORD-TEST-002", str(tenant.id), str(admin.id), admin.role, session)

    assert result["status"] == "success"
    assert result["data"]["order_no"] == "ORD-TEST-002"


@pytest.mark.asyncio
async def test_get_order_denies_merchant_bound_user_missing_merchant_id(session: AsyncSession, seeded_session):
    tenant = seeded_session["tenant"]
    support = seeded_session["users"]["cs_zhang"]
    support.merchant_id = None
    await session.flush()

    result = await get_order("ORD-TEST-001", str(tenant.id), str(support.id), support.role, session)

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "FORBIDDEN"
    assert result["error"]["should_stop"] is True


@pytest.mark.asyncio
async def test_get_order_denies_unknown_role(session: AsyncSession, seeded_session):
    tenant = seeded_session["tenant"]
    support = seeded_session["users"]["cs_zhang"]

    result = await get_order("ORD-TEST-001", str(tenant.id), str(support.id), "auditor", session)

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "FORBIDDEN"
    assert result["error"]["should_stop"] is True
