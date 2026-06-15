from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.prompts import ASSESS_RISK_SYSTEM
from src.agent.schemas import RiskAssessment
from src.agent.state import AgentState
from src.approvals.snapshot_service import (
    ActionSafetySnapshotPersistenceError,
    compute_action_payload_hash,
    persist_action_safety_snapshot,
)
from src.approvals.schemas import PROPOSED_ACTION_SCHEMA_VERSION
from src.config import settings
from src.knowledge.schemas import EvidenceRefV1, canonical_evidence_projection

RISK_RULES_PATH = Path("rules/risk_rules.yaml")
POLICY_CONFIG_VERSION = "approval-policy.v1"
RISK_CONFIG_VERSION = "risk-rules.v1"
DEFAULT_RETRIEVAL_CONFIG_VERSION = "retrieval.v1"
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
) -> dict[str, Any]:
    return {
        "node": "assess_risk_and_approval",
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

    refund_case = context.get("refund_case") or {}
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
    order = context.get("order") or {}
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
    refund_case = context.get("refund_case") or {}
    order = context.get("order") or {}
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
    candidates: list[Any] = []
    for value in (
        state.get("evidence_refs"),
        draft.get("evidence_refs"),
        (state.get("retrieved_evidence") or {}).get("evidence_refs")
        if isinstance(state.get("retrieved_evidence"), dict)
        else None,
    ):
        if isinstance(value, list) and value:
            candidates = value
            break
    if not candidates:
        raise ValueError("missing evidence_refs")

    refs: list[EvidenceRefV1] = []
    for candidate in candidates:
        item = candidate.model_dump() if hasattr(candidate, "model_dump") else dict(candidate)
        if isinstance(item.get("retrieved_at"), str):
            item["retrieved_at"] = _normalize_timestamp(item["retrieved_at"])
        refs.append(EvidenceRefV1.model_validate(item))
    return refs


async def _attach_snapshot_binding(
    state: AgentState,
    result: dict[str, Any],
    *,
    assessment: dict[str, Any],
    draft: dict[str, Any],
    context: dict[str, Any],
    config: RunnableConfig | None,
) -> dict[str, Any]:
    if not result.get("proposed_action"):
        return result

    try:
        evidence_refs = _evidence_refs_from_state(state, draft)
        proposed_action = _build_proposed_action(
            state=state,
            draft=draft,
            context=context,
            assessment=assessment,
            evidence_refs=evidence_refs,
        )
        action_payload_hash = compute_action_payload_hash(proposed_action)
        session = (config or {}).get("configurable", {}).get("session") if config else None
        if session is None:
            raise ActionSafetySnapshotPersistenceError("session unavailable for snapshot persistence")

        run_id = UUID(str(state.get("current_run_id")))
        tenant_id = UUID(str(state.get("tenant_id")))
        user_id = UUID(str(state.get("user_id")))
        snapshot = await persist_action_safety_snapshot(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            proposed_action=proposed_action,
            action_payload_hash=action_payload_hash,
            policy_config_version=POLICY_CONFIG_VERSION,
            risk_config_version=RISK_CONFIG_VERSION,
            retrieval_config_version=_retrieval_config_version(evidence_refs),
            evidence_refs=evidence_refs,
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
            "auto_allowed": False,
            "safety_snapshot_verified": False,
            "final_response": "操作需要人工复核，当前未创建可执行审批或动作草稿。",
            "node_errors": (state.get("node_errors") or [])
            + [{"node": "assess_risk_and_approval", "error": str(exc)}],
        }

    return {
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


async def assess_risk_and_approval(state: AgentState, config: RunnableConfig = None) -> dict:
    started_at = _now_iso()
    rules = _load_risk_rules()
    draft = state.get("recommendation_draft") or {}
    context = state.get("business_context") or {}

    if draft.get("recommended_action") in NO_ACTION_RECOMMENDATIONS:
        assessment = _fallback_risk(draft, context, rules)
        return {
            "risk_assessment": assessment,
            "proposed_action": None,
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
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
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
        }

    messages: list[dict[str, str]] = [
        {"role": "system", "content": ASSESS_RISK_SYSTEM},
        {"role": "user", "content": f"Risk rules: {rules}\nRecommendation: {draft}\nBusiness context: {context}"},
    ]
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
            outputs = {**(state.get("llm_outputs") or {}), "assess_risk_and_approval": assessment}
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
                        len(str(messages)),
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
        + [{"node": "assess_risk_and_approval", "error": last_error, "retry_count": 2}],
        "trace_steps": (state.get("trace_steps") or [])
        + [
            _trace_step(
                "error",
                started_at,
                provider_latency_ms,
                retry_count,
                len(str(messages)),
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
    )
