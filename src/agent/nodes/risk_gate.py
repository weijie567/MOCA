from __future__ import annotations

import re
from hashlib import sha256
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import yaml
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.context import ContextAssembler, PromptAssembly
from src.agent.context.session_memory_bundle import load_session_prompt_context
from src.agent.prompts import ASSESS_RISK_SYSTEM
from src.agent.routing import _has_allowed_action_recommendation
from src.agent.schemas import RiskAssessment
from src.agent.state import AgentState
from src.agent.working_state import project_working_state
from src.approvals.snapshot_service import (
    ActionSafetySnapshotPersistenceError,
    compute_action_payload_hash,
    persist_action_safety_snapshot,
)
from src.approvals.snapshots import build_action_safety_snapshot
from src.approvals.schemas import PROPOSED_ACTION_SCHEMA_VERSION
from src.approvals.schemas import AutoAllowedActionBindingV1, RiskDecisionV1, TargetMerchantBindingV1
from src.approvals.schemas import TrustedApprovalResultV1
from src.config import settings
from src.knowledge.schemas import ClaimVerificationBundleV1, EvidenceRefV1, canonical_evidence_projection
from src.tools.contracts import BusinessFactRefV1

RISK_RULES_PATH = Path("rules/risk_rules.yaml")
POLICY_CONFIG_VERSION = "approval-policy.v1"
RISK_CONFIG_VERSION = "risk-rules.v1"
DEFAULT_RETRIEVAL_CONFIG_VERSION = "retrieval.v1"
SAFE_MANUAL_REVIEW_RESPONSE = "操作需要人工复核，当前未创建可执行审批或动作草稿。"
APPROVAL_DECISION_TYPES = ["accept", "approve", "edit", "respond", "reject", "ignore"]
FULL_REFUND_TERMS = ("full_refund", "全额退款", "全额退", "整单退款")
ACTIONABLE_ACTIONS = {
    "issue_coupon",
    "approve_refund",
    "full_refund",
    "partial_refund",
    "compensation",
    "manual_review",
}
NO_ACTION_RECOMMENDATIONS = {"insufficient_evidence", "citation_invalid", "retrieval_error"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.dashscope_api_key,
        openai_api_base=settings.embedding_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )


def _trace_step(
    status: str,
    started_at: str,
    provider_latency_ms: int | None = None,
    retry_count: int = 0,
    context_chars: int = 0,
    *,
    trace_node: str = "risk_gate",
) -> dict[str, Any]:
    return {
        "node": trace_node,
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "model_name": settings.llm_model,
        "prompt_tokens": None,
        "completion_tokens": None,
        "provider_latency_ms": provider_latency_ms,
        "retry_count": retry_count,
        "metrics_json": {
            "model": settings.llm_model,
            "provider": "dashscope",
            "context_chars": context_chars,
        },
    }


def _load_risk_rules() -> dict[str, Any]:
    with RISK_RULES_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _money_value(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _extract_compensation_amount(draft: dict[str, Any], context: dict[str, Any]) -> Decimal | None:
    for key in ("compensation_amount", "amount", "approved_amount", "requested_amount"):
        amount = _money_value(draft.get(key))
        if amount is not None:
            return amount

    text = " ".join(str(draft.get(key) or "") for key in ("recommended_action", "reasoning_summary"))
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:CNY|元|人民币)", text, flags=re.IGNORECASE)
    if match:
        return _money_value(match.group(1))

    refund_case = _business_context_resource(context, "refund_case")
    return _money_value(refund_case.get("approved_amount") or refund_case.get("requested_amount"))


def _rule_threshold(rule: dict[str, Any], operator: str) -> Decimal | None:
    pattern = rf"compensation_amount\s*{re.escape(operator)}\s*(\d+(?:\.\d+)?)"
    match = re.search(pattern, rule.get("condition", ""))
    return _money_value(match.group(1)) if match else None


def _deterministic_rule_match(
    draft: dict[str, Any], context: dict[str, Any], rules: dict[str, Any]
) -> dict[str, Any] | None:
    action = str(draft.get("recommended_action") or "")
    amount = _extract_compensation_amount(draft, context)
    order = _business_context_resource(context, "order")
    merchant_risk_level = context.get("merchant_risk_level") or order.get("merchant_risk_level")

    for rule in rules.get("high_risk") or []:
        condition = rule.get("condition", "")
        threshold = _rule_threshold(rule, ">")
        if threshold is not None and amount is not None and amount > threshold:
            return rule
        if (
            "full_refund" in condition
            and any(term in action for term in FULL_REFUND_TERMS)
            and order.get("status") == "delivered"
        ):
            return rule
        if "merchant_risk_level" in condition and merchant_risk_level == "high":
            return rule
    return None


def _is_actionable_recommendation(action: Any) -> bool:
    action_text = str(action or "").lower()
    return any(actionable in action_text for actionable in ACTIONABLE_ACTIONS)


def _verification_route(state: AgentState) -> str | None:
    rag_verification = state.get("rag_verification")
    if isinstance(rag_verification, dict):
        route = rag_verification.get("route")
        if isinstance(route, dict) and route.get("route"):
            return str(route["route"])
    route_value = state.get("verification_route")
    return str(route_value) if route_value else None


def _non_allow_verification(state: AgentState) -> bool:
    route = _verification_route(state)
    return route is not None and route != "allow"


def _action_requires_claim_bundle(state: AgentState, draft: dict[str, Any]) -> bool:
    if state.get("proposed_action"):
        return True
    action = draft.get("recommended_action")
    return action not in NO_ACTION_RECOMMENDATIONS and _is_actionable_recommendation(action)


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


def _claim_bundle_blocks_action(state: AgentState, draft: dict[str, Any]) -> bool:
    if not _action_requires_claim_bundle(state, draft):
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
    return not _has_allowed_action_recommendation(bundle)


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _action_gate_block_reason(state: AgentState, draft: dict[str, Any]) -> str | None:
    if _non_allow_verification(state):
        return "legacy_verifier_not_allow"
    if _claim_bundle_blocks_action(state, draft):
        return "claim_verification_not_allow"
    return None


def _blocked_verifier_risk(state: AgentState, reason_code: str | None = None) -> dict[str, Any]:
    route = _verification_route(state)
    risk_level = "manual_review" if route == "manual_review" else "blocked" if route == "refuse" else "low"
    reason = (
        "Claim verification did not allow action assessment."
        if reason_code == "claim_verification_not_allow"
        else "Recommendation verification did not allow action assessment."
    )
    return {
        "risk_level": risk_level,
        "risk_reason": reason,
        "approval_required": False,
        "rule_ref": "PHASE33-CLAIM-VERIFY" if reason_code == "claim_verification_not_allow" else "PHASE22-VERIFY",
    }


def _blocked_action_gate_state(
    state: AgentState,
    started_at: str,
    reason_code: str,
    *,
    trace_node: str = "risk_gate",
) -> dict[str, Any]:
    bundle = _claim_verification_bundle(state)
    return {
        "risk_assessment": _blocked_verifier_risk(state, reason_code),
        "proposed_action": None,
        "approval_plan": None,
        "approval_result": None,
        "action_draft": None,
        "draft_outcome": None,
        "action_result": None,
        "action_payload_hash": None,
        "safety_snapshot_ref": None,
        "safety_snapshot_hash": None,
        "safety_snapshot_verified": False,
        "auto_allowed": False,
        "rag_verification": state.get("rag_verification"),
        "claim_verification_bundle": state.get("claim_verification_bundle"),
        "blocked_claims": list(state.get("blocked_claims") or (bundle or {}).get("blocked_claims") or []),
        "safe_support_refs": list(state.get("safe_support_refs") or (bundle or {}).get("safe_support_refs") or []),
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("blocked", started_at, trace_node=trace_node)],
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


def _build_proposed_action(
    *,
    state: AgentState,
    draft: dict[str, Any],
    context: dict[str, Any],
    assessment: dict[str, Any],
    evidence_refs: list[EvidenceRefV1],
) -> dict[str, Any]:
    refund_case = _business_context_resource(context, "refund_case")
    order = _business_context_resource(context, "order")
    amount = _extract_compensation_amount(draft, context)
    action_type = _canonical_action_type(draft.get("recommended_action"))
    target_type, target_id = _action_target(refund_case=refund_case, order=order)
    run_id = str(state.get("current_run_id") or "")
    return {
        "schema_version": PROPOSED_ACTION_SCHEMA_VERSION,
        "tenant_id": str(state.get("tenant_id") or ""),
        "run_id": run_id,
        "action_id": str(draft.get("action_id") or f"act:{run_id}:{action_type}:{target_id}"),
        "action_type": action_type,
        "target_type": target_type,
        "target_id": target_id,
        "amount": _canonical_amount(amount),
        "currency": "CNY" if amount is not None else None,
        "args": {
            "risk_level": str(assessment.get("risk_level") or ""),
            "rule_ref": str(assessment.get("rule_ref") or ""),
        },
        "reason": str(draft.get("reasoning_summary") or assessment.get("risk_reason") or ""),
        "evidence_refs": canonical_evidence_projection(evidence_refs),
    }


def _trusted_edit_resume(
    state: AgentState,
    *,
    expected_resume_route: str = "risk_gate",
) -> TrustedApprovalResultV1 | None:
    raw_result = state.get("approval_result") or {}
    try:
        result = TrustedApprovalResultV1.model_validate(raw_result)
    except ValidationError:
        return None
    if (
        result.decision_type != "edit"
        or result.status != "superseded"
        or result.resume_route != expected_resume_route
        or not result.edited_action
        or not result.new_action_payload_hash
    ):
        return None
    if str(result.tenant_id) != str(state.get("tenant_id") or ""):
        return None
    if str(result.run_id) != str(state.get("current_run_id") or ""):
        return None
    if (
        result.action_payload_hash != state.get("action_payload_hash")
        or result.safety_snapshot_ref != state.get("safety_snapshot_ref")
        or result.safety_snapshot_hash != state.get("safety_snapshot_hash")
    ):
        return None
    return result


def _draft_from_trusted_edit(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "recommended_action": action.get("action_type") or "manual_review",
        "reasoning_summary": action.get("reason") or "Reviewer edited the proposed action.",
        "compensation_amount": action.get("amount"),
        "risk_level": (action.get("args") or {}).get("risk_level"),
        "action_id": action.get("action_id"),
    }


def _canonical_trusted_edit_action(
    *,
    state: AgentState,
    trusted_edit: TrustedApprovalResultV1,
    evidence_refs: list[EvidenceRefV1],
) -> dict[str, Any]:
    action = dict(trusted_edit.edited_action or {})
    if str(action.get("tenant_id") or "") != str(state.get("tenant_id") or ""):
        raise ValueError("edited action tenant mismatch")
    if str(action.get("run_id") or "") != str(state.get("current_run_id") or ""):
        raise ValueError("edited action run mismatch")
    action["evidence_refs"] = canonical_evidence_projection(evidence_refs)
    action_payload_hash = compute_action_payload_hash(action)
    if action_payload_hash != trusted_edit.new_action_payload_hash:
        raise ValueError("edited action hash mismatch")
    return action


def _action_target(*, refund_case: dict[str, Any], order: dict[str, Any]) -> tuple[str, str]:
    refund_id = refund_case.get("id") or refund_case.get("refund_case_id") or refund_case.get("refund_case_no")
    if refund_id:
        return "refund_case", str(refund_id)
    order_id = order.get("id") or order.get("order_id") or order.get("order_no")
    if order_id:
        return "order", str(order_id)
    return "unknown", "unknown"


def _canonical_amount(amount: Decimal | None) -> str | None:
    if amount is None:
        return None
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def _fixed_millisecond_now() -> datetime:
    now = datetime.now(UTC)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def _normalize_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    normalized = parsed.astimezone(UTC)
    normalized = normalized.replace(microsecond=(normalized.microsecond // 1000) * 1000)
    return normalized.strftime("%Y-%m-%dT%H:%M:%S.") + f"{normalized.microsecond // 1000:03d}Z"


def _evidence_refs_from_state(state: AgentState, draft: dict[str, Any]) -> list[EvidenceRefV1]:
    candidates = _safe_support_ref_candidates(state)
    if not candidates:
        raise ValueError("missing safe_support_refs")

    refs: list[EvidenceRefV1] = []
    evidence_map = _verified_evidence_map(state)
    for candidate in candidates:
        item = _evidence_ref_item(candidate, evidence_map)
        if item is None:
            continue
        if isinstance(item.get("retrieved_at"), str):
            item["retrieved_at"] = _normalize_timestamp(item["retrieved_at"])
        refs.append(EvidenceRefV1.model_validate(item))
    if not refs:
        raise ValueError("missing safe_support_refs")
    return refs


def _safe_support_ref_candidates(state: AgentState) -> list[Any]:
    bundle = _claim_verification_bundle(state)
    for value in ((bundle or {}).get("safe_support_refs"), state.get("safe_support_refs")):
        if isinstance(value, list) and value:
            return value
    return []


def _verified_evidence_map(state: AgentState) -> dict[str, Any]:
    refs: dict[str, Any] = {}
    for raw_map in (_package_evidence_map(state.get("verified_evidence_package")), state.get("evidence_map")):
        if not isinstance(raw_map, dict):
            continue
        for key, value in raw_map.items():
            evidence_id = _evidence_id(value) or str(key)
            refs[evidence_id] = value
    return refs


def _package_evidence_map(package: Any) -> dict[str, Any]:
    if hasattr(package, "evidence_map"):
        return dict(package.evidence_map)
    if isinstance(package, dict) and isinstance(package.get("evidence_map"), dict):
        return package["evidence_map"]
    return {}


def _evidence_id(value: Any) -> str | None:
    if isinstance(value, EvidenceRefV1):
        return value.evidence_id
    if isinstance(value, dict) and isinstance(value.get("evidence_id"), str):
        return value["evidence_id"]
    return None


def _evidence_ref_item(candidate: Any, evidence_map: dict[str, Any]) -> dict[str, Any] | None:
    value = evidence_map.get(candidate) if isinstance(candidate, str) else candidate
    if isinstance(value, EvidenceRefV1):
        return value.model_dump()
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else None
    if isinstance(value, dict):
        return dict(value)
    return None


def _business_fact_refs_from_state(state: AgentState) -> list[BusinessFactRefV1]:
    context = state.get("business_context") or {}
    raw_refs: list[Any] = []
    raw_refs.extend(context.get("business_fact_refs") or [])
    for result in context.get("business_fact_results") or []:
        if isinstance(result, dict):
            raw_refs.extend(result.get("business_fact_refs") or [])

    bundle = _claim_verification_bundle(state) or {}
    for raw_result in bundle.get("claim_results") or []:
        result = raw_result.model_dump(mode="python") if hasattr(raw_result, "model_dump") else raw_result
        if isinstance(result, dict):
            raw_refs.extend(result.get("business_fact_refs") or [])

    refs: list[BusinessFactRefV1] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for raw_ref in raw_refs:
        ref = raw_ref if isinstance(raw_ref, BusinessFactRefV1) else BusinessFactRefV1.model_validate(raw_ref)
        key = (ref.tenant_id, ref.source_system, ref.resource_type, ref.resource_id)
        if key in seen:
            continue
        seen.add(key)
        refs.append(ref)
    return refs


def _target_merchant_binding(
    *,
    context: dict[str, Any],
    proposed_action: dict[str, Any],
    business_fact_refs: list[BusinessFactRefV1],
) -> TargetMerchantBindingV1 | None:
    target_id = str(proposed_action.get("target_id") or "")
    if not target_id:
        return None

    merchant_candidates: list[tuple[str, str]] = []
    for resource_type in ("refund_case", "order", "ticket"):
        resource = _business_context_resource(context, resource_type)
        if not resource:
            continue
        resource_id = _business_resource_id(resource_type, resource)
        merchant_id = resource.get("merchant_id")
        if resource_id == target_id and merchant_id:
            merchant_candidates.append((str(merchant_id), resource_type))

    merchant_ids = {merchant_id for merchant_id, _resource_type in merchant_candidates}
    if len(merchant_ids) != 1:
        return None

    supporting_ref = _supporting_business_fact_ref(
        business_fact_refs=business_fact_refs,
        resource_types={resource_type for _merchant_id, resource_type in merchant_candidates},
        target_id=target_id,
    )
    if supporting_ref is None:
        return None

    return TargetMerchantBindingV1(
        target_merchant_id=next(iter(merchant_ids)),
        source="business_fact_ref",
        business_fact_ref=supporting_ref.model_dump(mode="json"),
    )


def _business_context_resource(context: dict[str, Any], resource_type: str) -> dict[str, Any]:
    resource = context.get(resource_type)
    if isinstance(resource, dict):
        return resource
    facts = context.get("facts")
    if isinstance(facts, dict):
        nested = facts.get(resource_type)
        if isinstance(nested, dict):
            return nested
    return {}


def _business_resource_id(resource_type: str, resource: dict[str, Any]) -> str | None:
    keys_by_type = {
        "refund_case": ("id", "refund_case_id", "refund_case_no"),
        "order": ("id", "order_id", "order_no"),
        "ticket": ("id", "ticket_id", "ticket_no"),
    }
    for key in keys_by_type[resource_type]:
        value = resource.get(key)
        if value:
            return str(value)
    return None


def _supporting_business_fact_ref(
    *,
    business_fact_refs: list[BusinessFactRefV1],
    resource_types: set[str],
    target_id: str,
) -> BusinessFactRefV1 | None:
    for ref in business_fact_refs:
        if ref.resource_type in resource_types and ref.resource_id == target_id:
            return ref
    return None


def _claim_verification_summary(state: AgentState) -> dict[str, Any] | None:
    bundle = _claim_verification_bundle(state)
    if bundle is None:
        return None
    return {
        "overall_status": bundle.get("overall_status"),
        "route": bundle.get("route"),
        "safe_support_ref_count": len(bundle.get("safe_support_refs") or []),
        "blocked_claim_count": len(bundle.get("blocked_claims") or []),
        "reason_codes": sorted(str(code) for code in bundle.get("reason_codes") or []),
    }


def _risk_reason_codes(assessment: dict[str, Any], state: AgentState) -> list[str]:
    reason_codes = {str(code) for code in (_claim_verification_summary(state) or {}).get("reason_codes") or []}
    for key in ("risk_level", "rule_ref"):
        value = assessment.get(key)
        if value:
            reason_codes.add(str(value))
    if assessment.get("approval_required") is True:
        reason_codes.add("approval_required")
    if assessment.get("approval_required") is False:
        reason_codes.add("auto_allowed_candidate")
    return sorted(reason_codes)


def _risk_decision(
    *,
    state: AgentState,
    proposed_action: dict[str, Any],
    assessment: dict[str, Any],
    action_payload_hash: str,
) -> RiskDecisionV1:
    return RiskDecisionV1(
        tenant_id=str(state.get("tenant_id") or ""),
        run_id=str(state.get("current_run_id") or ""),
        action_id=str(proposed_action.get("action_id") or ""),
        action_payload_hash=action_payload_hash,
        risk_level=str(assessment.get("risk_level") or ""),
        reason_codes=_risk_reason_codes(assessment, state),
        policy_config_version=POLICY_CONFIG_VERSION,
        risk_config_version=RISK_CONFIG_VERSION,
        approval_required=assessment.get("approval_required") is True,
        evaluated_at=_now_iso(),
        risk_rule_ref=str(assessment.get("rule_ref")) if assessment.get("rule_ref") else None,
        risk_reason=str(assessment.get("risk_reason")) if assessment.get("risk_reason") else None,
    )


def _stable_idempotency_key(prefix: str, raw_material: str) -> str:
    if len(raw_material) <= 256:
        return raw_material
    return f"{prefix}:{sha256(raw_material.encode('utf-8')).hexdigest()}"


def _approval_idempotency_key(
    *,
    state: AgentState,
    proposed_action: dict[str, Any],
    action_payload_hash: str,
    safety_snapshot_hash: str,
    risk_decision_ref: str,
) -> str:
    raw_material = ":".join(
        [
            "approval",
            str(state.get("tenant_id") or ""),
            str(state.get("current_run_id") or ""),
            str(proposed_action.get("action_type") or ""),
            str(proposed_action.get("target_id") or ""),
            action_payload_hash,
            safety_snapshot_hash,
            risk_decision_ref,
        ]
    )
    return _stable_idempotency_key("approval", raw_material)


def _auto_allowed_idempotency_key(
    *,
    state: AgentState,
    proposed_action: dict[str, Any],
    action_payload_hash: str,
    safety_snapshot_hash: str,
    risk_decision_ref: str,
) -> str:
    raw_material = ":".join(
        [
            "auto_allowed",
            str(state.get("tenant_id") or ""),
            str(state.get("current_run_id") or ""),
            str(proposed_action.get("action_type") or ""),
            str(proposed_action.get("target_id") or ""),
            action_payload_hash,
            safety_snapshot_hash,
            risk_decision_ref,
        ]
    )
    return _stable_idempotency_key("auto_allowed", raw_material)


def _approval_plan(
    *,
    assessment: dict[str, Any],
    action_payload_hash: str,
    safety_snapshot_ref: str,
    safety_snapshot_hash: str,
    target_merchant_ref: TargetMerchantBindingV1,
    business_fact_refs: list[BusinessFactRefV1],
    verified_evidence_refs: list[EvidenceRefV1],
    claim_verification_summary: dict[str, Any] | None,
    risk_decision_ref: str,
    risk_decision: RiskDecisionV1,
    approval_idempotency_key: str,
) -> dict[str, Any]:
    return {
        "schema_version": "approval_plan.v1",
        "approval_required": assessment.get("approval_required") is True,
        "policy_id": "default-approval-policy",
        "policy_version": POLICY_CONFIG_VERSION,
        "action_payload_hash": action_payload_hash,
        "safety_snapshot_ref": safety_snapshot_ref,
        "safety_snapshot_hash": safety_snapshot_hash,
        "risk_decision_ref": risk_decision_ref,
        "risk_decision": risk_decision.model_dump(mode="json"),
        "approval_idempotency_key": approval_idempotency_key,
        "target_merchant_id": target_merchant_ref.target_merchant_id,
        "target_merchant_ref": target_merchant_ref.model_dump(mode="json"),
        "business_fact_refs": [ref.model_dump(mode="json") for ref in business_fact_refs],
        "verified_evidence_refs": [ref.model_dump(mode="json") for ref in verified_evidence_refs],
        "claim_verification_ref": None,
        "claim_verification_summary": claim_verification_summary,
        "allowed_decision_types": APPROVAL_DECISION_TYPES,
    }


def _auto_allowed_binding(
    *,
    state: AgentState,
    target_merchant_ref: TargetMerchantBindingV1,
    business_fact_refs: list[BusinessFactRefV1],
    verified_evidence_refs: list[EvidenceRefV1],
    claim_verification_summary: dict[str, Any] | None,
    action_payload_hash: str,
    safety_snapshot_ref: str,
    safety_snapshot_hash: str,
    risk_decision_ref: str,
    idempotency_key: str,
) -> AutoAllowedActionBindingV1 | None:
    try:
        return AutoAllowedActionBindingV1(
            tenant_id=str(state.get("tenant_id") or ""),
            run_id=str(state.get("current_run_id") or ""),
            target_merchant_id=target_merchant_ref.target_merchant_id,
            action_payload_hash=action_payload_hash,
            safety_snapshot_ref=safety_snapshot_ref,
            safety_snapshot_hash=safety_snapshot_hash,
            risk_decision_ref=risk_decision_ref,
            idempotency_key=idempotency_key,
            business_fact_refs=business_fact_refs,
            verified_evidence_refs=verified_evidence_refs,
            claim_verification_ref=None,
            claim_verification_summary=claim_verification_summary,
        )
    except ValidationError:
        return None


def _phase34_fail_closed_result(
    result: dict[str, Any],
    assessment: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    safe_assessment = {
        **assessment,
        "approval_required": False,
        "blocked": True,
        "risk_level": "manual_review",
        "risk_reason": reason,
    }
    return {
        **result,
        "risk_assessment": safe_assessment,
        "proposed_action": None,
        "approval_plan": None,
        "risk_decision": None,
        "risk_decision_ref": None,
        "target_merchant_id": None,
        "target_merchant_ref": None,
        "business_fact_refs": [],
        "verified_evidence_refs": [],
        "claim_verification_ref": None,
        "claim_verification_summary": None,
        "approval_idempotency_key": None,
        "auto_allowed_binding": None,
        "auto_allowed": False,
        "action_payload_hash": None,
        "safety_snapshot_ref": None,
        "safety_snapshot_hash": None,
        "safety_snapshot_verified": False,
        "final_response": SAFE_MANUAL_REVIEW_RESPONSE,
    }


def _attach_phase34_binding_state(
    *,
    state: AgentState,
    result: dict[str, Any],
    proposed_action: dict[str, Any],
    assessment: dict[str, Any],
    context: dict[str, Any],
    action_payload_hash: str,
    safety_snapshot_ref: str,
    safety_snapshot_hash: str,
    evidence_refs: list[EvidenceRefV1],
) -> dict[str, Any]:
    business_fact_refs = _business_fact_refs_from_state(state)
    target_merchant_ref = _target_merchant_binding(
        context=context,
        proposed_action=proposed_action,
        business_fact_refs=business_fact_refs,
    )
    if target_merchant_ref is None:
        return _phase34_fail_closed_result(
            result,
            assessment,
            reason="Target merchant binding could not be verified from business facts.",
        )

    risk_decision = _risk_decision(
        state=state,
        proposed_action=proposed_action,
        assessment=assessment,
        action_payload_hash=action_payload_hash,
    )
    risk_decision_ref = f"risk_decision:{str(state.get('current_run_id') or '')}:{action_payload_hash}"
    approval_idempotency_key = _approval_idempotency_key(
        state=state,
        proposed_action=proposed_action,
        action_payload_hash=action_payload_hash,
        safety_snapshot_hash=safety_snapshot_hash,
        risk_decision_ref=risk_decision_ref,
    )
    claim_summary = _claim_verification_summary(state)
    approval_plan = _approval_plan(
        assessment=assessment,
        action_payload_hash=action_payload_hash,
        safety_snapshot_ref=safety_snapshot_ref,
        safety_snapshot_hash=safety_snapshot_hash,
        target_merchant_ref=target_merchant_ref,
        business_fact_refs=business_fact_refs,
        verified_evidence_refs=evidence_refs,
        claim_verification_summary=claim_summary,
        risk_decision_ref=risk_decision_ref,
        risk_decision=risk_decision,
        approval_idempotency_key=approval_idempotency_key,
    )
    auto_allowed_binding: dict[str, Any] | None = None
    if assessment.get("approval_required") is False:
        binding = _auto_allowed_binding(
            state=state,
            target_merchant_ref=target_merchant_ref,
            business_fact_refs=business_fact_refs,
            verified_evidence_refs=evidence_refs,
            claim_verification_summary=claim_summary,
            action_payload_hash=action_payload_hash,
            safety_snapshot_ref=safety_snapshot_ref,
            safety_snapshot_hash=safety_snapshot_hash,
            risk_decision_ref=risk_decision_ref,
            idempotency_key=_auto_allowed_idempotency_key(
                state=state,
                proposed_action=proposed_action,
                action_payload_hash=action_payload_hash,
                safety_snapshot_hash=safety_snapshot_hash,
                risk_decision_ref=risk_decision_ref,
            ),
        )
        auto_allowed_binding = binding.model_dump(mode="json") if binding else None

    return {
        **result,
        "risk_assessment": assessment,
        "proposed_action": proposed_action,
        "action_payload_hash": action_payload_hash,
        "safety_snapshot_ref": safety_snapshot_ref,
        "safety_snapshot_hash": safety_snapshot_hash,
        "target_merchant_id": target_merchant_ref.target_merchant_id,
        "target_merchant_ref": target_merchant_ref.model_dump(mode="json"),
        "business_fact_refs": [ref.model_dump(mode="json") for ref in business_fact_refs],
        "verified_evidence_refs": [ref.model_dump(mode="json") for ref in evidence_refs],
        "claim_verification_ref": None,
        "claim_verification_summary": claim_summary,
        "risk_decision_ref": risk_decision_ref,
        "risk_decision": risk_decision.model_dump(mode="json"),
        "approval_idempotency_key": approval_idempotency_key,
        "approval_plan": approval_plan,
        "auto_allowed_binding": auto_allowed_binding,
    }


def _allow_ephemeral_snapshot_binding(state: AgentState, config: RunnableConfig | None) -> bool:
    """Allow direct risk-node unit calls to keep deterministic risk output without DB state."""

    return config is None and not state.get("current_run_id")


async def _attach_snapshot_binding(
    state: AgentState,
    result: dict[str, Any],
    *,
    assessment: dict[str, Any],
    draft: dict[str, Any],
    context: dict[str, Any],
    config: RunnableConfig | None,
    trusted_edit: TrustedApprovalResultV1 | None = None,
    trace_node: str = "risk_gate",
    persist_snapshot=None,
) -> dict[str, Any]:
    if not result.get("proposed_action"):
        return result

    try:
        try:
            evidence_refs = _evidence_refs_from_state(state, draft)
        except ValueError:
            if not _allow_ephemeral_snapshot_binding(state, config):
                raise
            evidence_refs = []
        if trusted_edit is not None:
            proposed_action = _canonical_trusted_edit_action(
                state=state,
                trusted_edit=trusted_edit,
                evidence_refs=evidence_refs,
            )
        else:
            proposed_action = _build_proposed_action(
                state=state,
                draft=draft,
                context=context,
                assessment=assessment,
                evidence_refs=evidence_refs,
            )
        action_payload_hash = compute_action_payload_hash(proposed_action)
        try:
            business_fact_refs = _business_fact_refs_from_state(state)
        except ValidationError as exc:
            return _phase34_fail_closed_result(
                result,
                assessment,
                reason=f"Business fact binding could not be verified: {exc}",
            )
        target_merchant_ref = _target_merchant_binding(
            context=context,
            proposed_action=proposed_action,
            business_fact_refs=business_fact_refs,
        )
        if target_merchant_ref is None:
            return _phase34_fail_closed_result(
                result,
                assessment,
                reason="Target merchant binding could not be verified from business facts.",
            )
        session = (config or {}).get("configurable", {}).get("session") if config else None
        if session is None and _allow_ephemeral_snapshot_binding(state, config):
            snapshot_id = str(uuid5(NAMESPACE_URL, action_payload_hash))
            snapshot = build_action_safety_snapshot(
                tenant_id=str(state.get("tenant_id") or ""),
                run_id=str(state.get("current_run_id") or ""),
                snapshot_id=snapshot_id,
                snapshot_ref=f"snapshot:ephemeral:{snapshot_id}",
                policy_config_version=POLICY_CONFIG_VERSION,
                risk_config_version=RISK_CONFIG_VERSION,
                retrieval_config_version=_retrieval_config_version(evidence_refs),
                evidence=evidence_refs,
                action_payload_hash=action_payload_hash,
                target_merchant_id=target_merchant_ref.target_merchant_id,
                target_merchant_ref=target_merchant_ref,
                business_fact_refs=business_fact_refs,
                created_at=_fixed_millisecond_now(),
            )
            snapshot_result = {
                **result,
                "risk_assessment": assessment,
                "proposed_action": proposed_action,
                "action_payload_hash": action_payload_hash,
                "safety_snapshot_ref": snapshot.snapshot_ref,
                "safety_snapshot_hash": snapshot.immutable_hash,
                "safety_snapshot_verified": True,
                "safety_snapshot_persistence": "ephemeral",
                "auto_allowed": assessment.get("approval_required") is False,
                "policy_config_version": POLICY_CONFIG_VERSION,
                "risk_config_version": RISK_CONFIG_VERSION,
                "retrieval_config_version": _retrieval_config_version(evidence_refs),
                "evidence_refs": [ref.model_dump(mode="json") for ref in evidence_refs],
            }
            return _attach_phase34_binding_state(
                state=state,
                result=snapshot_result,
                proposed_action=proposed_action,
                assessment=assessment,
                context=context,
                action_payload_hash=action_payload_hash,
                safety_snapshot_ref=snapshot.snapshot_ref,
                safety_snapshot_hash=snapshot.immutable_hash,
                evidence_refs=evidence_refs,
            )
        if session is None:
            raise ActionSafetySnapshotPersistenceError("session unavailable for snapshot persistence")

        run_id = UUID(str(state.get("current_run_id")))
        tenant_id = UUID(str(state.get("tenant_id")))
        user_id = UUID(str(state.get("user_id")))
        snapshot_writer = persist_snapshot or persist_action_safety_snapshot
        snapshot = await snapshot_writer(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            proposed_action=proposed_action,
            action_payload_hash=action_payload_hash,
            policy_config_version=POLICY_CONFIG_VERSION,
            risk_config_version=RISK_CONFIG_VERSION,
            retrieval_config_version=_retrieval_config_version(evidence_refs),
            evidence_refs=evidence_refs,
            target_merchant_id=target_merchant_ref.target_merchant_id,
            target_merchant_ref=target_merchant_ref.model_dump(mode="json"),
            business_fact_refs=[ref.model_dump(mode="json") for ref in business_fact_refs],
            created_at=_fixed_millisecond_now(),
            created_by=user_id,
        )
    except (ActionSafetySnapshotPersistenceError, TypeError, ValueError, ValidationError) as exc:
        safe_assessment = {
            **assessment,
            "approval_required": False,
            "risk_level": "manual_review",
            "risk_reason": f"Action safety snapshot could not be verified: {exc}",
        }
        return {
            **result,
            "risk_assessment": safe_assessment,
            "proposed_action": None,
            "approval_plan": None,
            "risk_decision": None,
            "risk_decision_ref": None,
            "target_merchant_id": None,
            "target_merchant_ref": None,
            "business_fact_refs": [],
            "verified_evidence_refs": [],
            "claim_verification_ref": None,
            "claim_verification_summary": None,
            "approval_idempotency_key": None,
            "auto_allowed_binding": None,
            "auto_allowed": False,
            "safety_snapshot_verified": False,
            "final_response": SAFE_MANUAL_REVIEW_RESPONSE,
            "node_errors": (state.get("node_errors") or []) + [{"node": trace_node, "error": str(exc)}],
        }

    snapshot_result = {
        **result,
        "risk_assessment": assessment,
        "proposed_action": proposed_action,
        "action_payload_hash": snapshot.action_payload_hash,
        "safety_snapshot_ref": snapshot.safety_snapshot_ref,
        "safety_snapshot_hash": snapshot.safety_snapshot_hash,
        "safety_snapshot_verified": True,
        "auto_allowed": assessment.get("approval_required") is False,
        "policy_config_version": POLICY_CONFIG_VERSION,
        "risk_config_version": RISK_CONFIG_VERSION,
        "retrieval_config_version": _retrieval_config_version(evidence_refs),
        "evidence_refs": [ref.model_dump(mode="json") for ref in evidence_refs],
    }
    return _attach_phase34_binding_state(
        state=state,
        result=snapshot_result,
        proposed_action=proposed_action,
        assessment=assessment,
        context=context,
        action_payload_hash=snapshot.action_payload_hash,
        safety_snapshot_ref=snapshot.safety_snapshot_ref,
        safety_snapshot_hash=snapshot.safety_snapshot_hash,
        evidence_refs=evidence_refs,
    )


def _retrieval_config_version(evidence_refs: list[EvidenceRefV1]) -> str:
    if evidence_refs:
        return evidence_refs[0].retrieval_config_version
    return DEFAULT_RETRIEVAL_CONFIG_VERSION


def _fallback_risk(draft: dict[str, Any], context: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    if draft.get("recommended_action") == "insufficient_evidence":
        return {
            "risk_level": "low",
            "risk_reason": "No action is recommended because evidence is insufficient.",
            "approval_required": False,
            "rule_ref": "LR-01",
        }

    high_rule = _deterministic_rule_match(draft, context, rules)
    if high_rule:
        return {
            "risk_level": "high",
            "risk_reason": high_rule.get("description") or "High risk rule matched.",
            "approval_required": True,
            "rule_ref": high_rule.get("id"),
        }

    low_rule = (rules.get("low_risk") or [{}])[0]
    return {
        "risk_level": "low",
        "risk_reason": low_rule.get("description") or "No high risk rule matched.",
        "approval_required": False,
        "rule_ref": low_rule.get("id"),
    }


async def risk_gate(state: AgentState, config: RunnableConfig = None) -> dict:
    """Canonical risk/action graph node."""
    started_at = _now_iso()
    rules = _load_risk_rules()
    trusted_edit = _trusted_edit_resume(state)
    draft = (
        _draft_from_trusted_edit(trusted_edit.edited_action)
        if trusted_edit is not None
        else state.get("recommendation_draft") or {}
    )
    context = state.get("business_context") or {}

    block_reason = _action_gate_block_reason(state, draft)
    if block_reason is not None:
        return _blocked_action_gate_state(state, started_at, block_reason)

    if draft.get("recommended_action") in NO_ACTION_RECOMMENDATIONS:
        assessment = _fallback_risk(draft, context, rules)
        return {
            "risk_assessment": assessment,
            "proposed_action": None,
            "trace_steps": (state.get("trace_steps") or [])
            + [_trace_step("completed", started_at)],
        }
    if state.get("current_intent") == "policy_qa":
        low_rule = (rules.get("low_risk") or [{}])[0]
        return {
            "risk_assessment": {
                "risk_level": "low",
                "risk_reason": low_rule.get("description") or "Policy explanation only; no customer action proposed.",
                "approval_required": False,
                "rule_ref": low_rule.get("id"),
            },
            "proposed_action": None,
            "trace_steps": (state.get("trace_steps") or [])
            + [_trace_step("completed", started_at)],
        }

    prompt_assembly = await _assemble_risk_prompt(
        state=state,
        config=config,
        rules=rules,
        draft=draft,
        context=context,
    )
    messages = prompt_assembly.to_messages()
    structured_llm = _get_llm().with_structured_output(RiskAssessment)
    last_error: str | None = None
    provider_latency_ms: int | None = None
    retry_count = 0

    # retry_count records this node's manual structured-output retry loop, not LangGraph node retries.
    for attempt in range(2):
        retry_count = attempt
        try:
            t0 = time.perf_counter()
            result = await structured_llm.ainvoke(messages)
            provider_latency_ms = round((time.perf_counter() - t0) * 1000)
            assessment = result.model_dump()
            high_rule = _deterministic_rule_match(draft, context, rules)
            if high_rule:
                assessment.update(
                    {
                        "risk_level": "high",
                        "risk_reason": high_rule.get("description") or assessment["risk_reason"],
                        "approval_required": True,
                        "rule_ref": high_rule.get("id"),
                    }
                )
            proposed_action = (
                {"pending_snapshot": True}
                if draft.get("recommended_action") not in NO_ACTION_RECOMMENDATIONS
                and (
                    assessment.get("approval_required")
                    or _is_actionable_recommendation(draft.get("recommended_action"))
                )
                else None
            )
            outputs = {**(state.get("llm_outputs") or {}), "risk_gate": assessment}
            result = {
                "risk_assessment": assessment,
                "proposed_action": proposed_action,
                "llm_outputs": outputs,
                "trace_steps": (state.get("trace_steps") or [])
                + [
                    _trace_step(
                        "completed",
                        started_at,
                        provider_latency_ms,
                        retry_count,
                        _messages_chars(messages),
                    )
                ],
            }
            return await _attach_snapshot_binding(
                state,
                result,
                assessment=assessment,
                draft=draft,
                context=context,
                config=config,
                trusted_edit=trusted_edit,
            )
        except (ValidationError, ValueError, TimeoutError) as exc:
            provider_latency_ms = round((time.perf_counter() - t0) * 1000)
            last_error = str(exc)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Validation failed: {last_error}. Respond with valid JSON.",
                    }
                )

    fallback_assessment = _fallback_risk(draft, context, rules)
    proposed_action = (
        {"pending_snapshot": True}
        if draft.get("recommended_action") not in NO_ACTION_RECOMMENDATIONS
        and (
            fallback_assessment.get("approval_required")
            or _is_actionable_recommendation(draft.get("recommended_action"))
        )
        else None
    )
    result = {
        "risk_assessment": fallback_assessment,
        "proposed_action": proposed_action,
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "risk_gate", "error": last_error, "retry_count": 2}],
        "trace_steps": (state.get("trace_steps") or [])
        + [
            _trace_step(
                "error",
                started_at,
                provider_latency_ms,
                retry_count,
                _messages_chars(messages),
            )
        ],
    }
    return await _attach_snapshot_binding(
        state,
        result,
        assessment=fallback_assessment,
        draft=draft,
        context=context,
        config=config,
        trusted_edit=trusted_edit,
    )


async def _assemble_risk_prompt(
    *,
    state: AgentState,
    config: RunnableConfig | None,
    rules: dict[str, Any],
    draft: dict[str, Any],
    context: dict[str, Any],
) -> PromptAssembly:
    prompt_context = await load_session_prompt_context(state, config)
    return ContextAssembler().assemble(
        system_prompt=ASSESS_RISK_SYSTEM,
        current_user_message=str(state.get("user_query") or ""),
        working_state=project_working_state(state),
        thread_rolling_summary=prompt_context["thread_rolling_summary"],
        recent_messages=prompt_context["recent_messages"],
        verified_policy_snippets=_policy_refs_from_state(state, draft),
        profile_memory_snippets=state.get("long_term_memory") or [],
        case_memory_snippets=state.get("case_memory") or [],
        tool_result_summaries=[
            *prompt_context["tool_result_summaries"],
            *(state.get("tool_results") or []),
        ],
        business_context=context,
        memory_context_bundle=state.get("memory_context_bundle") or state.get("session_context_bundle"),
        node_hints=[
            _risk_rules_summary(rules),
            _recommendation_summary(draft),
            "Assess whether the recommendation needs approval. Use only projected business context and policy refs.",
        ],
    )


def _risk_rules_summary(rules: dict[str, Any]) -> str:
    lines: list[str] = ["Risk rules summary:"]
    for group in ("high_risk", "low_risk"):
        for rule in rules.get(group) or []:
            if not isinstance(rule, dict):
                continue
            parts = [
                f"group={group}",
                f"id={rule.get('id')}",
                f"condition={rule.get('condition')}",
                f"description={rule.get('description')}",
            ]
            lines.append("; ".join(str(part) for part in parts if part and not str(part).endswith("=None")))
    return "\n".join(lines)


def _recommendation_summary(draft: dict[str, Any]) -> str:
    fields = []
    for key in ("recommended_action", "reasoning_summary", "confidence", "risk_level"):
        value = draft.get(key)
        if value is not None:
            fields.append(f"{key}={value}")
    missing_info = draft.get("missing_info")
    if isinstance(missing_info, list) and missing_info:
        fields.append("missing_info=" + "; ".join(str(item) for item in missing_info if item))
    evidence_ids = [
        str(item.get("evidence_id") or f"{item.get('doc_key')}:{item.get('chunk_id')}")
        for item in draft.get("evidence_refs") or []
        if isinstance(item, dict)
    ]
    if evidence_ids:
        fields.append("evidence_refs=" + ", ".join(evidence_ids))
    return "Recommendation summary: " + "; ".join(fields)


def _policy_refs_from_state(state: AgentState, draft: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    evidence_map = _verified_evidence_map(state)
    for item in _safe_support_ref_candidates(state):
        mapping = _evidence_ref_item(item, evidence_map)
        if isinstance(mapping, dict):
            refs.append(
                {
                    "evidence_id": mapping.get("evidence_id"),
                    "doc_key": mapping.get("doc_key"),
                    "chunk_id": mapping.get("chunk_id"),
                    "policy_version": mapping.get("policy_version"),
                }
            )
    return refs


def _messages_chars(messages: list[dict[str, str]]) -> int:
    return sum(len(message.get("content") or "") for message in messages)
