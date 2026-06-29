from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from langgraph.types import interrupt

from src.agent.state import AgentState

APPROVAL_TIMEOUT_HOURS = 24


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _trace_step(status: str, started_at: str) -> dict[str, Any]:
    return {
        "node": "approval_gate",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
    }


async def approval_gate(state: AgentState) -> dict:
    """Interrupt graph execution until a human approval decision resumes it."""
    started_at = _now_iso()
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action") or {}
    approval_plan = state.get("approval_plan") if isinstance(state.get("approval_plan"), dict) else {}
    if approval_plan:
        approval_idempotency_key = approval_plan.get("approval_idempotency_key")
    else:
        approval_idempotency_key = state.get("approval_idempotency_key")
    if not approval_idempotency_key:
        return {
            "approval_result": None,
            "final_response": "审批计划缺少可信幂等键，已停止执行高风险操作。",
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }

    # interrupt_payload proposed_action is display-only; ApprovalService owns persistence.
    interrupt_payload = {
        "run_id": state.get("current_run_id"),
        "tenant_id": state.get("tenant_id"),
        "user_id": state.get("user_id"),
        "proposed_action": proposed,
        "risk_level": risk.get("risk_level"),
        "risk_reason": risk.get("risk_reason"),
        "risk_rule_ref": risk.get("rule_ref"),
        "approval_revision_refs": state.get("approval_revision_refs") or [],
        "action_payload_hash": state.get("action_payload_hash"),
        "safety_snapshot_ref": state.get("safety_snapshot_ref"),
        "safety_snapshot_hash": state.get("safety_snapshot_hash"),
        "policy_config_version": state.get("policy_config_version"),
        "risk_config_version": state.get("risk_config_version"),
        "retrieval_config_version": state.get("retrieval_config_version"),
        "evidence_refs": state.get("evidence_refs") or [],
        "approval_plan": approval_plan,
        "target_merchant_id": state.get("target_merchant_id"),
        "target_merchant_ref": state.get("target_merchant_ref"),
        "business_fact_refs": state.get("business_fact_refs") or [],
        "verified_evidence_refs": state.get("verified_evidence_refs") or [],
        "claim_verification_ref": state.get("claim_verification_ref"),
        "claim_verification_summary": state.get("claim_verification_summary"),
        "risk_decision_ref": state.get("risk_decision_ref"),
        "risk_decision": state.get("risk_decision"),
        "approval_idempotency_key": approval_idempotency_key,
        "allowed_decision_types": ["accept", "approve", "edit", "respond", "reject", "ignore"],
        "expires_at": (datetime.now(UTC) + timedelta(hours=APPROVAL_TIMEOUT_HOURS)).isoformat(),
    }

    decision = interrupt(interrupt_payload)
    if not isinstance(decision, dict) or decision.get("schema_version") != "approval_result.v1":
        return {
            "approval_result": None,
            "final_response": "审批结果无效，已停止执行高风险操作。",
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }

    return {
        "approval_result": decision,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
    }
