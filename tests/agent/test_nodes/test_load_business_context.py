from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agent.nodes.load_business_context import load_business_context
from src.api.routers.agent_runs import _trusted_tool_config
from src.business_tools.schemas import BusinessContextV1, ToolError, ToolResultV2
from src.business_tools.service import BusinessToolService
from src.db.models import User


def _state(**updates: object) -> dict:
    state: dict[str, object] = {
        "thread_id": "thread-09",
        "tenant_id": "tenant-09",
        "user_id": "user-09",
        "role": "support",
        "current_run_id": "run-09",
        "current_intent": "refund_troubleshooting",
        "extracted_slots": {"order_id": "ORD-09"},
    }
    state.update(updates)
    return state


def _result(
    status: str = "success",
    *,
    data: dict | None = None,
    code: str | None = None,
) -> ToolResultV2:
    return ToolResultV2(
        status=status,
        data={"order_no": "ORD-09", "status": "paid"} if status == "success" and data is None else data,
        summary=f"{status} result",
        source_system="test",
        data_freshness_at=None,
        error=(
            ToolError(code=code, safe_message="Safe facade error", retryable=False, source="adapter")
            if code
            else None
        ),
        latency_ms=1,
        audit_ref=None,
    )


def _context(*results: ToolResultV2, facts: dict | None = None) -> BusinessContextV1:
    return BusinessContextV1(
        tenant_id="tenant-09",
        status="complete" if facts else "insufficient",
        facts=facts or {},
        business_fact_refs=[],
        tool_results=list(results),
        missing_required_facts=[] if facts else ["order"],
        errors=[result.error for result in results if result.error is not None],
        data_freshness_at=None,
    )


def _config(**updates: object) -> dict:
    configurable: dict[str, object] = {
        "session": AsyncMock(),
        "permissions": ["tool:get_order"],
        "merchant_scope": {"merchant_ids": ["*"]},
        "trace_id": "trace-09",
    }
    configurable.update(updates)
    return {"configurable": configurable}


@pytest.mark.asyncio
async def test_load_business_context_uses_facade_and_preserves_state_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(spec=BusinessToolService)
    service.fetch_context.return_value = _context(
        _result(),
        facts={"order": {"order_no": "ORD-09", "status": "paid"}},
    )
    monkeypatch.setattr(BusinessToolService, "with_default_registry", lambda session: service)

    update = await load_business_context(_state(), _config())

    assert update["business_context"] == {"order": {"order_no": "ORD-09", "status": "paid"}}
    assert set(update) == {"business_context", "tool_results", "last_business_context_refs", "trace_steps"}
    assert isinstance(update["tool_results"][0], ToolResultV2)
    assert "tool" not in update["tool_results"][0].model_dump()
    assert update["trace_steps"][-1]["node"] == "load_business_context"
    service.fetch_context.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_trusted_permissions_and_scope_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(spec=BusinessToolService)
    service.fetch_context.return_value = _context(_result("permission_denied", data=None, code="EMPTY_MERCHANT_SCOPE"))
    monkeypatch.setattr(BusinessToolService, "with_default_registry", lambda session: service)

    update = await load_business_context(_state(), _config(permissions=[], merchant_scope={}))

    ctx = service.fetch_context.await_args.args[2]
    assert ctx.permissions == []
    assert ctx.merchant_scope == {}
    assert update["business_context"] == {}


@pytest.mark.asyncio
async def test_invalid_response_does_not_leak_raw_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AsyncMock(spec=BusinessToolService)
    service.fetch_context.return_value = _context(_result("invalid_response", data=None, code="INVALID_RESPONSE"))
    monkeypatch.setattr(BusinessToolService, "with_default_registry", lambda session: service)

    update = await load_business_context(_state(), _config())

    assert "raw invalid sentinel" not in str(update)
    assert update["tool_results"][0].status == "invalid_response"
    assert update["tool_results"][0].data is None


def test_router_projects_merchant_scope_and_tool_permissions() -> None:
    merchant_id = uuid4()
    user = User(
        id=uuid4(),
        tenant_id=uuid4(),
        merchant_id=merchant_id,
        username="merchant-09",
        password_hash="hash",
        role="merchant",
        is_active=True,
    )

    config = _trusted_tool_config(user, "trace-merchant")

    assert config["merchant_scope"]["merchant_ids"] == [str(merchant_id)]
    assert "tool:get_order" in config["permissions"]
    assert config["trace_id"] == "trace-merchant"
    assert "permissions" not in _state()
    assert "merchant_scope" not in _state()


def test_router_maps_support_scopes_to_tool_permissions() -> None:
    user = User(
        id=uuid4(),
        tenant_id=uuid4(),
        username="support-09",
        password_hash="hash",
        role="support",
        is_active=True,
    )

    config = _trusted_tool_config(user, "trace-support")

    assert config["merchant_scope"]["merchant_ids"] == ["*"]
    assert config["permissions"]
    assert "tool:get_order" in config["permissions"]
