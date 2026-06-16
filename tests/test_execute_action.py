from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agent.nodes import action_draft as action_draft_module
from src.agent.nodes import execute_action as execute_action_module


ACTION_HASH = "sha256:" + "1" * 64
SNAPSHOT_HASH = "sha256:" + "2" * 64


def _approval_result(**overrides) -> dict:
    payload = {
        "schema_version": "approval_result.v1",
        "approval_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "run_id": str(uuid4()),
        "decision_type": "approve",
        "status": "approved",
        "revision": 1,
        "request_version": 2,
        "level_version": 2,
        "assignment_version": 2,
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
        "decided_by": str(uuid4()),
        "decided_at": "2026-06-15T00:00:00.000Z",
    }
    payload.update(overrides)
    return payload


def _approved_state() -> dict:
    tenant_id = str(uuid4())
    run_id = str(uuid4())
    return {
        "tenant_id": tenant_id,
        "user_id": str(uuid4()),
        "current_run_id": run_id,
        "risk_assessment": {"approval_required": True},
        "approval_result": _approval_result(tenant_id=tenant_id, run_id=run_id),
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
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
    draft_id = str(uuid4())
    return {
        "status": "success",
        "data": {
            "draft_id": draft_id,
            "idempotency_key": "idem",
            "status": "draft_created",
            "created": True,
            "idempotent_reused": False,
            "action_draft": {
                "schema_version": "action_draft.v2",
                "draft_id": draft_id,
                "action_type": "issue_coupon",
                "target_id": "refund-001",
                "status": "draft_created",
            },
            "draft_outcome": {
                "schema_version": "draft_outcome.v1",
                "draft_id": draft_id,
                "status": "not_executed_demo",
                "external_side_effect": False,
            },
            "execution_mode": "demo",
            "action_result": {
                "status": "draft_created",
                "data": {"draft_id": draft_id},
                "error": {},
            },
        },
        "error": {},
    }


@pytest.mark.asyncio
async def test_action_draft_with_service_approval_result_creates_draft(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    session = object()
    state = _approved_state()

    result = await action_draft_module.action_draft(state, {"configurable": {"session": session}})

    assert result["action_draft"]["schema_version"] == "action_draft.v2"
    assert result["draft_outcome"]["status"] == "not_executed_demo"
    assert result["draft_outcome"]["external_side_effect"] is False
    assert result["execution_mode"] == "demo"
    assert result["action_result"]["status"] != "success"
    assert result["trace_steps"][-1]["tool_name"] == "create_coupon_grant_draft"
    assert result["trace_steps"][-1]["node"] == "action_draft"
    create_draft.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_action_blocks_when_required_approval_not_approved(monkeypatch):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["approval_result"] = _approval_result(decision_type="reject", status="rejected")

    result = await action_draft_module.action_draft(state, {"configurable": {"session": object()}})

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "NOT_APPROVED"
    create_draft.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing_field",
    [
        "revision",
        "request_version",
        "level_version",
        "assignment_version",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
    ],
)
async def test_execute_action_blocks_when_approval_result_binding_field_missing(monkeypatch, missing_field: str):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["approval_result"].pop(missing_field)

    result = await action_draft_module.action_draft(state, {"configurable": {"session": object()}})

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "NOT_APPROVED"
    create_draft.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    ["action_payload_hash", "safety_snapshot_ref", "safety_snapshot_hash"],
)
async def test_execute_action_blocks_when_approval_result_binding_mismatches_state(monkeypatch, field: str):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["approval_result"][field] = f"mismatch:{field}"

    result = await action_draft_module.action_draft(state, {"configurable": {"session": object()}})

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "NOT_APPROVED"
    create_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_action_draft_does_not_build_final_service_idempotency_key(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()

    await action_draft_module.action_draft(state, {"configurable": {"session": object()}})

    _, kwargs = create_draft.await_args
    idempotency_key = kwargs["idempotency_key"]
    assert state["proposed_action"]["target_id"] not in idempotency_key
    assert state["action_payload_hash"] not in idempotency_key
    assert ":" not in idempotency_key


@pytest.mark.asyncio
async def test_execute_action_prefers_approval_run_id_for_resumed_action(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    persisted_run_id = str(uuid4())
    state["approval_result"]["run_id"] = persisted_run_id
    state["current_run_id"] = persisted_run_id

    await action_draft_module.action_draft(state, {"configurable": {"session": object()}})

    _, kwargs = create_draft.await_args
    assert kwargs["run_id"] == persisted_run_id
    assert kwargs["idempotency_key"].startswith(f"action_draft_{persisted_run_id}")


@pytest.mark.asyncio
async def test_execute_action_blocks_when_approval_result_run_mismatches_state(monkeypatch):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["approval_result"]["run_id"] = str(uuid4())

    result = await action_draft_module.action_draft(state, {"configurable": {"session": object()}})

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "NOT_APPROVED"
    create_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_action_canonicalizes_legacy_freeform_action_type(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["proposed_action"]["action_type"] = (
        "拒绝600元补偿请求。根据补偿规则，订单实付金额599元对应的最高体验补偿标准为50元。"
    )

    await action_draft_module.action_draft(state, {"configurable": {"session": object()}})

    _, kwargs = create_draft.await_args
    assert kwargs["action_type"] == "manual_review"
    assert "manual_review" not in kwargs["idempotency_key"]
    assert len(kwargs["action_type"]) <= 64


@pytest.mark.asyncio
async def test_execute_action_uses_session_from_runnable_config(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    sessions = []

    def init_service(self, session):
        del self
        sessions.append(session)

    monkeypatch.setattr("src.tools.executors.action.ActionService.__init__", init_service)
    session = object()

    await action_draft_module.action_draft(_approved_state(), {"configurable": {"session": session}})

    assert sessions == [session]


@pytest.mark.asyncio
async def test_execute_action_without_required_approval_succeeds(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["risk_assessment"] = {"approval_required": False}
    state["approval_result"] = None

    result = await action_draft_module.action_draft(state, {"configurable": {"session": object()}})

    assert result["draft_outcome"]["status"] == "not_executed_demo"
    assert result["action_result"]["status"] != "success"
    _, kwargs = create_draft.await_args
    assert kwargs["approval_request_id"] is None


@pytest.mark.asyncio
async def test_execute_action_shim_delegates_to_action_draft(monkeypatch):
    expected = {"draft_outcome": {"status": "not_executed_demo"}}
    delegate = AsyncMock(return_value=expected)
    monkeypatch.setattr(execute_action_module, "action_draft", delegate)
    state = _approved_state()
    config = {"configurable": {"session": object()}}

    result = await execute_action_module.execute_action(state, config)

    assert result == expected
    delegate.assert_awaited_once_with(state, config)
