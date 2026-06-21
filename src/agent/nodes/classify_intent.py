from __future__ import annotations

import time
import re
from datetime import UTC, datetime
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.intent_policy import (
    REQUIRED_SLOT_POLICY,
    PreRouteDecision,
    detect_pre_route,
    resolve_intent_precedence,
    resolve_risk_tier,
)
from src.agent.prompts import CLASSIFY_INTENT_SYSTEM
from src.agent.schemas import IntentResultV3, RequiredSlotExpression
from src.agent.routing import route_after_intent
from src.agent.state import AgentState
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
_AMBIGUOUS_SHORT_REPLIES = {
    "继续",
    "继续吧",
    "就按上面",
    "就按上面的处理",
    "按上面处理",
    "好的",
    "好",
    "可以",
    "行",
    "嗯",
    "同意",
    "批准",
    "确认",
    "执行",
    "approve",
    "approved",
    "accept",
    "accepted",
    "yes",
    "ok",
    "goahead",
    "doit",
}
_SHORT_APPROVAL_OR_ACTION_REPLIES = {
    "同意",
    "批准",
    "确认",
    "执行",
    "approve",
    "approved",
    "accept",
    "accepted",
    "yes",
    "goahead",
    "doit",
}


def intent_result_to_state(
    result: IntentResultV3,
    prior_llm_outputs: dict[str, Any] | None = None,
    pre_route: PreRouteDecision | None = None,
    user_query: str = "",
    role: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    raw_primary_intent = result.primary_intent
    raw_requested_operation = result.requested_operation
    primary_intent, requested_operation, precedence_reasons = resolve_intent_precedence(
        result.primary_intent,
        result.requested_operation,
        user_query,
        [str(intent) for intent in result.secondary_intents],
    )
    policy_overrides: list[dict[str, Any]] = []
    if (primary_intent, requested_operation) != (raw_primary_intent, raw_requested_operation):
        policy_overrides.append(
            {
                "source": "intent_precedence",
                "from": {
                    "primary_intent": raw_primary_intent,
                    "requested_operation": raw_requested_operation,
                },
                "to": {
                    "primary_intent": primary_intent,
                    "requested_operation": requested_operation,
                },
                "reason_codes": precedence_reasons,
            }
        )
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
    if pre_route and pre_route.disposition == "safety_sensitive" and pre_route.requested_operation == "execute_action":
        if primary_intent != "action_request":
            policy_overrides.append(
                {
                    "source": "safety_sensitive_pre_route",
                    "from": {"primary_intent": primary_intent},
                    "to": {"primary_intent": "action_request"},
                    "reason_codes": pre_route.reason_codes,
                }
            )
        primary_intent = "action_request"
        requested_operation = pre_route.requested_operation or "execute_action"
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

    policy_required_slots = REQUIRED_SLOT_POLICY.get(primary_intent, RequiredSlotExpression()).model_dump()
    raw = result.model_dump()
    routing_hints = dict(result.routing_hints)
    reason_codes = list(result.reason_codes) + precedence_reasons
    if pre_route and pre_route.disposition != "none":
        routing_hints["pre_route_disposition"] = pre_route.disposition
        routing_hints["requires_clarification"] = pre_route.requires_clarification
        if pre_route.requires_clarification:
            routing_hints["clarification_reason"] = pre_route.disposition
        reason_codes.extend(pre_route.reason_codes)

    risk_tier = resolve_risk_tier(primary_intent, requested_operation, role, channel, routing_hints)
    update = {
        "primary_intent": primary_intent,
        "requested_operation": requested_operation,
        "intent_confidence": result.confidence,
        "risk_tier": risk_tier,
        "secondary_intents": [str(intent) for intent in result.secondary_intents],
        "required_slots": policy_required_slots,
        "candidate_slots": dict(result.candidate_slots),
        "routing_hints": routing_hints,
        "current_intent": primary_intent,
        "last_intent": primary_intent,
    }
    route_decision = route_after_intent(update)
    classification_trace = {
        "raw_llm_classification": raw,
        "pre_route_decision": pre_route.model_dump() if pre_route else None,
        "policy_overrides": policy_overrides,
        "effective_classification": {
            "primary_intent": primary_intent,
            "requested_operation": requested_operation,
            "required_slots": policy_required_slots,
        },
        "risk_tier": risk_tier,
        "route_decision": route_decision,
        "reason_codes": reason_codes,
    }
    llm_outputs = {
        **(prior_llm_outputs or {}),
        "intent_classification": {
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


def _short_text_key(text: str) -> str:
    return re.sub(r"[\s。！!,.，、；;：:]+", "", text.strip()).lower()


def _is_identifier_like_answer(text: str) -> bool:
    if _ID_ANSWER_RE.search(text):
        return True
    stripped = text.strip()
    return (
        2 <= len(stripped) <= 64
        and any(char.isdigit() for char in stripped)
        and re.fullmatch(r"[\w\s\-_:：#号单]+", stripped, flags=re.IGNORECASE) is not None
    )


def _is_ambiguous_short_reply(text: str) -> bool:
    return _short_text_key(text) in _AMBIGUOUS_SHORT_REPLIES


def _is_short_approval_or_action(text: str) -> bool:
    return _short_text_key(text) in _SHORT_APPROVAL_OR_ACTION_REPLIES


def _trace_step_without_llm(started_at: str, context_chars: int, source: str, reason_codes: list[str]) -> dict[str, Any]:
    return {
        "node": "classify_intent",
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
    return REQUIRED_SLOT_POLICY.get(primary_intent, RequiredSlotExpression()).model_dump()


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
    risk_tier = resolve_risk_tier(
        primary_intent,
        requested_operation,
        state.get("role"),
        "ordinary_chat",
        routing_hints,
    )
    update = {
        "primary_intent": primary_intent,
        "requested_operation": requested_operation,
        "intent_confidence": intent_confidence,
        "risk_tier": risk_tier,
        "secondary_intents": [],
        "required_slots": required_slots,
        "candidate_slots": candidate_slots,
        "routing_hints": routing_hints,
        "current_intent": primary_intent,
        "last_intent": primary_intent,
    }
    route_decision = route_after_intent(update)
    classification_trace = {
        "raw_llm_classification": None,
        "pre_route_decision": pre_route.model_dump(),
        "policy_overrides": policy_overrides,
        "effective_classification": {
            "primary_intent": primary_intent,
            "requested_operation": requested_operation,
            "required_slots": required_slots,
        },
        "risk_tier": risk_tier,
        "route_decision": route_decision,
        "reason_codes": reason_codes,
    }
    llm_outputs = {
        **(state.get("llm_outputs") or {}),
        "intent_classification": {
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
    flow = state.get("active_flow_state") if isinstance(state.get("active_flow_state"), dict) else None
    if flow and flow.get("kind") == "pending_required_slot":
        primary_intent = str(flow.get("last_effective_intent") or "unsupported")
        requested_operation = str(flow.get("last_requested_operation") or "advise")
        required_slots = _required_slots_from_flow(flow, primary_intent)
        candidate_slots = flow.get("candidate_slots") if isinstance(flow.get("candidate_slots"), dict) else {}
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
        if _is_ambiguous_short_reply(user_text):
            if _is_short_approval_or_action(user_text):
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
    if _is_ambiguous_short_reply(user_text):
        return _short_reply_clarification_update(
            state,
            user_text,
            pre_route,
            started_at,
            _is_short_approval_or_action(user_text),
        )
    return None


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
    required_slots = REQUIRED_SLOT_POLICY["unsupported"].model_dump()
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


async def classify_intent(state: AgentState) -> dict:
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
                    "classify_intent",
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

    fallback_required = REQUIRED_SLOT_POLICY["unsupported"].model_dump()
    routing_hints: dict[str, Any] = {}
    if pre_route.disposition != "none":
        routing_hints = {
            "pre_route_disposition": pre_route.disposition,
            "requires_clarification": pre_route.requires_clarification,
            "clarification_reason": pre_route.disposition if pre_route.requires_clarification else None,
        }
    risk_tier = resolve_risk_tier("unsupported", "advise", state.get("role"), "ordinary_chat", routing_hints)
    fallback_state = {
        "primary_intent": "unsupported",
        "requested_operation": "advise",
        "intent_confidence": 0.0,
        "routing_hints": {key: value for key, value in routing_hints.items() if value is not None},
    }
    classification_trace = {
        "raw_llm_classification": None,
        "pre_route_decision": pre_route.model_dump(),
        "policy_overrides": [{"source": "classifier_validation_failed", "reason_codes": [*pre_route.reason_codes]}],
        "effective_classification": {
            "primary_intent": "unsupported",
            "requested_operation": "advise",
            "required_slots": fallback_required,
        },
        "risk_tier": risk_tier,
        "route_decision": route_after_intent(fallback_state),
        "reason_codes": ["classifier_validation_failed", *pre_route.reason_codes],
    }
    return {
        "primary_intent": "unsupported",
        "requested_operation": "advise",
        "intent_confidence": 0.0,
        "risk_tier": risk_tier,
        "classification_trace": classification_trace,
        "secondary_intents": [],
        "required_slots": fallback_required,
        "candidate_slots": {},
        "routing_hints": fallback_state["routing_hints"],
        "current_intent": "unsupported",
        "last_intent": "unsupported",
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "intent_classification": {
                "raw": None,
                "classification_trace": classification_trace,
                "eval_metadata": {
                    "calibrated_confidence": 0.0,
                    "classifier_version": "intent_classifier.v2",
                    "calibration_version": "calibration.unverified",
                    "reason_codes": ["classifier_validation_failed", *pre_route.reason_codes],
                },
            },
        },
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "classify_intent", "error": last_error, "retry_count": 2}],
        "trace_steps": (state.get("trace_steps") or [])
        + [
            _trace_step(
                "classify_intent",
                "error",
                started_at,
                provider_latency_ms,
                retry_count,
                len(str(messages)),
            )
        ],
    }
