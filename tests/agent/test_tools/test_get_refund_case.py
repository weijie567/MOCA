from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

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
