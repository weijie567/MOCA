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

    interrupt_payload = {
        "run_id": state.get("current_run_id"),
        "tenant_id": state.get("tenant_id"),
        "user_id": state.get("user_id"),
        "proposed_action": proposed,
        "risk_level": risk.get("risk_level"),
        "risk_reason": risk.get("risk_reason"),
        "risk_rule_ref": risk.get("rule_ref"),
        "expires_at": (datetime.now(UTC) + timedelta(hours=APPROVAL_TIMEOUT_HOURS)).isoformat(),
    }

    decision = interrupt(interrupt_payload)

    return {
        "approval_result": decision,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
    }
