from __future__ import annotations

from uuid import uuid4

import pytest

from src.agent.nodes import approval_gate as approval_gate_module


def _state() -> dict:
    action_hash = "sha256:" + "1" * 64
    snapshot_ref = "snapshot:test"
    snapshot_hash = "sha256:" + "2" * 64
    risk_decision_ref = f"risk_decision:run:{action_hash}"
    target_merchant_ref = {
        "schema_version": "target_merchant_binding.v1",
        "target_merchant_id": "merchant-1",
        "source": "business_fact_ref",
        "business_fact_ref": {"resource_type": "refund_case", "resource_id": "refund-001"},
    }
    business_fact_refs = [{"resource_type": "refund_case", "resource_id": "refund-001"}]
    verified_evidence_refs = [{"evidence_id": "refund-policy/chunk-001@v3"}]
    risk_decision = {
        "schema_version": "risk_decision.v1",
        "action_payload_hash": action_hash,
        "approval_required": True,
    }
    return {
        "current_run_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "risk_assessment": {
            "risk_level": "high",
            "risk_reason": "Compensation amount exceeds threshold",
            "approval_required": True,
            "rule_ref": "HR-01",
        },
        "proposed_action": {
            "schema_version": "proposed_action.v1",
            "action_type": "issue_coupon",
            "target_id": "refund-001",
            "amount": "100.00",
            "currency": "CNY",
            "reason": "Policy compensation applies.",
        },
        "approval_revision_refs": [
            {
                "approval_id": str(uuid4()),
                "revision": 1,
                "request_version": 1,
                "level_id": str(uuid4()),
                "level_version": 1,
                "assignment_id": str(uuid4()),
                "assignment_version": 1,
            }
        ],
        "approval_plan": {
            "schema_version": "approval_plan.v1",
            "approval_required": True,
            "approval_idempotency_key": "approval:test-key",
            "action_payload_hash": action_hash,
            "safety_snapshot_ref": snapshot_ref,
            "safety_snapshot_hash": snapshot_hash,
            "target_merchant_id": "merchant-1",
            "target_merchant_ref": target_merchant_ref,
            "business_fact_refs": business_fact_refs,
            "verified_evidence_refs": verified_evidence_refs,
            "claim_verification_ref": None,
            "claim_verification_summary": {"overall_status": "verified"},
            "risk_decision_ref": risk_decision_ref,
            "risk_decision": risk_decision,
        },
        "action_payload_hash": action_hash,
        "safety_snapshot_ref": snapshot_ref,
        "safety_snapshot_hash": snapshot_hash,
        "target_merchant_id": "merchant-1",
        "target_merchant_ref": target_merchant_ref,
        "business_fact_refs": business_fact_refs,
        "verified_evidence_refs": verified_evidence_refs,
        "claim_verification_ref": None,
        "claim_verification_summary": {"overall_status": "verified"},
        "risk_decision_ref": risk_decision_ref,
        "risk_decision": risk_decision,
        "approval_idempotency_key": "approval:test-key",
        "trace_steps": [{"node": "assess_risk_and_approval", "status": "completed"}],
    }


@pytest.mark.asyncio
async def test_approval_gate_interrupt_payload_contains_display_refs_and_versions(monkeypatch):
    captured_payload: dict = {}
    decision = {
        "schema_version": "approval_result.v1",
        "approval_id": str(uuid4()),
        "decision_type": "approve",
        "status": "approved",
        "revision": 1,
        "request_version": 2,
        "level_version": 2,
        "assignment_version": 2,
        "action_payload_hash": "sha256:" + "1" * 64,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": "sha256:" + "2" * 64,
        "decided_by": str(uuid4()),
        "decided_at": "2026-06-15T00:00:00.000Z",
    }

    def fake_interrupt(payload):
        captured_payload.update(payload)
        return decision

    monkeypatch.setattr(approval_gate_module, "interrupt", fake_interrupt)

    await approval_gate_module.approval_gate(_state())

    assert captured_payload["run_id"]
    assert captured_payload["tenant_id"]
    assert captured_payload["user_id"]
    assert captured_payload["risk_level"] == "high"
    assert captured_payload["risk_rule_ref"] == "HR-01"
    assert captured_payload["proposed_action"]["action_type"] == "issue_coupon"
    assert captured_payload["approval_revision_refs"][0]["request_version"] == 1
    assert captured_payload["action_payload_hash"] == "sha256:" + "1" * 64
    assert captured_payload["safety_snapshot_ref"] == "snapshot:test"
    assert captured_payload["safety_snapshot_hash"] == "sha256:" + "2" * 64
    assert captured_payload["approval_plan"]["schema_version"] == "approval_plan.v1"
    assert captured_payload["approval_idempotency_key"] == "approval:test-key"
    assert captured_payload["target_merchant_id"] == "merchant-1"
    assert captured_payload["target_merchant_ref"]["target_merchant_id"] == "merchant-1"
    assert captured_payload["business_fact_refs"][0]["resource_id"] == "refund-001"
    assert captured_payload["verified_evidence_refs"][0]["evidence_id"] == "refund-policy/chunk-001@v3"
    assert captured_payload["claim_verification_ref"] is None
    assert captured_payload["claim_verification_summary"] == {"overall_status": "verified"}
    assert captured_payload["risk_decision_ref"].startswith("risk_decision:")
    assert captured_payload["risk_decision"]["schema_version"] == "risk_decision.v1"
    assert captured_payload["allowed_decision_types"] == [
        "accept",
        "approve",
        "edit",
        "respond",
        "reject",
        "ignore",
    ]
    assert captured_payload["expires_at"]


@pytest.mark.asyncio
async def test_approval_gate_fails_closed_when_required_plan_lacks_idempotency(monkeypatch):
    state = _state()
    state["approval_plan"] = {**state["approval_plan"], "approval_idempotency_key": None}

    def fail_interrupt(_payload):
        raise AssertionError("approval_gate must fail closed before interrupt")

    monkeypatch.setattr(approval_gate_module, "interrupt", fail_interrupt)

    result = await approval_gate_module.approval_gate(state)

    assert result["approval_result"] is None
    assert result["final_response"] == "审批计划缺少可信幂等键，已停止执行高风险操作。"
    assert result["trace_steps"][-1]["status"] == "error"


@pytest.mark.asyncio
async def test_approval_gate_sets_approval_result_only_from_trusted_service_payload(monkeypatch):
    decision = {
        "schema_version": "approval_result.v1",
        "approval_id": str(uuid4()),
        "decision_type": "reject",
        "status": "rejected",
        "revision": 1,
        "request_version": 2,
        "level_version": 2,
        "assignment_version": 2,
        "action_payload_hash": "sha256:" + "1" * 64,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": "sha256:" + "2" * 64,
        "decided_by": str(uuid4()),
        "decided_at": "2026-06-15T00:00:00.000Z",
    }
    monkeypatch.setattr(approval_gate_module, "interrupt", lambda payload: decision)

    result = await approval_gate_module.approval_gate(_state())

    assert result["approval_result"] == decision


@pytest.mark.asyncio
async def test_approval_gate_rejects_untrusted_raw_resume_payload(monkeypatch):
    monkeypatch.setattr(approval_gate_module, "interrupt", lambda payload: {"decision": "approve"})

    result = await approval_gate_module.approval_gate(_state())

    assert result["approval_result"] is None
    assert result["final_response"]
    assert result["trace_steps"][-1]["node"] == "approval_gate"
    assert result["trace_steps"][-1]["status"] == "error"


@pytest.mark.asyncio
async def test_approval_gate_appends_trace_step(monkeypatch):
    monkeypatch.setattr(
        approval_gate_module,
        "interrupt",
        lambda payload: {
            "schema_version": "approval_result.v1",
            "approval_id": str(uuid4()),
            "decision_type": "approve",
            "status": "approved",
            "revision": 1,
            "request_version": 2,
            "level_version": 2,
            "assignment_version": 2,
            "action_payload_hash": "sha256:" + "1" * 64,
            "safety_snapshot_ref": "snapshot:test",
            "safety_snapshot_hash": "sha256:" + "2" * 64,
            "decided_by": str(uuid4()),
            "decided_at": "2026-06-15T00:00:00.000Z",
        },
    )

    result = await approval_gate_module.approval_gate(_state())

    assert result["trace_steps"][-1]["node"] == "approval_gate"
    assert result["trace_steps"][-1]["status"] == "completed"
