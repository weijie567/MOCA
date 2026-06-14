from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.intent_policy import (
    REQUIRED_SLOT_POLICY,
    PreRouteDecision,
    detect_pre_route,
    resolve_intent_precedence,
)
from src.agent.prompts import CLASSIFY_INTENT_SYSTEM
from src.agent.schemas import IntentResultV3, RequiredSlotExpression
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


def intent_result_to_state(
    result: IntentResultV3,
    prior_llm_outputs: dict[str, Any] | None = None,
    pre_route: PreRouteDecision | None = None,
    user_query: str = "",
) -> dict[str, Any]:
    primary_intent, requested_operation, precedence_reasons = resolve_intent_precedence(
        result.primary_intent,
        result.requested_operation,
        user_query,
        [str(intent) for intent in result.secondary_intents],
    )
    if pre_route and pre_route.requested_operation:
        requested_operation = pre_route.requested_operation
    if pre_route and pre_route.disposition == "approval_chat_not_trusted":
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

    llm_outputs = {
        **(prior_llm_outputs or {}),
        "intent_classification": {
            "raw": raw,
            "eval_metadata": {
                "calibrated_confidence": result.calibrated_confidence,
                "classifier_version": result.classifier_version,
                "calibration_version": result.calibration_version,
                "reason_codes": reason_codes,
                "llm_required_slots": raw.get("required_slots"),
            },
        },
    }
    update = {
        "primary_intent": primary_intent,
        "requested_operation": requested_operation,
        "intent_confidence": result.confidence,
        "secondary_intents": [str(intent) for intent in result.secondary_intents],
        "required_slots": policy_required_slots,
        "candidate_slots": dict(result.candidate_slots),
        "routing_hints": routing_hints,
        "current_intent": primary_intent,
        "last_intent": primary_intent,
        "llm_outputs": llm_outputs,
    }
    return {key: value for key, value in update.items() if key not in FORBIDDEN_STATE_WRITES}


async def classify_intent(state: AgentState) -> dict:
    started_at = _now_iso()
    user_text = state.get("user_query") or ""
    pre_route = detect_pre_route(user_text)
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
    return {
        "primary_intent": "unsupported",
        "requested_operation": "advise",
        "intent_confidence": 0.0,
        "secondary_intents": [],
        "required_slots": fallback_required,
        "candidate_slots": {},
        "routing_hints": {key: value for key, value in routing_hints.items() if value is not None},
        "current_intent": "unsupported",
        "last_intent": "unsupported",
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "intent_classification": {
                "raw": None,
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
