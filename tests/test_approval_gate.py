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
            "action_type": "issue_coupon",
            "target_id": "refund-001",
            "amount": "600",
            "currency": "CNY",
            "reasoning_summary": "Policy compensation applies.",
        },
        "trace_steps": [{"node": "assess_risk_and_approval", "status": "completed"}],
    }


@pytest.mark.asyncio
async def test_approval_gate_interrupt_payload_contains_required_fields(monkeypatch):
    captured_payload: dict = {}
    decision = {
        "approval_id": str(uuid4()),
        "decision": "approve",
        "reason": None,
        "decided_by": str(uuid4()),
        "decided_at": "2026-05-16T00:00:00+00:00",
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
    assert captured_payload["expires_at"]


@pytest.mark.asyncio
async def test_approval_gate_sets_approval_result_from_resume_payload(monkeypatch):
    decision = {
        "approval_id": str(uuid4()),
        "decision": "reject",
        "reason": "Insufficient evidence for compensation",
        "decided_by": str(uuid4()),
        "decided_at": "2026-05-16T00:00:00+00:00",
    }
    monkeypatch.setattr(approval_gate_module, "interrupt", lambda payload: decision)

    result = await approval_gate_module.approval_gate(_state())

    assert result["approval_result"] == decision


@pytest.mark.asyncio
async def test_approval_gate_appends_trace_step(monkeypatch):
    monkeypatch.setattr(approval_gate_module, "interrupt", lambda payload: {"decision": "approve"})

    result = await approval_gate_module.approval_gate(_state())

    assert result["trace_steps"][-1]["node"] == "approval_gate"
    assert result["trace_steps"][-1]["status"] == "completed"
