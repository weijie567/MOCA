from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState
from src.agent.tools.create_coupon_grant_draft import create_coupon_grant_draft

FULL_REFUND_TERMS = ("full_refund", "全额退款", "全额退", "整单退款")
ACTIONABLE_ACTIONS = {
    "issue_coupon",
    "approve_refund",
    "full_refund",
    "partial_refund",
    "compensation",
    "manual_review",
}


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


def _canonical_action_type(action: Any) -> str:
    action_text = str(action or "")
    lowered = action_text.lower()
    if lowered in ACTIONABLE_ACTIONS:
        return lowered
    if any(term in action_text for term in ("拒绝", "不建议", "无法支持")) or "reject" in lowered:
        return "manual_review"
    if any(term in lowered for term in ("coupon", "compensation", "compensate")) or any(
        term in action_text for term in ("补偿", "券", "赔付")
    ):
        return "issue_coupon"
    if any(term in action_text for term in FULL_REFUND_TERMS):
        return "full_refund"
    if "partial_refund" in lowered or "部分退款" in action_text:
        return "partial_refund"
    if "refund" in lowered or "退款" in action_text:
        return "approve_refund"
    return "manual_review"


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
    run_id = approval.get("run_id") or state.get("current_run_id") or ""
    approval_id = approval.get("approval_id") or "no_approval"
    action_type = _canonical_action_type(proposed.get("action_type"))
    proposed = {**proposed, "action_type": action_type}
    idempotency_key = (
        f"{run_id}_{approval_id}_"
        f"{action_type}_{proposed.get('target_id', 'unknown')}"
    )

    result = await create_coupon_grant_draft(
        tenant_id=state.get("tenant_id", ""),
        user_id=state.get("user_id", ""),
        run_id=run_id,
        approval_request_id=approval.get("approval_id"),
        idempotency_key=idempotency_key,
        action_type=action_type,
        payload=proposed,
        session=session,
    )

    status = "completed" if result.get("status") == "success" else "error"
    return {
        "action_result": result,
        "trace_steps": (state.get("trace_steps") or [])
        + [_trace_step(status, started_at, "create_coupon_grant_draft")],
    }
