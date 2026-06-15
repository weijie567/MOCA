from __future__ import annotations

from uuid import uuid4

import pytest

from src.agent.nodes import approval_gate as approval_gate_module


def _state() -> dict:
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
        "action_payload_hash": "sha256:" + "1" * 64,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": "sha256:" + "2" * 64,
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
    assert captured_payload["allowed_decision_types"] == ["accept", "approve", "reject", "ignore"]
    assert captured_payload["expires_at"]


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
