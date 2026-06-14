from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agent.nodes import execute_action as execute_action_module


def _approved_state() -> dict:
    return {
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "current_run_id": str(uuid4()),
        "risk_assessment": {"approval_required": True},
        "approval_result": {"approval_id": str(uuid4()), "decision": "approve"},
        "proposed_action": {
            "action_type": "issue_coupon",
            "target_id": "refund-001",
            "amount": "50",
            "currency": "CNY",
            "reasoning_summary": "Compensation within approved policy.",
        },
        "trace_steps": [],
    }


def _success_result() -> dict:
    return {
        "status": "success",
        "data": {
            "draft_id": str(uuid4()),
            "idempotency_key": "idem",
            "status": "draft_created",
            "created": True,
            "idempotent_reused": False,
        },
        "error": {},
    }


@pytest.mark.asyncio
async def test_execute_action_with_approval_creates_draft(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.agent.tools.unified.create_coupon_grant_draft", create_draft)
    session = object()
    state = _approved_state()

    result = await execute_action_module.execute_action(state, {"configurable": {"session": session}})

    assert result["action_result"]["status"] == "success"
    assert result["trace_steps"][-1]["tool_name"] == "create_coupon_grant_draft"
    create_draft.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_action_blocks_when_required_approval_not_approved(monkeypatch):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.agent.tools.unified.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["approval_result"] = {"approval_id": str(uuid4()), "decision": "reject"}

    result = await execute_action_module.execute_action(state, {"configurable": {"session": object()}})

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "NOT_APPROVED"
    create_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_action_idempotency_key_uses_run_approval_action_and_target(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.agent.tools.unified.create_coupon_grant_draft", create_draft)
    state = _approved_state()

    await execute_action_module.execute_action(state, {"configurable": {"session": object()}})

    _, kwargs = create_draft.await_args
    expected_key = (
        f"{state['current_run_id']}_{state['approval_result']['approval_id']}_"
        f"{state['proposed_action']['action_type']}_{state['proposed_action']['target_id']}"
    )
    assert kwargs["idempotency_key"] == expected_key


@pytest.mark.asyncio
async def test_execute_action_prefers_approval_run_id_for_resumed_action(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.agent.tools.unified.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    persisted_run_id = str(uuid4())
    state["approval_result"]["run_id"] = persisted_run_id

    await execute_action_module.execute_action(state, {"configurable": {"session": object()}})

    _, kwargs = create_draft.await_args
    assert kwargs["run_id"] == persisted_run_id
    assert kwargs["idempotency_key"].startswith(f"{persisted_run_id}_{state['approval_result']['approval_id']}_")


@pytest.mark.asyncio
async def test_execute_action_canonicalizes_legacy_freeform_action_type(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.agent.tools.unified.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["proposed_action"]["action_type"] = (
        "拒绝600元补偿请求。根据补偿规则，订单实付金额599元对应的最高体验补偿标准为50元。"
    )

    await execute_action_module.execute_action(state, {"configurable": {"session": object()}})

    _, kwargs = create_draft.await_args
    assert kwargs["action_type"] == "manual_review"
    assert "_manual_review_" in kwargs["idempotency_key"]
    assert len(kwargs["action_type"]) <= 64


@pytest.mark.asyncio
async def test_execute_action_uses_session_from_runnable_config(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.agent.tools.unified.create_coupon_grant_draft", create_draft)
    session = object()

    await execute_action_module.execute_action(_approved_state(), {"configurable": {"session": session}})

    _, kwargs = create_draft.await_args
    assert kwargs["session"] is session


@pytest.mark.asyncio
async def test_execute_action_without_required_approval_succeeds(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.agent.tools.unified.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["risk_assessment"] = {"approval_required": False}
    state["approval_result"] = None

    result = await execute_action_module.execute_action(state, {"configurable": {"session": object()}})

    assert result["action_result"]["status"] == "success"
    _, kwargs = create_draft.await_args
    assert "_no_approval_" in kwargs["idempotency_key"]
