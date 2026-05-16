from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState
from src.agent.tools.create_coupon_grant_draft import create_coupon_grant_draft


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _trace_step(status: str, started_at: str, tool_name: str | None = None) -> dict[str, Any]:
    return {
        "node": "execute_action",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "tool_name": tool_name,
    }


async def execute_action(state: AgentState, config: RunnableConfig) -> dict:
    """Execute an approved action by creating a durable draft."""
    started_at = _now_iso()
    proposed = state.get("proposed_action") or {}
    approval = state.get("approval_result") or {}
    risk = state.get("risk_assessment") or {}

    if risk.get("approval_required") and approval.get("decision") != "approve":
        return {
            "action_result": {
                "status": "error",
                "data": {},
                "error": {
                    "error_code": "NOT_APPROVED",
                    "message": "Action requires approval but was not approved",
                    "retryable": False,
                },
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }

    session = config["configurable"]["session"]
    approval_id = approval.get("approval_id") or "no_approval"
    idempotency_key = (
        f"{state.get('current_run_id')}_{approval_id}_"
        f"{proposed.get('action_type', 'unknown')}_{proposed.get('target_id', 'unknown')}"
    )

    result = await create_coupon_grant_draft(
        tenant_id=state.get("tenant_id", ""),
        user_id=state.get("user_id", ""),
        run_id=state.get("current_run_id", ""),
        approval_request_id=approval.get("approval_id"),
        idempotency_key=idempotency_key,
        action_type=proposed.get("action_type", "unknown"),
        payload=proposed,
        session=session,
    )

    status = "completed" if result.get("status") == "success" else "error"
    return {
        "action_result": result,
        "trace_steps": (state.get("trace_steps") or [])
        + [_trace_step(status, started_at, "create_coupon_grant_draft")],
    }
