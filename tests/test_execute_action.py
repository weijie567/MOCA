from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agent.nodes import action_draft as action_draft_module
from src.agent.nodes import execute_action as execute_action_module
from src.platform.trusted_context import MerchantScopeV1, TrustedContext
from src.tools.contracts import ToolCallContext, ToolResultV2
from src.tools.manager import UnifiedToolManager


ACTION_HASH = "sha256:" + "1" * 64
SNAPSHOT_HASH = "sha256:" + "2" * 64
ACTION_PERMISSION = "tool:create_coupon_grant_draft"


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


def _business_fact_ref(tenant_id: str) -> dict[str, Any]:
    return {
        "schema_version": "business_fact_ref.v1",
        "tenant_id": tenant_id,
        "source_system": "moca_demo",
        "resource_type": "refund_case",
        "resource_id": "RF-1001",
        "resource_version": "v1",
        "data_freshness_at": "2026-06-29T00:00:00Z",
        "retrieved_at": "2026-06-29T00:01:00Z",
    }


def _evidence_ref(tenant_id: str) -> dict[str, Any]:
    return {
        "schema_version": "evidence_ref.v1",
        "tenant_id": tenant_id,
        "evidence_id": "refund-policy/chunk-001@v3",
        "doc_key": "refund-policy",
        "chunk_id": "chunk-001",
        "policy_version": "v3",
        "text_hash": "sha256:" + "3" * 64,
        "retrieved_at": "2026-06-29T00:00:00.000Z",
        "retrieval_config_version": "retrieval.v1",
        "rank": 1,
    }


def _phase34_binding_fields(tenant_id: str, run_id: str) -> dict[str, Any]:
    business_fact_ref = _business_fact_ref(tenant_id)
    return {
        "target_merchant_id": "merchant-1",
        "target_merchant_ref": {
            "schema_version": "target_merchant_binding.v1",
            "target_merchant_id": "merchant-1",
            "source": "business_fact_ref",
            "business_fact_ref": business_fact_ref,
        },
        "business_fact_refs": [business_fact_ref],
        "verified_evidence_refs": [_evidence_ref(tenant_id)],
        "claim_verification_ref": "claim_verification_bundle/bundle-1",
        "claim_verification_summary": {"overall_status": "verified", "safe_support_ref_count": 1},
        "risk_decision_ref": f"risk_decision:{run_id}:{ACTION_HASH}",
        "risk_decision": {
            "schema_version": "risk_decision.v1",
            "tenant_id": tenant_id,
            "run_id": run_id,
            "action_id": "act-action-draft",
            "action_payload_hash": ACTION_HASH,
            "risk_level": "high",
            "reason_codes": ["manual_review"],
            "policy_config_version": "approval-policy.v1",
            "risk_config_version": "risk-rules.v1",
            "approval_required": True,
            "evaluated_at": "2026-06-29T00:02:00.000Z",
        },
    }


def _approved_state() -> dict:
    tenant_id = str(uuid4())
    run_id = str(uuid4())
    phase34_bindings = _phase34_binding_fields(tenant_id, run_id)
    return {
        "tenant_id": tenant_id,
        "user_id": str(uuid4()),
        "current_run_id": run_id,
        "risk_assessment": {"approval_required": True},
        "approval_result": _approval_result(tenant_id=tenant_id, run_id=run_id, **phase34_bindings),
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
        **phase34_bindings,
        "claim_verification_bundle": {
            "schema_version": "claim_verification_bundle.v1",
            "overall_status": "verified",
            "route": "continue",
            "claim_results": [],
            "blocked_claims": [],
            "safe_support_refs": phase34_bindings["verified_evidence_refs"],
            "reason_codes": [],
            "verifier_policy_version": "claim-verifier.v1",
        },
        "proposed_action": {
            "action_type": "issue_coupon",
            "target_id": "refund-001",
            "amount": "50",
            "currency": "CNY",
            "reasoning_summary": "Compensation within approved policy.",
        },
        "trace_steps": [],
    }


def _auto_allowed_binding(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "auto_allowed_action_binding.v1",
        "tenant_id": state["tenant_id"],
        "run_id": state["current_run_id"],
        "target_merchant_id": state["target_merchant_id"],
        "action_payload_hash": state["action_payload_hash"],
        "safety_snapshot_ref": state["safety_snapshot_ref"],
        "safety_snapshot_hash": state["safety_snapshot_hash"],
        "risk_decision_ref": state["risk_decision_ref"],
        "idempotency_key": f"auto:{state['tenant_id']}:{state['current_run_id']}",
        "business_fact_refs": state["business_fact_refs"],
        "verified_evidence_refs": state["verified_evidence_refs"],
        "claim_verification_ref": state["claim_verification_ref"],
        "claim_verification_summary": state["claim_verification_summary"],
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


def _trusted_context_for_state(state: dict[str, Any], *, permissions: list[str] | None = None) -> dict[str, Any]:
    return TrustedContext(
        tenant_id=state["tenant_id"],
        user_id=state.get("user_id") or str(uuid4()),
        role=state.get("role") or "support",
        permissions=[ACTION_PERMISSION] if permissions is None else permissions,
        merchant_scope=MerchantScopeV1(merchant_ids=["*"]),
        session_id=None,
        thread_id=state.get("thread_id") or "thread-action-draft",
        run_id=state["current_run_id"],
        trace_id="trace-action-draft",
        locale=None,
    ).model_dump(mode="json")


def _trusted_config(state: dict[str, Any] | None = None, **overrides: Any) -> dict:
    state = state or _approved_state()
    permissions = [ACTION_PERMISSION]
    if "permissions" in overrides:
        permissions = list(overrides["permissions"])
    configurable = {
        "session": object(),
        "trusted_context": _trusted_context_for_state(state, permissions=permissions),
        "permissions": permissions,
    }
    configurable.update(overrides)
    return {"configurable": configurable}


class _RecordingActionExecutor:
    executor_name = "action"

    def __init__(self) -> None:
        self.calls = 0

    def has_tool(self, name: str) -> bool:
        return name == "create_coupon_grant_draft"

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        del name, args, ctx
        self.calls += 1
        return ToolResultV2(
            status="success",
            data=_success_result()["data"],
            summary="created draft",
            source_system="fake_action_executor",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )


@pytest.mark.asyncio
async def test_action_draft_with_service_approval_result_creates_draft(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()

    result = await action_draft_module.action_draft(state, _trusted_config(state))

    assert result["action_draft"]["schema_version"] == "action_draft.v2"
    assert result["draft_outcome"]["status"] == "not_executed_demo"
    assert result["draft_outcome"]["external_side_effect"] is False
    assert result["execution_mode"] == "demo"
    assert result["action_result"]["status"] != "success"
    assert result["trace_steps"][-1]["tool_name"] == "create_coupon_grant_draft"
    assert result["trace_steps"][-1]["node"] == "action_draft"
    assert result["trace_steps"][-1]["status"] == "completed"
    create_draft.assert_awaited_once()


@pytest.mark.asyncio
async def test_action_draft_tool_success_missing_draft_outcome_fails_closed(monkeypatch):
    payload = _success_result()
    payload["data"].pop("draft_outcome")
    create_draft = AsyncMock(return_value=payload)
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)

    state = _approved_state()
    result = await action_draft_module.action_draft(state, _trusted_config(state))

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "INVALID_DRAFT_OUTCOME"
    assert "action_draft" not in result
    assert "draft_outcome" not in result
    assert result["trace_steps"][-1]["status"] == "error"


@pytest.mark.asyncio
async def test_action_draft_tool_success_invalid_draft_outcome_fails_closed(monkeypatch):
    payload = _success_result()
    payload["data"]["draft_outcome"] = {
        "schema_version": "draft_outcome.v1",
        "draft_id": payload["data"]["draft_id"],
        "status": "executed",
        "external_side_effect": False,
    }
    create_draft = AsyncMock(return_value=payload)
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)

    state = _approved_state()
    result = await action_draft_module.action_draft(state, _trusted_config(state))

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "INVALID_DRAFT_OUTCOME"
    assert "action_draft" not in result
    assert "draft_outcome" not in result
    assert result["trace_steps"][-1]["status"] == "error"


@pytest.mark.asyncio
async def test_action_draft_without_write_tool_permission_returns_permission_required_without_draft():
    fake_action_executor = _RecordingActionExecutor()
    manager = UnifiedToolManager(executors=[fake_action_executor])
    state = _approved_state()

    result = await action_draft_module.action_draft(
        state,
        {
            "configurable": {
                "session": object(),
                "trusted_context": _trusted_context_for_state(state, permissions=[]),
                "permissions": [],
                "action_tool_manager": manager,
            }
        },
    )

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "PERMISSION_REQUIRED"
    assert "action_draft" not in result
    assert "draft_outcome" not in result
    assert result["trace_steps"][-1]["status"] == "error"
    assert fake_action_executor.calls == 0


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
@pytest.mark.parametrize(
    "missing_field",
    [
        "target_merchant_id",
        "business_fact_refs",
        "verified_evidence_refs",
    ],
)
async def test_execute_action_blocks_when_phase34_approval_binding_missing(monkeypatch, missing_field: str):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["approval_result"].pop(missing_field)

    result = await action_draft_module.action_draft(state, _trusted_config(state))

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "NOT_APPROVED"
    create_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_action_blocks_when_phase34_approval_claim_binding_missing(monkeypatch):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["approval_result"].pop("claim_verification_ref")
    state["approval_result"].pop("claim_verification_summary")

    result = await action_draft_module.action_draft(state, _trusted_config(state))

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "NOT_APPROVED"
    create_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_action_blocks_when_phase34_approval_risk_binding_missing(monkeypatch):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["approval_result"].pop("risk_decision_ref")
    state["approval_result"].pop("risk_decision")

    result = await action_draft_module.action_draft(state, _trusted_config(state))

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "NOT_APPROVED"
    create_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_action_blocks_when_phase34_approval_binding_mismatches_state(monkeypatch):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["approval_result"]["target_merchant_id"] = "merchant-other"

    result = await action_draft_module.action_draft(state, _trusted_config(state))

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "NOT_APPROVED"
    create_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_action_passes_phase34_binding_fields_to_action_tool(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()

    await action_draft_module.action_draft(state, _trusted_config(state))

    _, kwargs = create_draft.await_args
    for field in (
        "target_merchant_id",
        "target_merchant_ref",
        "business_fact_refs",
        "verified_evidence_refs",
        "claim_verification_ref",
        "claim_verification_summary",
        "risk_decision_ref",
        "risk_decision",
    ):
        assert kwargs[field] == state[field]
    assert kwargs["auto_allowed_binding"] is None


@pytest.mark.asyncio
async def test_execute_action_auto_allowed_binding_invokes_action_tool(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["risk_assessment"] = {"approval_required": False}
    state["approval_result"] = None
    state["auto_allowed_binding"] = _auto_allowed_binding(state)

    result = await action_draft_module.action_draft(state, _trusted_config(state))

    assert result["draft_outcome"]["status"] == "not_executed_demo"
    _, kwargs = create_draft.await_args
    assert kwargs["approval_request_id"] is None
    assert kwargs["auto_allowed_binding"] == state["auto_allowed_binding"]


@pytest.mark.asyncio
async def test_action_draft_does_not_build_final_service_idempotency_key(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()

    await action_draft_module.action_draft(state, _trusted_config(state))

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

    await action_draft_module.action_draft(state, _trusted_config(state))

    _, kwargs = create_draft.await_args
    assert kwargs["run_id"] == persisted_run_id
    assert kwargs["idempotency_key"].startswith(f"action_draft_{persisted_run_id}")


@pytest.mark.asyncio
async def test_action_draft_authorizes_approval_against_trusted_context_not_legacy_state(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    trusted_context = _trusted_context_for_state(state)
    state["tenant_id"] = str(uuid4())
    state["current_run_id"] = str(uuid4())

    await action_draft_module.action_draft(
        state,
        {"configurable": {"session": object(), "trusted_context": trusted_context}},
    )

    _, kwargs = create_draft.await_args
    assert kwargs["tenant_id"] == trusted_context["tenant_id"]
    assert kwargs["run_id"] == trusted_context["run_id"]


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

    await action_draft_module.action_draft(state, _trusted_config(state))

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

    state = _approved_state()
    await action_draft_module.action_draft(state, _trusted_config(state, session=session))

    assert sessions == [session]


@pytest.mark.asyncio
async def test_execute_action_without_required_approval_fails_closed(monkeypatch):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["risk_assessment"] = {"approval_required": False}
    state["approval_result"] = None

    result = await action_draft_module.action_draft(state, _trusted_config())

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "AUTO_ALLOWED_BINDING_REQUIRED"
    assert "draft_outcome" not in result
    create_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_action_shim_delegates_to_action_draft(monkeypatch):
    expected = {"draft_outcome": {"status": "not_executed_demo"}}
    delegate = AsyncMock(return_value=expected)
    monkeypatch.setattr(execute_action_module, "action_draft", delegate)
    state = _approved_state()
    config = _trusted_config()

    result = await execute_action_module.execute_action(state, config)

    assert result == expected
    delegate.assert_awaited_once_with(state, config)
