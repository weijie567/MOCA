from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agent.tools.get_order import get_order


def _order(order_no: str = "ORD-001"):
    return SimpleNamespace(
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
    monkeypatch.setattr("src.agent.tools.get_order.OrderRepository", lambda session: repo)
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

    result = await get_order("ORD-001", str(uuid4()), str(uuid4()), "support_agent", AsyncMock())

    assert result["status"] == "success"
    assert "order_no" in result["data"]


@pytest.mark.asyncio
async def test_get_order_timeout(monkeypatch):
    _patch_repo(monkeypatch, side_effect=asyncio.TimeoutError)

    result = await get_order("ORD-001", str(uuid4()), str(uuid4()), "support_agent", AsyncMock())

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

    result = await get_order("ORD-001", str(uuid4()), str(uuid4()), "support_agent", AsyncMock())

    assert result["status"] == "success"
    assert "messages" not in result["data"]
