from __future__ import annotations

import time
import re
from datetime import UTC, datetime
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.intent_policy import (
    ClarificationDecision,
    INTENT_POLICY_REGISTRY,
    RiskDecision,
    SLOT_POLICY_REGISTRY,
    SemanticIntent,
    PreRouteDecision,
    build_task_plan,
    decide_clarification,
    derive_keyword_signals,
    detect_pre_route,
    is_ambiguous_short_reply,
    is_short_approval_or_action_reply,
    select_executable_prefix,
    task_plan_payload,
    task_steps_payload,
)
from src.agent.prompts import CLASSIFY_INTENT_SYSTEM
from src.agent.schemas import IntentResultV3, RequiredSlotExpression
from src.agent.routing import normalize_expected_slot_type, route_after_contextual_intent
from src.agent.state import AgentState, trusted_business_query_context_binding
from src.business.query.registry import BUSINESS_QUERY_REGISTRY
from src.business.query.schemas import BusinessQuerySpec
from src.config import settings


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
    node: str,
    status: str,
    started_at: str,
    provider_latency_ms: int | None,
    retry_count: int,
    context_chars: int,
) -> dict[str, Any]:
    return {
        "node": node,
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


FORBIDDEN_STATE_WRITES = {
    "approval_result",
    "approval_revision_refs",
    "trusted_approval_result",
    "resume",
    "command",
    "extracted_slots",
    "active_slots",
    "risk_signals",
    "final_response",
    "tool_results",
    "action_result",
    "proposed_action",
}


_ID_ANSWER_RE = re.compile(
    r"\b(?:OD|ORD|ORDER|RF|REFUND|TKT|TK|APR|MER|CUST)[-_]?[A-Z0-9]{2,}\b",
    re.IGNORECASE,
)
_AGGREGATE_ORDER_METRIC_RE = re.compile(
    r"(?:当前|现在|目前|一共|总共|总计|全部|所有)?.{0,8}(?:多少|几|数量|总数|统计|count).{0,8}(?:订单|order)",
    re.IGNORECASE,
)
_STANDALONE_SMALL_TALK_RE = re.compile(
    r"^(?:你好|您好|嗨|哈喽|hello|hi|hey|在吗|谢谢|感谢|辛苦了|好的|好)$",
    re.IGNORECASE,
)
_BUSINESS_KEYWORDS_RE = re.compile(
    r"(?:订单|退款|退货|工单|补偿|优惠券|投诉|申诉|解封|政策|规则|审批|处理|状态|order|refund|ticket|coupon|policy)",
    re.IGNORECASE,
)
_BUSINESS_QUERY_FIELD_REQUEST_RE = re.compile(
    r"(?:订单号|单号|退款单号|工单号|券号|编号|明细|详情|列表|list|detail|order\s*(?:no|number|id))",
    re.IGNORECASE,
)
_BUSINESS_QUERY_CURSOR_REQUEST_RE = re.compile(
    r"(?:下一页|下页|继续|更多|next\s*page|more)",
    re.IGNORECASE,
)
_BUSINESS_QUERY_FIELD_ALIASES = {
    "order": (("订单号", "单号", "order no", "order number", "order id"), "order_no"),
    "refund_case": (("退款单号", "退款编号", "refund case", "refund no"), "refund_case_no"),
    "ticket": (("工单号", "工单编号", "ticket"), "ticket_no"),
    "coupon_record": (("券号", "优惠券编号", "coupon"), "coupon_record_no"),
}


def _semantic_payload(semantic: SemanticIntent) -> dict[str, Any]:
    return {
        "intent": semantic.intent,
        "operation": semantic.operation,
        "entities": dict(semantic.entities),
        "raw_confidence": semantic.raw_confidence,
        "keyword_signals": list(semantic.keyword_signals),
        "arbitration": list(semantic.arbitration),
    }


def _risk_payload(risk: RiskDecision) -> dict[str, Any]:
    return {
        "tier": risk.tier,
        "evidence_required": risk.evidence_required,
        "approval_required": risk.approval_required,
        "reason_codes": list(risk.reason_codes),
    }


def _clarification_payload(decision: ClarificationDecision) -> dict[str, Any]:
    return {
        "requires_clarification": decision.requires_clarification,
        "reason": decision.reason,
        "threshold_applied": decision.threshold_applied,
    }


def _registry_resolve_precedence(
    primary_intent: str,
    secondary_intents: list[str],
    requested_operation: str,
    *,
    query: str,
    raw_confidence: float | None,
) -> tuple[str, str, list[str]]:
    return INTENT_POLICY_REGISTRY.resolve_precedence(
        primary_intent,
        secondary_intents,
        requested_operation,
        query=query,
        raw_confidence=raw_confidence,
    )


def _semantic_from_llm_result(result: IntentResultV3, user_query: str) -> SemanticIntent:
    primary_intent, requested_operation, arbitration = _registry_resolve_precedence(
        result.primary_intent,
        [str(intent) for intent in result.secondary_intents],
        result.requested_operation,
        query=user_query,
        raw_confidence=result.confidence,
    )
    return SemanticIntent(
        intent=primary_intent,
        operation=requested_operation,
        entities=dict(result.candidate_slots),
        raw_confidence=result.confidence,
        keyword_signals=derive_keyword_signals(user_query),
        arbitration=tuple(arbitration),
    )


def _semantic_from_effective_values(
    *,
    primary_intent: str,
    requested_operation: str,
    raw_confidence: float | None,
    candidate_slots: dict[str, Any],
    user_query: str,
    arbitration: list[str],
) -> SemanticIntent:
    return SemanticIntent(
        intent=primary_intent,  # type: ignore[arg-type]
        operation=requested_operation,  # type: ignore[arg-type]
        entities=dict(candidate_slots),
        raw_confidence=raw_confidence,
        keyword_signals=derive_keyword_signals(user_query),
        arbitration=tuple(arbitration),
    )


def _apply_pre_route_to_semantic(
    semantic: SemanticIntent,
    pre_route: PreRouteDecision | None,
) -> tuple[SemanticIntent, list[dict[str, Any]]]:
    policy_overrides: list[dict[str, Any]] = []
    primary_intent = semantic.intent
    requested_operation = semantic.operation
    if pre_route and pre_route.requested_operation:
        if requested_operation != pre_route.requested_operation:
            policy_overrides.append(
                {
                    "source": "pre_route_requested_operation",
                    "from": {"requested_operation": requested_operation},
                    "to": {"requested_operation": pre_route.requested_operation},
                    "reason_codes": pre_route.reason_codes,
                }
            )
        requested_operation = pre_route.requested_operation
    if pre_route and pre_route.disposition == "safety_sensitive":
        forced_intent = None
        if pre_route.requested_operation == "execute_action":
            forced_intent = "action_request"
        elif pre_route.requested_operation == "escalate":
            forced_intent = "complaint_escalation"
        if forced_intent and primary_intent != forced_intent:
            policy_overrides.append(
                {
                    "source": "safety_sensitive_pre_route",
                    "from": {"primary_intent": primary_intent},
                    "to": {"primary_intent": forced_intent},
                    "reason_codes": pre_route.reason_codes,
                }
            )
            primary_intent = forced_intent
        if forced_intent:
            requested_operation = pre_route.requested_operation or requested_operation
    if pre_route and pre_route.disposition == "approval_chat_not_trusted":
        policy_overrides.append(
            {
                "source": "approval_chat_not_trusted",
                "from": {
                    "primary_intent": primary_intent,
                    "requested_operation": requested_operation,
                },
                "to": {"primary_intent": "unsupported", "requested_operation": "advise"},
                "reason_codes": pre_route.reason_codes,
            }
        )
        primary_intent = "unsupported"
        requested_operation = "advise"
    return (
        SemanticIntent(
            intent=primary_intent,  # type: ignore[arg-type]
            operation=requested_operation,  # type: ignore[arg-type]
            entities=semantic.entities,
            raw_confidence=semantic.raw_confidence,
            keyword_signals=semantic.keyword_signals,
            arbitration=semantic.arbitration,
        ),
        policy_overrides,
    )


def _risk_decision_for(
    semantic: SemanticIntent,
    *,
    role: str | None,
    channel: str | None,
    routing_hints: dict[str, Any],
) -> RiskDecision:
    return INTENT_POLICY_REGISTRY.resolve_risk_decision(
        semantic.intent,
        semantic.operation,
        role=role,
        channel=channel,
        routing_hints=routing_hints,
    )


def _classify_layers(
    semantic: SemanticIntent,
    *,
    role: str | None,
    channel: str | None,
    routing_hints: dict[str, Any],
    pre_route: PreRouteDecision | None,
    calibrated_confidence: float | None,
) -> tuple[SemanticIntent, RiskDecision, ClarificationDecision]:
    risk_decision = _risk_decision_for(
        semantic,
        role=role,
        channel=channel,
        routing_hints=routing_hints,
    )
    clarification_decision = decide_clarification(
        semantic.intent,
        semantic.operation,
        semantic.raw_confidence,
        pre_route,
        calibrated_confidence=calibrated_confidence,
    )
    return semantic, risk_decision, clarification_decision


def _pre_route_for_task_plan(
    pre_route: PreRouteDecision | None,
    *,
    step_count: int,
    normalization: tuple[str, ...],
) -> PreRouteDecision | None:
    if pre_route is None or pre_route.disposition != "multi_target_request":
        return pre_route
    lossless_single_step_normalizations = {
        "same_intent_entities_merged",
        "modifier_dropped:small_talk",
        "modifier_folded:complaint_as_severity",
    }
    plan_handled_multiple_requests = step_count > 1 or (
        bool(normalization)
        and all(record in lossless_single_step_normalizations for record in normalization)
    )
    if not plan_handled_multiple_requests:
        return pre_route
    return PreRouteDecision(
        disposition=pre_route.disposition,
        requested_operation=pre_route.requested_operation,
        reason_codes=list(pre_route.reason_codes),
        requires_clarification=False,
    )


def intent_result_to_state(
    result: IntentResultV3,
    prior_llm_outputs: dict[str, Any] | None = None,
    pre_route: PreRouteDecision | None = None,
    user_query: str = "",
    role: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    semantic_before_pre_route = _semantic_from_llm_result(result, user_query)
    semantic, pre_route_overrides = _apply_pre_route_to_semantic(semantic_before_pre_route, pre_route)
    task_plan, plan_normalization = build_task_plan(
        semantic,
        secondary_intents=[str(intent) for intent in result.secondary_intents],
        requested_operation=result.requested_operation,
        candidate_slots=result.candidate_slots,
    )
    task_pre_route = _pre_route_for_task_plan(
        pre_route,
        step_count=len(task_plan.steps),
        normalization=plan_normalization,
    )
    root_step = task_plan.steps[0]
    primary_intent = root_step.intent
    requested_operation = root_step.operation
    semantic = SemanticIntent(
        intent=primary_intent,
        operation=requested_operation,
        entities=root_step.entities,
        raw_confidence=semantic.raw_confidence,
        keyword_signals=semantic.keyword_signals,
        arbitration=semantic.arbitration,
    )
    policy_overrides: list[dict[str, Any]] = []
    if (semantic_before_pre_route.intent, semantic_before_pre_route.operation) != (
        result.primary_intent,
        result.requested_operation,
    ):
        policy_overrides.append(
            {
                "source": "intent_precedence",
                "from": {
                    "primary_intent": result.primary_intent,
                    "requested_operation": result.requested_operation,
                },
                "to": {
                    "primary_intent": semantic_before_pre_route.intent,
                    "requested_operation": semantic_before_pre_route.operation,
                },
                "reason_codes": list(semantic_before_pre_route.arbitration),
            }
        )
    policy_overrides.extend(pre_route_overrides)

    policy_required_slots = SLOT_POLICY_REGISTRY.required_slots_for(primary_intent).model_dump()
    raw = result.model_dump()
    routing_hints = dict(result.routing_hints)
    reason_codes = list(result.reason_codes) + list(semantic.arbitration)
    if pre_route and pre_route.disposition != "none":
        routing_hints["pre_route_disposition"] = pre_route.disposition
        if task_pre_route and task_pre_route.requires_clarification:
            routing_hints["requires_clarification"] = True
            routing_hints["clarification_reason"] = pre_route.disposition
        reason_codes.extend(pre_route.reason_codes)

    semantic, risk_decision, clarification_decision = _classify_layers(
        semantic,
        role=role,
        channel=channel,
        routing_hints=routing_hints,
        pre_route=task_pre_route,
        calibrated_confidence=result.calibrated_confidence,
    )
    executable_prefix, deferred_steps = select_executable_prefix(
        task_plan,
        role=role,
        channel=channel,
        routing_hints=routing_hints,
    )
    task_plan_state = task_plan_payload(task_plan)
    deferred_step_payloads = task_steps_payload(deferred_steps)
    executable_prefix_ids = [step.step_id for step in executable_prefix]
    update = {
        "primary_intent": primary_intent,
        "requested_operation": requested_operation,
        "intent_confidence": result.confidence,
        "risk_tier": risk_decision.tier,
        "task_plan": task_plan_state,
        "deferred_steps": deferred_step_payloads,
        "secondary_intents": [str(intent) for intent in result.secondary_intents],
        "required_slots": policy_required_slots,
        "candidate_slots": dict(result.candidate_slots),
        "routing_hints": routing_hints,
        "current_intent": primary_intent,
        "last_intent": primary_intent,
    }
    route_decision = route_after_contextual_intent(update)
    classification_trace = {
        "raw_llm_classification": raw,
        "candidate_classification": raw,
        "policy_owner": "IntentPolicyRegistry",
        "policy_overrides": policy_overrides,
        "semantic_intent": _semantic_payload(semantic),
        "risk_decision": _risk_payload(risk_decision),
        "clarification_decision": _clarification_payload(clarification_decision),
        "task_plan": task_plan_state,
        "executable_prefix": executable_prefix_ids,
        "deferred_steps": deferred_step_payloads,
        "plan_normalization": list(plan_normalization),
        "effective_classification": {
            "primary_intent": primary_intent,
            "requested_operation": requested_operation,
            "required_slots": policy_required_slots,
        },
        "risk_tier": risk_decision.tier,
        "route_decision": route_decision,
        "reason_codes": reason_codes,
    }
    llm_outputs = {
        **(prior_llm_outputs or {}),
        "contextual_intent_resolve": {
            "raw": raw,
            "classification_trace": classification_trace,
            "eval_metadata": {
                "calibrated_confidence": result.calibrated_confidence,
                "classifier_version": result.classifier_version,
                "calibration_version": result.calibration_version,
                "reason_codes": reason_codes,
                "llm_required_slots": raw.get("required_slots"),
            },
        },
    }
    update["classification_trace"] = classification_trace
    update["llm_outputs"] = llm_outputs
    return {key: value for key, value in update.items() if key not in FORBIDDEN_STATE_WRITES}


def _is_identifier_like_answer(text: str) -> bool:
    if _ID_ANSWER_RE.search(text):
        return True
    stripped = text.strip()
    return (
        2 <= len(stripped) <= 64
        and any(char.isdigit() for char in stripped)
        and re.fullmatch(r"[\w\s\-_:：#号单]+", stripped, flags=re.IGNORECASE) is not None
    )


def _trace_step_without_llm(started_at: str, context_chars: int, source: str, reason_codes: list[str]) -> dict[str, Any]:
    return {
        "node": "contextual_intent_resolve",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": {
            "source": source,
            "reason_codes": reason_codes,
            "context_chars": context_chars,
        },
    }


def _required_slots_from_flow(flow: dict[str, Any], primary_intent: str) -> dict[str, Any]:
    required_slots = flow.get("required_slots")
    if isinstance(required_slots, dict):
        try:
            return RequiredSlotExpression.model_validate(required_slots).model_dump()
        except ValidationError:
            pass
    return SLOT_POLICY_REGISTRY.required_slots_for(primary_intent).model_dump()


def _deterministic_classification_update(
    state: AgentState,
    *,
    started_at: str,
    pre_route: PreRouteDecision,
    primary_intent: str,
    requested_operation: str,
    intent_confidence: float,
    required_slots: dict[str, Any],
    candidate_slots: dict[str, Any],
    routing_hints: dict[str, Any],
    policy_overrides: list[dict[str, Any]],
    reason_codes: list[str],
    source: str,
) -> dict[str, Any]:
    semantic = _semantic_from_effective_values(
        primary_intent=primary_intent,
        requested_operation=requested_operation,
        raw_confidence=intent_confidence,
        candidate_slots=candidate_slots,
        user_query=str(state.get("user_query") or ""),
        arbitration=reason_codes,
    )
    semantic, risk_decision, clarification_decision = _classify_layers(
        semantic,
        role=state.get("role"),
        channel="ordinary_chat",
        routing_hints=routing_hints,
        pre_route=pre_route,
        calibrated_confidence=intent_confidence,
    )
    task_plan, plan_normalization = build_task_plan(
        semantic,
        secondary_intents=[],
        requested_operation=requested_operation,
        candidate_slots=candidate_slots,
    )
    executable_prefix, deferred_steps = select_executable_prefix(
        task_plan,
        role=state.get("role"),
        channel="ordinary_chat",
        routing_hints=routing_hints,
    )
    task_plan_state = task_plan_payload(task_plan)
    deferred_step_payloads = task_steps_payload(deferred_steps)
    update = {
        "primary_intent": primary_intent,
        "requested_operation": requested_operation,
        "intent_confidence": intent_confidence,
        "risk_tier": risk_decision.tier,
        "task_plan": task_plan_state,
        "deferred_steps": deferred_step_payloads,
        "secondary_intents": [],
        "required_slots": required_slots,
        "candidate_slots": candidate_slots,
        "routing_hints": routing_hints,
        "current_intent": primary_intent,
        "last_intent": primary_intent,
    }
    route_decision = route_after_contextual_intent(update)
    classification_trace = {
        "raw_llm_classification": None,
        "candidate_classification": None,
        "policy_owner": "IntentPolicyRegistry",
        "policy_overrides": policy_overrides,
        "semantic_intent": _semantic_payload(semantic),
        "risk_decision": _risk_payload(risk_decision),
        "clarification_decision": _clarification_payload(clarification_decision),
        "task_plan": task_plan_state,
        "executable_prefix": [step.step_id for step in executable_prefix],
        "deferred_steps": deferred_step_payloads,
        "plan_normalization": list(plan_normalization),
        "effective_classification": {
            "primary_intent": primary_intent,
            "requested_operation": requested_operation,
            "required_slots": required_slots,
        },
        "risk_tier": risk_decision.tier,
        "route_decision": route_decision,
        "reason_codes": reason_codes,
    }
    llm_outputs = {
        **(state.get("llm_outputs") or {}),
        "contextual_intent_resolve": {
            "raw": None,
            "classification_trace": classification_trace,
            "eval_metadata": {
                "calibrated_confidence": intent_confidence,
                "classifier_version": "intent_classifier.v2",
                "calibration_version": "deterministic_context",
                "reason_codes": reason_codes,
            },
        },
    }
    update["classification_trace"] = classification_trace
    update["llm_outputs"] = llm_outputs
    update["trace_steps"] = (state.get("trace_steps") or []) + [
        _trace_step_without_llm(started_at, len(str(state.get("user_query") or "")), source, reason_codes)
    ]
    return {key: value for key, value in update.items() if key not in FORBIDDEN_STATE_WRITES}


def _deterministic_context_update(
    state: AgentState,
    user_text: str,
    pre_route: PreRouteDecision,
    started_at: str,
) -> dict[str, Any] | None:
    if _is_standalone_small_talk(user_text):
        return _standalone_small_talk_update(state, pre_route, started_at)

    drilldown_slots = _business_query_drilldown_candidate_slots(state, user_text)
    if drilldown_slots is not None:
        return _business_query_drilldown_update(state, pre_route, started_at, drilldown_slots)

    metric_slots = _deterministic_metric_candidate_slots(user_text)
    if metric_slots is not None:
        return _business_metric_query_update(state, pre_route, started_at, metric_slots)

    flow = state.get("active_flow_state") if isinstance(state.get("active_flow_state"), dict) else None
    if flow and flow.get("kind") == "pending_required_slot":
        primary_intent = str(flow.get("last_effective_intent") or "unsupported")
        requested_operation = str(flow.get("last_requested_operation") or "advise")
        required_slots = _required_slots_from_flow(flow, primary_intent)
        candidate_slots = flow.get("candidate_slots") if isinstance(flow.get("candidate_slots"), dict) else {}
        pending_metric_slots = _pending_metric_time_answer_slots(primary_intent, flow, user_text)
        if pending_metric_slots:
            merged_candidate_slots = _merge_flow_metric_slots(flow, pending_metric_slots)
            reason_codes = ["active_flow_pending_metric_time_answered"]
            return _deterministic_classification_update(
                state,
                started_at=started_at,
                pre_route=pre_route,
                primary_intent=primary_intent,
                requested_operation=requested_operation,
                intent_confidence=1.0,
                required_slots=required_slots,
                candidate_slots=merged_candidate_slots,
                routing_hints={
                    "workflow_state_resolution": "answered_pending_metric_time_range",
                    "clarification_request_id": flow.get("clarification_request_id"),
                    "metric_slot_parser": "active_flow_state",
                },
                policy_overrides=[
                    {
                        "source": "active_flow_state",
                        "reason_codes": reason_codes,
                        "clarification_request_id": flow.get("clarification_request_id"),
                    }
                ],
                reason_codes=reason_codes,
                source="active_flow_state",
            )
        if _is_identifier_like_answer(user_text):
            reason_codes = ["active_flow_pending_slot_answered"]
            return _deterministic_classification_update(
                state,
                started_at=started_at,
                pre_route=pre_route,
                primary_intent=primary_intent,
                requested_operation=requested_operation,
                intent_confidence=1.0,
                required_slots=required_slots,
                candidate_slots=candidate_slots,
                routing_hints={
                    "workflow_state_resolution": "answered_pending_required_slot",
                    "clarification_request_id": flow.get("clarification_request_id"),
                },
                policy_overrides=[
                    {
                        "source": "active_flow_state",
                        "reason_codes": reason_codes,
                        "clarification_request_id": flow.get("clarification_request_id"),
                    }
                ],
                reason_codes=reason_codes,
                source="active_flow_state",
            )
        if is_ambiguous_short_reply(user_text):
            if is_short_approval_or_action_reply(user_text):
                return _short_reply_clarification_update(state, user_text, pre_route, started_at, True)
            reason_codes = ["active_flow_pending_slot_not_answered"]
            return _deterministic_classification_update(
                state,
                started_at=started_at,
                pre_route=pre_route,
                primary_intent=primary_intent,
                requested_operation=requested_operation,
                intent_confidence=0.0,
                required_slots=required_slots,
                candidate_slots=candidate_slots,
                routing_hints={
                    "workflow_state_resolution": "pending_required_slot_not_answered",
                    "requires_clarification": True,
                    "clarification_reason": "missing_required_slots",
                    "clarification_request_id": flow.get("clarification_request_id"),
                },
                policy_overrides=[
                    {
                        "source": "active_flow_state",
                        "reason_codes": reason_codes,
                        "clarification_request_id": flow.get("clarification_request_id"),
                    }
                ],
                reason_codes=reason_codes,
                source="active_flow_state",
            )
    if is_ambiguous_short_reply(user_text):
        return _short_reply_clarification_update(
            state,
            user_text,
            pre_route,
            started_at,
            is_short_approval_or_action_reply(user_text),
        )
    return None


def _is_standalone_small_talk(text: str) -> bool:
    normalized = re.sub(r"[，。！？!?,.\s]+", "", text.strip())
    if not normalized:
        return False
    if len(normalized) > 12:
        return False
    if _BUSINESS_KEYWORDS_RE.search(normalized):
        return False
    return _STANDALONE_SMALL_TALK_RE.search(normalized) is not None


def _standalone_small_talk_update(
    state: AgentState,
    pre_route: PreRouteDecision,
    started_at: str,
) -> dict[str, Any]:
    reason_codes = ["standalone_small_talk"]
    return _deterministic_classification_update(
        state,
        started_at=started_at,
        pre_route=pre_route,
        primary_intent="small_talk",
        requested_operation="advise",
        intent_confidence=1.0,
        required_slots=SLOT_POLICY_REGISTRY.required_slots_for("small_talk").model_dump(),
        candidate_slots={},
        routing_hints={},
        policy_overrides=[{"source": "small_talk_guard", "reason_codes": reason_codes}],
        reason_codes=reason_codes,
        source="small_talk_guard",
    )


def _deterministic_metric_candidate_slots(text: str) -> dict[str, Any] | None:
    normalized = text.strip()
    if not normalized:
        return None
    if _ID_ANSWER_RE.search(normalized):
        return None
    metric_id = _registry_metric_id_from_text(normalized)
    if metric_id is None:
        return None

    candidate_slots: dict[str, Any] = {"metric_id": metric_id}
    preset = _metric_time_preset_from_text(normalized)
    if preset:
        candidate_slots["metric_time_preset"] = preset
    default_preset = BUSINESS_QUERY_REGISTRY.default_time_preset_for_metric(metric_id)
    if default_preset and "metric_time_preset" not in candidate_slots:
        candidate_slots["metric_time_preset"] = default_preset
    return candidate_slots


def _registry_metric_id_from_text(text: str) -> str | None:
    normalized = text.strip()
    lowered = normalized.lower()
    if _AGGREGATE_ORDER_METRIC_RE.search(normalized):
        return BUSINESS_QUERY_REGISTRY.metric_id_for_alias("多少订单")
    for alias, metric_id in BUSINESS_QUERY_REGISTRY.metric_parser_aliases().items():
        alias_lowered = alias.lower()
        if alias_lowered not in lowered:
            continue
        if BUSINESS_QUERY_REGISTRY.metric_descriptor(metric_id).unit == "count" and not _looks_like_metric_count(
            normalized
        ):
            continue
        return metric_id
    if "refund rate" in lowered and "merchant" in lowered:
        return BUSINESS_QUERY_REGISTRY.metric_id_for_alias("退款率")
    return None


def _looks_like_metric_count(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ("多少", "几个", "几单", "数量", "总数", "统计", "一共", "总共", "count"))


def _metric_time_preset_from_text(text: str) -> str | None:
    lowered = text.lower()
    for alias, preset_id in BUSINESS_QUERY_REGISTRY.time_preset_parser_aliases().items():
        if alias.lower() in lowered and preset_id in BUSINESS_QUERY_REGISTRY.window_time_preset_ids():
            return preset_id
    return None


def _pending_metric_time_answer_slots(
    primary_intent: str,
    flow: dict[str, Any],
    user_text: str,
) -> dict[str, Any]:
    if primary_intent != "business_metric_query":
        return {}
    if not _flow_has_metric_id(flow):
        return {}
    preset = _metric_time_preset_from_text(user_text)
    if preset is None:
        return {}
    return {"metric_time_preset": preset}


def _flow_has_metric_id(flow: dict[str, Any]) -> bool:
    for key in ("resolved_slots", "candidate_slots"):
        slots = flow.get(key)
        if isinstance(slots, dict) and slots.get("metric_id"):
            return True
    return False


def _merge_flow_metric_slots(flow: dict[str, Any], current_turn_slots: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in ("candidate_slots", "resolved_slots"):
        slots = flow.get(key)
        if not isinstance(slots, dict):
            continue
        for slot in ("metric_id", "resource_type", "merchant_id", "status_filter"):
            value = slots.get(slot)
            if value not in (None, "", []):
                merged.setdefault(slot, value)
    merged.update(current_turn_slots)
    return merged


def _business_query_drilldown_candidate_slots(
    state: AgentState,
    user_text: str,
) -> dict[str, Any] | None:
    trusted_context = _trusted_business_query_drilldown_context(state)
    if trusted_context is None:
        return None
    expected_slot_type = _business_query_expected_slot_type(state)
    if _BUSINESS_QUERY_CURSOR_REQUEST_RE.search(user_text):
        if expected_slot_type not in (None, "cursor_request"):
            return None
        spec = _cursor_business_query_spec(trusted_context)
        reason_code = "business_query_drilldown_cursor_request"
        slot_type = "cursor_request"
    elif _BUSINESS_QUERY_FIELD_REQUEST_RE.search(user_text):
        if expected_slot_type not in (None, "field_request"):
            return None
        spec = _field_business_query_spec(trusted_context, user_text)
        reason_code = "business_query_drilldown_field_request"
        slot_type = "field_request"
    else:
        return None
    if spec is None:
        return None
    return {
        "business_query_spec": spec.model_dump(mode="json", exclude_none=True),
        "expected_slot_type": slot_type,
        "reason_code": reason_code,
    }


def _trusted_business_query_drilldown_context(state: AgentState) -> dict[str, Any] | None:
    last_query_spec = state.get("last_query_spec")
    last_answer_context = state.get("last_answer_context")
    expected_context = state.get("expected_slot_context")
    if not isinstance(last_query_spec, dict) or not isinstance(last_answer_context, dict):
        return None
    if not isinstance(expected_context, dict):
        return None
    if expected_context.get("purpose") != "business_query_drilldown":
        return None
    current_binding = trusted_business_query_context_binding(state)
    if current_binding is None or expected_context.get("context_binding") != current_binding:
        return None
    try:
        spec = BusinessQuerySpec.model_validate(last_query_spec)
    except ValidationError:
        return None
    return {
        "last_query_spec": spec,
        "last_answer_context": dict(last_answer_context),
        "result_cursor": state.get("result_cursor") if isinstance(state.get("result_cursor"), dict) else None,
        "expected_slot_context": dict(expected_context),
    }


def _business_query_expected_slot_type(state: AgentState) -> str | None:
    expected_slot_type = normalize_expected_slot_type(state.get("expected_slot_type"))
    if expected_slot_type is not None:
        return expected_slot_type
    expected_context = state.get("expected_slot_context")
    if isinstance(expected_context, dict):
        return normalize_expected_slot_type(expected_context.get("expected_slot_type"))
    return None


def _field_business_query_spec(context: dict[str, Any], user_text: str) -> BusinessQuerySpec | None:
    answer_context = context["last_answer_context"]
    allowed_drilldowns = answer_context.get("allowed_drilldowns")
    if not isinstance(allowed_drilldowns, list) or "list" not in allowed_drilldowns:
        return None
    prior_spec: BusinessQuerySpec = context["last_query_spec"]
    if prior_spec.operation not in {"aggregate", "group_by", "compare"}:
        return None
    fields = _requested_business_query_fields(prior_spec.resource, user_text)
    if not fields:
        return None
    payload = _business_query_scope_payload(prior_spec)
    payload.update(
        {
            "operation": "list",
            "resource": prior_spec.resource,
            "fields": fields,
            "limit": BUSINESS_QUERY_REGISTRY.resource_descriptor(prior_spec.resource).default_limit,
        }
    )
    return _validated_business_query_spec(payload)


def _cursor_business_query_spec(context: dict[str, Any]) -> BusinessQuerySpec | None:
    cursor = context.get("result_cursor")
    if not isinstance(cursor, dict):
        return None
    next_cursor = cursor.get("next_cursor")
    if not isinstance(next_cursor, dict):
        return None
    prior_spec: BusinessQuerySpec = context["last_query_spec"]
    if prior_spec.operation != "list":
        return None
    payload = prior_spec.model_dump(mode="json", exclude_none=True)
    payload["cursor"] = next_cursor
    return _validated_business_query_spec(payload)


def _business_query_scope_payload(spec: BusinessQuerySpec) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "time_preset": spec.time_preset,
        "start_at": spec.start_at,
        "end_at": spec.end_at,
        "merchant_id": spec.merchant_id,
        "filters": spec.filters.model_dump(mode="json"),
    }
    return {key: value for key, value in payload.items() if value not in (None, "")}


def _requested_business_query_fields(resource: str, user_text: str) -> list[str]:
    aliases = _BUSINESS_QUERY_FIELD_ALIASES.get(resource)
    if aliases is None:
        return []
    terms, field_id = aliases
    lowered = user_text.lower()
    if any(term.lower() in lowered for term in terms):
        return [field_id]
    if any(term in lowered for term in ("明细", "详情", "列表", "list", "detail")):
        list_fields = BUSINESS_QUERY_REGISTRY.field_ids_for_resource(resource, purpose="list")
        return [field_id] if field_id in list_fields else sorted(list_fields)[:1]
    return []


def _validated_business_query_spec(payload: dict[str, Any]) -> BusinessQuerySpec | None:
    try:
        return BusinessQuerySpec.model_validate(payload)
    except ValidationError:
        return None


def _business_query_drilldown_update(
    state: AgentState,
    pre_route: PreRouteDecision,
    started_at: str,
    drilldown_slots: dict[str, Any],
) -> dict[str, Any]:
    expected_slot_type = str(drilldown_slots["expected_slot_type"])
    reason_codes = [str(drilldown_slots["reason_code"])]
    candidate_slots = {"business_query_spec": drilldown_slots["business_query_spec"]}
    expected_context = state.get("expected_slot_context") if isinstance(state.get("expected_slot_context"), dict) else {}
    return _deterministic_classification_update(
        state,
        started_at=started_at,
        pre_route=pre_route,
        primary_intent="business_metric_query",
        requested_operation="read_status",
        intent_confidence=1.0,
        required_slots=SLOT_POLICY_REGISTRY.required_slots_for("business_metric_query").model_dump(),
        candidate_slots=candidate_slots,
        routing_hints={
            "workflow_state_resolution": "answered_business_query_drilldown",
            "expected_slot_type": expected_slot_type,
            "business_query_slot_parser": "deterministic",
            "expected_slot_context": {
                "purpose": "business_query_drilldown",
                "operation": expected_context.get("operation"),
                "resource": expected_context.get("resource"),
            },
        },
        policy_overrides=[
            {
                "source": "business_query_drilldown_context",
                "expected_slot_type": expected_slot_type,
                "reason_codes": reason_codes,
            }
        ],
        reason_codes=reason_codes,
        source="business_query_drilldown_context",
    )


def _business_metric_query_update(
    state: AgentState,
    pre_route: PreRouteDecision,
    started_at: str,
    candidate_slots: dict[str, Any],
) -> dict[str, Any]:
    reason_codes = ["deterministic_business_metric_query"]
    return _deterministic_classification_update(
        state,
        started_at=started_at,
        pre_route=pre_route,
        primary_intent="business_metric_query",
        requested_operation="read_status",
        intent_confidence=1.0,
        required_slots=SLOT_POLICY_REGISTRY.required_slots_for("business_metric_query").model_dump(),
        candidate_slots=candidate_slots,
        routing_hints={"metric_intent_parser": "deterministic"},
        policy_overrides=[{"source": "business_metric_guard", "reason_codes": reason_codes}],
        reason_codes=reason_codes,
        source="business_metric_guard",
    )


def _short_reply_clarification_update(
    state: AgentState,
    user_text: str,
    pre_route: PreRouteDecision,
    started_at: str,
    approval_like: bool,
) -> dict[str, Any]:
    del user_text
    reason = "approval_chat_not_trusted" if approval_like else "unsupported_or_ambiguous"
    routing_hints = {
        "requires_clarification": True,
        "clarification_reason": reason,
        "short_reply_without_active_flow": True,
    }
    if approval_like:
        routing_hints["pre_route_disposition"] = "approval_chat_not_trusted"
    required_slots = SLOT_POLICY_REGISTRY.required_slots_for("unsupported").model_dump()
    reason_codes = ["short_reply_without_active_flow", reason]
    return _deterministic_classification_update(
        state,
        started_at=started_at,
        pre_route=pre_route,
        primary_intent="unsupported",
        requested_operation="advise",
        intent_confidence=0.0,
        required_slots=required_slots,
        candidate_slots={},
        routing_hints=routing_hints,
        policy_overrides=[{"source": "short_reply_guard", "reason_codes": reason_codes}],
        reason_codes=reason_codes,
        source="short_reply_guard",
    )


async def contextual_intent_resolve(state: AgentState) -> dict:
    started_at = _now_iso()
    user_text = state.get("user_query") or ""
    pre_route = detect_pre_route(user_text)
    context_update = _deterministic_context_update(state, user_text, pre_route, started_at)
    if context_update is not None:
        return context_update
    messages: list[dict[str, str]] = [
        {"role": "system", "content": CLASSIFY_INTENT_SYSTEM},
        {"role": "user", "content": user_text},
    ]
    structured_llm = _get_llm().with_structured_output(IntentResultV3)
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
            update = intent_result_to_state(
                result,
                prior_llm_outputs=state.get("llm_outputs") or {},
                pre_route=pre_route,
                user_query=user_text,
                role=state.get("role"),
                channel="ordinary_chat",
            )
            update["trace_steps"] = (state.get("trace_steps") or []) + [
                _trace_step(
                    "contextual_intent_resolve",
                    "completed",
                    started_at,
                    provider_latency_ms,
                    retry_count,
                    len(str(messages)),
                )
            ]
            return update
        except (ValidationError, ValueError, TimeoutError, Exception) as exc:
            provider_latency_ms = round((time.perf_counter() - t0) * 1000)
            last_error = str(exc)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Validation failed: {last_error}. Respond with valid JSON.",
                    }
                )

    fallback_required = SLOT_POLICY_REGISTRY.required_slots_for("unsupported").model_dump()
    routing_hints: dict[str, Any] = {}
    if pre_route.disposition != "none":
        routing_hints = {
            "pre_route_disposition": pre_route.disposition,
            "requires_clarification": pre_route.requires_clarification,
            "clarification_reason": pre_route.disposition if pre_route.requires_clarification else None,
        }
    fallback_semantic = _semantic_from_effective_values(
        primary_intent="unsupported",
        requested_operation="advise",
        raw_confidence=0.0,
        candidate_slots={},
        user_query=user_text,
        arbitration=["classifier_validation_failed"],
    )
    fallback_semantic, risk_decision, clarification_decision = _classify_layers(
        fallback_semantic,
        role=state.get("role"),
        channel="ordinary_chat",
        routing_hints=routing_hints,
        pre_route=pre_route,
        calibrated_confidence=0.0,
    )
    fallback_routing_hints = {key: value for key, value in routing_hints.items() if value is not None}
    fallback_routing_hints.setdefault("requires_clarification", True)
    fallback_routing_hints.setdefault("clarification_reason", "structured_output_validation_failed")
    task_plan, plan_normalization = build_task_plan(
        fallback_semantic,
        secondary_intents=[],
        requested_operation="advise",
        candidate_slots={},
    )
    executable_prefix, deferred_steps = select_executable_prefix(
        task_plan,
        role=state.get("role"),
        channel="ordinary_chat",
        routing_hints=fallback_routing_hints,
    )
    task_plan_state = task_plan_payload(task_plan)
    deferred_step_payloads = task_steps_payload(deferred_steps)
    fallback_state = {
        "primary_intent": "unsupported",
        "requested_operation": "advise",
        "intent_confidence": 0.0,
        "routing_hints": fallback_routing_hints,
    }
    classification_trace = {
        "raw_llm_classification": None,
        "candidate_classification": None,
        "policy_owner": "IntentPolicyRegistry",
        "policy_overrides": [{"source": "classifier_validation_failed", "reason_codes": [*pre_route.reason_codes]}],
        "semantic_intent": _semantic_payload(fallback_semantic),
        "risk_decision": _risk_payload(risk_decision),
        "clarification_decision": _clarification_payload(clarification_decision),
        "task_plan": task_plan_state,
        "executable_prefix": [step.step_id for step in executable_prefix],
        "deferred_steps": deferred_step_payloads,
        "plan_normalization": list(plan_normalization),
        "effective_classification": {
            "primary_intent": "unsupported",
            "requested_operation": "advise",
            "required_slots": fallback_required,
        },
        "risk_tier": risk_decision.tier,
        "route_decision": route_after_contextual_intent(fallback_state),
        "reason_codes": ["classifier_validation_failed", *pre_route.reason_codes],
    }
    return {
        "primary_intent": "unsupported",
        "requested_operation": "advise",
        "intent_confidence": 0.0,
        "risk_tier": risk_decision.tier,
        "task_plan": task_plan_state,
        "deferred_steps": deferred_step_payloads,
        "classification_trace": classification_trace,
        "secondary_intents": [],
        "required_slots": fallback_required,
        "candidate_slots": {},
        "routing_hints": fallback_state["routing_hints"],
        "current_intent": "unsupported",
        "last_intent": "unsupported",
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "contextual_intent_resolve": {
                "status": "fallback",
                "fallback_intent": "unsupported",
                "reason_codes": ["classifier_validation_failed", *pre_route.reason_codes],
                "error_type": "structured_output_validation_failed",
            },
        },
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "contextual_intent_resolve", "error": last_error, "retry_count": 2}],
        "trace_steps": (state.get("trace_steps") or [])
        + [
            _trace_step(
                "contextual_intent_resolve",
                "error",
                started_at,
                provider_latency_ms,
                retry_count,
                len(str(messages)),
            )
        ],
    }
