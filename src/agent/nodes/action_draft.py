from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from src.actions.schemas import DraftOutcomeV1
from src.agent.state import AgentState
from src.approvals.schemas import AutoAllowedActionBindingV1, RiskDecisionV1, TargetMerchantBindingV1, TrustedApprovalResultV1
from src.knowledge.schemas import ClaimVerificationBundleV1, EvidenceRefV1
from src.platform.context_projections import project_to_tool_context
from src.platform.trusted_context import TrustedContext
from src.tools.contracts import BusinessFactRefV1, ToolCallContext, ToolError, ToolResultV2
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
    "target_merchant_id",
    "business_fact_refs",
    "verified_evidence_refs",
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
    if route is not None and route != "allow":
        return True
    return _claim_bundle_blocks_action(state)


def _claim_verification_bundle(state: AgentState) -> dict[str, Any] | None:
    raw_bundle = state.get("claim_verification_bundle")
    if raw_bundle is None:
        return None
    if isinstance(raw_bundle, ClaimVerificationBundleV1):
        return raw_bundle.model_dump(mode="python")
    if isinstance(raw_bundle, dict):
        try:
            return ClaimVerificationBundleV1.model_validate(raw_bundle).model_dump(mode="python")
        except ValidationError:
            return {
                "overall_status": "error",
                "route": "final_response",
                "claim_results": [],
                "blocked_claims": ["malformed_claim_verification_bundle"],
                "safe_support_refs": [],
            }
    return {
        "overall_status": "error",
        "route": "final_response",
        "claim_results": [],
        "blocked_claims": ["malformed_claim_verification_bundle"],
        "safe_support_refs": [],
    }


def _claim_bundle_blocks_action(state: AgentState) -> bool:
    if not state.get("proposed_action"):
        return False
    bundle = _claim_verification_bundle(state)
    if bundle is None:
        return True
    if bundle.get("route") != "continue":
        return True
    if bundle.get("overall_status") not in {"verified", "not_required"}:
        return True
    if _non_empty_list(state.get("blocked_claims")) or _non_empty_list(bundle.get("blocked_claims")):
        return True
    return _action_claim_result_disallows_action(bundle)


def _action_claim_result_disallows_action(bundle: dict[str, Any]) -> bool:
    for raw_result in bundle.get("claim_results") or []:
        result = raw_result.model_dump(mode="python") if hasattr(raw_result, "model_dump") else raw_result
        if not isinstance(result, dict):
            continue
        claim_type = result.get("claim_type") or result.get("authority_class")
        if claim_type == "action_recommendation" and result.get("allows_action_recommendation") is False:
            return True
    return False


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


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
    if not _approval_phase34_binding_matches(state, trusted):
        return None
    return trusted


def _approval_phase34_binding_matches(state: AgentState, trusted: TrustedApprovalResultV1) -> bool:
    try:
        state_binding = _state_phase34_binding(state)
        trusted_binding = {
            "target_merchant_id": trusted.target_merchant_id,
            "target_merchant_ref": _canonical_target_merchant_ref(trusted.target_merchant_ref),
            "business_fact_refs": _canonical_business_fact_refs(trusted.business_fact_refs),
            "verified_evidence_refs": _canonical_evidence_refs(trusted.verified_evidence_refs),
            "claim_verification_ref": trusted.claim_verification_ref,
            "claim_verification_summary": _json_safe(trusted.claim_verification_summary),
            "risk_decision_ref": trusted.risk_decision_ref,
            "risk_decision": _canonical_risk_decision(trusted.risk_decision),
        }
    except (TypeError, ValueError, ValidationError):
        return False
    return _phase34_binding_matches(state_binding, trusted_binding)


def _trusted_auto_allowed_binding(
    state: AgentState,
    trusted_context: TrustedContext | None,
) -> dict[str, Any] | None:
    raw_binding = state.get("auto_allowed_binding")
    if not isinstance(raw_binding, dict):
        return None
    try:
        trusted = AutoAllowedActionBindingV1.model_validate(raw_binding)
    except ValidationError:
        return None
    if not trusted.risk_decision_ref:
        return None
    expected_tenant_id = trusted_context.tenant_id if trusted_context is not None else str(state.get("tenant_id") or "")
    expected_run_id = trusted_context.run_id if trusted_context is not None else str(state.get("current_run_id") or "")
    if str(trusted.tenant_id) != expected_tenant_id or str(trusted.run_id) != expected_run_id:
        return None
    try:
        state_binding = _state_phase34_binding(state)
        trusted_binding = {
            "target_merchant_id": trusted.target_merchant_id,
            "target_merchant_ref": state_binding["target_merchant_ref"],
            "business_fact_refs": _canonical_business_fact_refs(trusted.business_fact_refs),
            "verified_evidence_refs": _canonical_evidence_refs(trusted.verified_evidence_refs),
            "claim_verification_ref": trusted.claim_verification_ref,
            "claim_verification_summary": _json_safe(trusted.claim_verification_summary),
            "risk_decision_ref": trusted.risk_decision_ref,
            "risk_decision": state_binding["risk_decision"],
        }
    except (TypeError, ValueError, ValidationError):
        return None
    if not _phase34_binding_matches(state_binding, trusted_binding):
        return None
    if (
        trusted.action_payload_hash != state.get("action_payload_hash")
        or trusted.safety_snapshot_ref != state.get("safety_snapshot_ref")
        or trusted.safety_snapshot_hash != state.get("safety_snapshot_hash")
    ):
        return None
    return _json_safe(raw_binding)


def _phase34_binding_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["target_merchant_id"] != right["target_merchant_id"]:
        return False
    if left["target_merchant_ref"] != right["target_merchant_ref"]:
        return False
    if left["business_fact_refs"] != right["business_fact_refs"]:
        return False
    if left["verified_evidence_refs"] != right["verified_evidence_refs"]:
        return False
    claim_left = bool(left["claim_verification_ref"] or left["claim_verification_summary"])
    claim_right = bool(right["claim_verification_ref"] or right["claim_verification_summary"])
    if not (claim_left and claim_right):
        return False
    if left["claim_verification_ref"] != right["claim_verification_ref"] and (
        left["claim_verification_summary"] != right["claim_verification_summary"]
    ):
        return False
    risk_left = bool(left["risk_decision_ref"] or left["risk_decision"])
    risk_right = bool(right["risk_decision_ref"] or right["risk_decision"])
    if not (risk_left and risk_right):
        return False
    if left["risk_decision_ref"] != right["risk_decision_ref"] and left["risk_decision"] != right["risk_decision"]:
        return False
    return True


def _state_phase34_binding(state: AgentState) -> dict[str, Any]:
    return {
        "target_merchant_id": str(state.get("target_merchant_id") or "") or None,
        "target_merchant_ref": _canonical_target_merchant_ref(state.get("target_merchant_ref")),
        "business_fact_refs": _canonical_business_fact_refs(state.get("business_fact_refs")),
        "verified_evidence_refs": _canonical_evidence_refs(state.get("verified_evidence_refs")),
        "claim_verification_ref": str(state.get("claim_verification_ref") or "") or None,
        "claim_verification_summary": _json_safe(state.get("claim_verification_summary")),
        "risk_decision_ref": str(state.get("risk_decision_ref") or "") or None,
        "risk_decision": _canonical_risk_decision(state.get("risk_decision")),
    }


def _phase34_tool_args(state: AgentState, auto_allowed_binding: dict[str, Any] | None) -> dict[str, Any]:
    args = {
        "target_merchant_id": state.get("target_merchant_id"),
        "target_merchant_ref": _json_safe(state.get("target_merchant_ref")),
        "business_fact_refs": _json_safe_list(state.get("business_fact_refs")),
        "verified_evidence_refs": _json_safe_list(state.get("verified_evidence_refs")),
        "claim_verification_ref": state.get("claim_verification_ref"),
        "claim_verification_summary": _json_safe(state.get("claim_verification_summary")),
        "risk_decision_ref": state.get("risk_decision_ref"),
        "risk_decision": _json_safe(state.get("risk_decision")),
    }
    if auto_allowed_binding is not None:
        args["auto_allowed_binding"] = auto_allowed_binding
    return {key: value for key, value in args.items() if value is not None}


def _canonical_target_merchant_ref(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return TargetMerchantBindingV1.model_validate(_json_safe(value)).model_dump(mode="json")


def _canonical_business_fact_refs(value: Any) -> list[dict[str, Any]]:
    return [BusinessFactRefV1.model_validate(_json_safe(ref)).model_dump(mode="json") for ref in _list_value(value)]


def _canonical_evidence_refs(value: Any) -> list[dict[str, Any]]:
    return [EvidenceRefV1.model_validate(_json_safe(ref)).model_dump(mode="json") for ref in _list_value(value)]


def _canonical_risk_decision(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return RiskDecisionV1.model_validate(_json_safe(value)).model_dump(mode="json")


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _json_safe_list(value: Any) -> list[Any]:
    safe = _json_safe(value)
    return safe if isinstance(safe, list) else []


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items() if item is not None}
    if isinstance(value, datetime):
        return value.isoformat()
    return value


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
    auto_allowed_binding = None if approval_accepted else _trusted_auto_allowed_binding(state, trusted_context)

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
    if not approval_accepted and auto_allowed_binding is None:
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
        **_phase34_tool_args(state, auto_allowed_binding),
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
