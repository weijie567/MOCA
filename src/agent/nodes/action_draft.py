from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from src.actions.schemas import DraftOutcomeV1
from src.agent.state import AgentState
from src.approvals.schemas import TrustedApprovalResultV1
from src.platform.context_projections import project_to_tool_context
from src.platform.trusted_context import TrustedContext
from src.tools.contracts import ToolCallContext, ToolError, ToolResultV2
from src.tools.platform import ToolPlatform

FULL_REFUND_TERMS = ("full_refund", "全额退款", "全额退", "整单退款")
ACTION_TOOL_NAME = "create_coupon_grant_draft"
ACTIONABLE_ACTIONS = {
    "issue_coupon",
    "approve_refund",
    "full_refund",
    "partial_refund",
    "compensation",
    "manual_review",
}
REQUIRED_APPROVAL_RESULT_FIELDS = (
    "approval_id",
    "tenant_id",
    "run_id",
    "revision",
    "request_version",
    "level_version",
    "assignment_version",
    "action_payload_hash",
    "safety_snapshot_ref",
    "safety_snapshot_hash",
)
ACTION_RESULT_COMPATIBILITY_GATE = (
    "Phase 14 action-draft-boundary-owned deprecated compatibility output; replace/remove at "
    "Phase 15 Replay Event Contract before Phase 15 verification, target no later than "
    "2026-07-16 unless Phase 15 is replanned."
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _trace_step(status: str, started_at: str, tool_name: str | None = None) -> dict[str, Any]:
    return {
        "node": "action_draft",
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


def _compat_action_result_from_data(data: dict[str, Any], draft_outcome: dict[str, Any]) -> dict[str, Any]:
    compat = data.get("action_result")
    if isinstance(compat, dict):
        compat = dict(compat)
        if compat.get("status") == "success":
            compat["status"] = "draft_created"
        compat.setdefault("compatibility", ACTION_RESULT_COMPATIBILITY_GATE)
        return compat
    return {
        "status": "draft_created",
        "data": {
            "draft_id": data.get("draft_id"),
            "draft_outcome": draft_outcome,
        },
        "error": {},
        "compatibility": ACTION_RESULT_COMPATIBILITY_GATE,
    }


def _verification_route(state: AgentState) -> str | None:
    rag_verification = state.get("rag_verification")
    if isinstance(rag_verification, dict):
        route = rag_verification.get("route")
        if isinstance(route, dict) and route.get("route"):
            return str(route["route"])
    route_value = state.get("verification_route")
    return str(route_value) if route_value else None


def _verification_blocks_action(state: AgentState) -> bool:
    route = _verification_route(state)
    return route is not None and route != "allow"


def _action_error_result(result: ToolResultV2) -> dict[str, Any]:
    error = result.error
    return {
        "status": "error",
        "data": {},
        "error": {
            "error_code": error.code if error is not None else result.status.upper(),
            "message": error.safe_message if error is not None else result.summary,
            "retryable": result.retryable,
        },
    }


def _invalid_draft_outcome_result(result: ToolResultV2) -> ToolResultV2:
    summary = "Action executor returned an invalid draft_outcome"
    return ToolResultV2(
        status="invalid_response",
        data=None,
        summary=summary,
        source_system=result.source_system,
        data_freshness_at=result.data_freshness_at,
        policy_evidence_refs=list(result.policy_evidence_refs),
        business_fact_refs=list(result.business_fact_refs),
        error=ToolError(code="INVALID_DRAFT_OUTCOME", safe_message=summary, retryable=False, source="adapter"),
        retryable=False,
        retry_after_ms=None,
        latency_ms=result.latency_ms,
        audit_ref=result.audit_ref,
    )


def _draft_update_from_tool_result(result: ToolResultV2) -> tuple[dict[str, Any], str]:
    if result.status != "success":
        return {"action_result": _action_error_result(result)}, "error"

    data = dict(result.data or {})
    action_draft_data = data.get("action_draft") if isinstance(data.get("action_draft"), dict) else None
    raw_draft_outcome = data.get("draft_outcome")
    if not isinstance(raw_draft_outcome, dict) or not raw_draft_outcome:
        return {"action_result": _action_error_result(_invalid_draft_outcome_result(result))}, "error"
    try:
        draft_outcome = DraftOutcomeV1.model_validate(raw_draft_outcome).model_dump(mode="json")
    except ValidationError:
        return {"action_result": _action_error_result(_invalid_draft_outcome_result(result))}, "error"
    if not action_draft_data:
        action_draft_data = {
            "draft_id": data.get("draft_id"),
            "idempotency_key": data.get("idempotency_key"),
            "status": data.get("status"),
        }
    update = {
        "action_draft": action_draft_data,
        "draft_outcome": draft_outcome,
        "execution_mode": data.get("execution_mode") or "demo",
        "action_result": _compat_action_result_from_data(data, draft_outcome),
    }
    trace_status = "completed" if draft_outcome.get("status") == "not_executed_demo" else "error"
    return update, trace_status


def _approval_result_is_action_authorizing(
    state: AgentState,
    approval: dict[str, Any],
    trusted_context: TrustedContext | None,
) -> bool:
    trusted = _trusted_approval_result(state, approval, trusted_context)
    if trusted is None:
        return False
    return trusted.decision_type in {"accept", "approve"} and trusted.status == "approved"


def _trusted_approval_result(
    state: AgentState,
    approval: dict[str, Any],
    trusted_context: TrustedContext | None,
) -> TrustedApprovalResultV1 | None:
    if any(not approval.get(field) for field in REQUIRED_APPROVAL_RESULT_FIELDS):
        return None
    try:
        trusted = TrustedApprovalResultV1.model_validate(approval)
    except ValidationError:
        return None
    if trusted_context is not None:
        if str(trusted.tenant_id) != trusted_context.tenant_id:
            return None
        if str(trusted.run_id) != trusted_context.run_id:
            return None
    else:
        if str(trusted.tenant_id) != str(state.get("tenant_id") or ""):
            return None
        if str(trusted.run_id) != str(state.get("current_run_id") or ""):
            return None
    if (
        trusted.action_payload_hash != state.get("action_payload_hash")
        or trusted.safety_snapshot_ref != state.get("safety_snapshot_ref")
        or trusted.safety_snapshot_hash != state.get("safety_snapshot_hash")
    ):
        return None
    return trusted


async def action_draft(state: AgentState, config: RunnableConfig) -> dict:
    """Create a durable demo action draft through the node-only tool boundary."""
    started_at = _now_iso()
    if _verification_blocks_action(state):
        return {
            "action_result": {
                "status": "error",
                "data": {},
                "error": {
                    "error_code": "VERIFIER_NOT_ALLOW",
                    "message": "Recommendation verification did not allow action draft creation",
                    "retryable": False,
                },
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }
    proposed = state.get("proposed_action") or {}
    approval = state.get("approval_result") or {}
    risk = state.get("risk_assessment") or {}
    configurable = config.get("configurable") or {}
    trusted_context = _trusted_context_from_config(configurable)
    approval_accepted = _approval_result_is_action_authorizing(state, approval, trusted_context)

    if risk.get("approval_required") and not approval_accepted:
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
    if not approval_accepted:
        return {
            "action_result": {
                "status": "error",
                "data": {},
                "error": {
                    "error_code": "AUTO_ALLOWED_BINDING_REQUIRED",
                    "message": "No-approval action draft requires a durable auto-allowed binding",
                    "retryable": False,
                },
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }

    session = configurable["session"]
    if trusted_context is None:
        return {
            "action_result": {
                "status": "error",
                "data": {},
                "error": {
                    "error_code": "MISSING_TRUSTED_CONTEXT",
                    "message": "Trusted context is required for action draft creation",
                    "retryable": False,
                },
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }
    run_id = approval.get("run_id") or trusted_context.run_id
    approval_id = approval.get("approval_id")
    action_type = _canonical_action_type(proposed.get("action_type"))
    proposed = {**proposed, "action_type": action_type}

    tool_ctx = project_to_tool_context(
        trusted_context,
        request_id=configurable.get("request_id") or run_id,
        tool_call_id=f"{run_id}:action_draft:{ACTION_TOOL_NAME}",
        caller_node="action_draft",
        deadline_at=configurable.get("deadline_at"),
        attempt=1,
        max_attempts=1,
        idempotency_key=f"action_draft_{run_id}_{approval_id or 'auto_allowed'}",
        approval_ref=approval_id,
        safety_snapshot_ref=state.get("safety_snapshot_ref")
        or approval.get("safety_snapshot_ref")
        or risk.get("safety_snapshot_ref")
        or risk.get("snapshot_ref"),
        policy_snapshot_ref=None,
    )
    action_payload_hash = state.get("action_payload_hash") or approval.get("action_payload_hash")
    safety_snapshot_ref = (
        state.get("safety_snapshot_ref")
        or approval.get("safety_snapshot_ref")
        or risk.get("safety_snapshot_ref")
        or risk.get("snapshot_ref")
    )
    safety_snapshot_hash = state.get("safety_snapshot_hash") or approval.get("safety_snapshot_hash")
    args = {
        "action_type": action_type,
        "payload": proposed,
        "action_payload_hash": action_payload_hash,
        "safety_snapshot_ref": safety_snapshot_ref,
        "safety_snapshot_hash": safety_snapshot_hash,
    }
    if approval_id:
        args["approval_request_id"] = approval_id

    tool_result = await _invoke_action_tool(configurable, session, args, tool_ctx)
    update, status = _draft_update_from_tool_result(tool_result)

    return {
        **update,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(status, started_at, ACTION_TOOL_NAME)],
    }


def _trusted_context_from_config(configurable: dict[str, Any]) -> TrustedContext | None:
    raw_context = configurable.get("trusted_context")
    if raw_context is None:
        return None
    try:
        return TrustedContext.model_validate(raw_context)
    except ValidationError:
        return None


async def _invoke_action_tool(
    configurable: dict[str, Any],
    session: Any,
    args: dict[str, Any],
    tool_ctx: ToolCallContext,
) -> ToolResultV2:
    tool_platform = configurable.get("action_tool_platform")
    legacy_manager = configurable.get("action_tool_manager")
    if tool_platform is None and legacy_manager is not None and hasattr(legacy_manager, "_platform"):
        tool_platform = legacy_manager._platform
    if tool_platform is None:
        tool_platform = configurable.get("tool_platform")
    if tool_platform is None:
        tool_platform = ToolPlatform.with_defaults(session)

    outcome = await tool_platform.invoke(ACTION_TOOL_NAME, args, tool_ctx, session=session)
    return outcome.tool_result
