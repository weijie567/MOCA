from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.context import ContextAssembler, PromptAssembly, project_candidate_slot_hints_for_prompt
from src.agent.context.session_memory_bundle import load_session_prompt_context
from src.agent.graph_vocabulary import target_graph_name
from src.agent.prompts import EXTRACT_SLOTS_SYSTEM
from src.agent.routing import resolve_slots_with_provenance
from src.agent.schemas import SlotExtractionResult
from src.agent.state import AgentState
from src.agent.working_state import project_working_state
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
    status: str,
    started_at: str,
    provider_latency_ms: int | None,
    retry_count: int,
    context_chars: int,
) -> dict[str, Any]:
    return {
        "node": "slot_resolution_gate",
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
            "target_node": target_graph_name("slot_resolution_gate", kind="node"),
            "target_router": target_graph_name("route_after_slot_resolution", kind="router"),
        },
    }


async def slot_resolution_gate(state: AgentState, config: RunnableConfig | None = None) -> dict:
    started_at = _now_iso()
    prompt_assembly = await _assemble_slot_prompt(state, config)
    messages = prompt_assembly.to_messages()
    structured_llm = _get_llm().with_structured_output(SlotExtractionResult)
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
            extracted = _merge_deterministic_metric_slots(result.model_dump(), state)
            resolution_state = _state_with_metric_parser_hint(state, extracted)
            resolution = resolve_slots_with_provenance(resolution_state)
            return _node_update(
                resolution_state,
                extracted=extracted,
                resolution=resolution,
                trace_status="completed",
                started_at=started_at,
                provider_latency_ms=provider_latency_ms,
                retry_count=retry_count,
                context_chars=_messages_chars(messages),
            )
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

    deterministic_extracted = _deterministic_metric_slots(state)
    if deterministic_extracted:
        extracted = _merge_deterministic_metric_slots({}, state)
        resolution_state = _state_with_metric_parser_hint(state, extracted)
        resolution = resolve_slots_with_provenance(resolution_state)
        return _node_update(
            resolution_state,
            extracted=extracted,
            resolution=resolution,
            trace_status="completed",
            started_at=started_at,
            provider_latency_ms=provider_latency_ms,
            retry_count=retry_count,
            context_chars=_messages_chars(messages),
        )

    resolution = _llm_error_resolution(state)
    update = _node_update(
        state,
        extracted={},
        resolution=resolution,
        trace_status="error",
        started_at=started_at,
        provider_latency_ms=provider_latency_ms,
        retry_count=retry_count,
        context_chars=_messages_chars(messages),
    )
    update["node_errors"] = (state.get("node_errors") or []) + [
        {"node": "slot_resolution_gate", "error": last_error, "retry_count": 2}
    ]
    return update


def _merge_deterministic_metric_slots(extracted: dict[str, Any], state: AgentState) -> dict[str, Any]:
    deterministic = _deterministic_metric_slots(state)
    if not deterministic:
        return dict(extracted)
    merged = dict(extracted)
    for slot, value in deterministic.items():
        if value not in (None, "", []):
            merged[slot] = value
    return merged


def _state_with_metric_parser_hint(state: AgentState, extracted: dict[str, Any]) -> AgentState:
    if not _deterministic_metric_slots(state):
        return {**state, "extracted_slots": extracted}
    routing_hints = dict(state.get("routing_hints") or {}) if isinstance(state.get("routing_hints"), dict) else {}
    routing_hints["metric_slot_parser"] = "deterministic"
    return {**state, "extracted_slots": extracted, "routing_hints": routing_hints}


def _deterministic_metric_slots(state: AgentState) -> dict[str, Any]:
    if state.get("primary_intent") != "business_metric_query":
        return {}
    text = str(state.get("normalized_query") or state.get("user_query") or "")
    lowered = text.lower()
    slots: dict[str, Any] = _active_flow_metric_slots(state)

    if "退款率" in text or "refund rate" in lowered:
        slots["metric_id"] = "merchant_refund_rate"
    elif "待处理" in text and "工单" in text:
        slots["metric_id"] = "pending_ticket_count"
        slots["metric_time_preset"] = "current_snapshot"
    elif "补偿券" in text or ("coupon" in lowered and any(token in lowered for token in ("count", "issued"))):
        slots["metric_id"] = "coupon_record_count"
    elif "退款单" in text or ("refund" in lowered and any(token in lowered for token in ("count", "how many"))):
        slots["metric_id"] = "refund_case_count"
    elif "订单" in text or ("order" in lowered and any(token in lowered for token in ("count", "how many"))):
        slots["metric_id"] = "order_count"

    if "今天" in text or "today" in lowered:
        slots["metric_time_preset"] = "today"
    elif "本周" in text or "这周" in text or "this week" in lowered:
        slots["metric_time_preset"] = "this_week"
    elif "本月" in text or "这个月" in text or "this month" in lowered:
        slots["metric_time_preset"] = "this_month"
    elif "本季度" in text or "这个季度" in text or "this quarter" in lowered:
        slots["metric_time_preset"] = "this_quarter"
    elif "今年" in text or "this year" in lowered:
        slots["metric_time_preset"] = "this_year"
    elif "当前" in text or "现在" in text or "current" in lowered:
        slots["metric_time_preset"] = "current_snapshot"

    return slots


def _active_flow_metric_slots(state: AgentState) -> dict[str, Any]:
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    if routing_hints.get("workflow_state_resolution") != "answered_pending_metric_time_range":
        return {}
    flow = state.get("active_flow_state") if isinstance(state.get("active_flow_state"), dict) else {}
    slots: dict[str, Any] = {}
    for key in ("resolved_slots", "candidate_slots"):
        flow_slots = flow.get(key)
        if not isinstance(flow_slots, dict):
            continue
        for slot in ("metric_id", "resource_type", "merchant_id", "status_filter"):
            value = flow_slots.get(slot)
            if value not in (None, "", []):
                slots.setdefault(slot, value)
    candidate_slots = state.get("candidate_slots") if isinstance(state.get("candidate_slots"), dict) else {}
    for slot in ("metric_id", "resource_type", "merchant_id", "status_filter"):
        value = candidate_slots.get(slot)
        if value not in (None, "", []):
            slots.setdefault(slot, value)
    return slots


def _node_update(
    state: AgentState,
    *,
    extracted: dict[str, Any],
    resolution: dict[str, Any],
    trace_status: str,
    started_at: str,
    provider_latency_ms: int | None,
    retry_count: int,
    context_chars: int,
) -> dict[str, Any]:
    active_slots = dict(resolution["resolved_slots"])
    active_slot_metadata = dict(resolution["slot_metadata"])
    missing_required = list(resolution["missing_required_slots"])
    slot_resolution_trace = dict(resolution["slot_resolution_trace"])
    routing_hints = dict(state.get("routing_hints") or {}) if isinstance(state.get("routing_hints"), dict) else {}
    if missing_required:
        routing_hints["missing_required_slots"] = missing_required
        routing_hints.setdefault("requires_clarification", True)
        routing_hints.setdefault("clarification_reason", "missing_required_slots")

    outputs = {
        **(state.get("llm_outputs") or {}),
        "slot_resolution_gate": {
            "raw": dict(extracted),
            "extracted_slots": dict(extracted),
            "candidate_slots": dict(slot_resolution_trace.get("candidate_slots") or {}),
            "slot_resolution_trace": slot_resolution_trace,
            "eval_metadata": {
                "route_decision": slot_resolution_trace.get("route_decision"),
                "reason_codes": list(slot_resolution_trace.get("reason_codes") or []),
            },
        },
    }
    return {
        "extracted_slots": extracted,
        "active_slots": active_slots,
        "active_slot_metadata": active_slot_metadata,
        "missing_required_slots": missing_required,
        "slot_resolution_trace": slot_resolution_trace,
        "routing_hints": routing_hints,
        "llm_outputs": outputs,
        "trace_steps": (state.get("trace_steps") or [])
        + [
            _trace_step(
                trace_status,
                started_at,
                provider_latency_ms,
                retry_count,
                context_chars,
            )
        ],
    }


def _llm_error_resolution(state: AgentState) -> dict[str, Any]:
    failure_state = {
        **state,
        "extracted_slots": {},
        "session_context": None,
        "session_memory": {"continuity_claimed": False},
    }
    resolution = resolve_slots_with_provenance(failure_state)
    trace = dict(resolution["slot_resolution_trace"])
    reason_codes = list(trace.get("reason_codes") or [])
    if "llm_slot_extraction_error" not in reason_codes:
        reason_codes.append("llm_slot_extraction_error")
    trace["reason_codes"] = reason_codes
    trace["route_decision"] = "clarification_gate"
    trace["resolved_slots"] = {}
    trace["inherited_session_slots"] = {}
    resolution["resolved_slots"] = {}
    resolution["slot_metadata"] = {}
    resolution["route_decision"] = "clarification_gate"
    resolution["slot_resolution_trace"] = trace
    return resolution


async def _assemble_slot_prompt(state: AgentState, config: RunnableConfig | None) -> PromptAssembly:
    candidate_slots = state.get("candidate_slots")
    node_hints = (
        project_candidate_slot_hints_for_prompt(candidate_slots)
        if isinstance(candidate_slots, dict) and candidate_slots
        else ""
    )
    prompt_context = await load_session_prompt_context(state, config)
    return ContextAssembler().assemble(
        system_prompt=EXTRACT_SLOTS_SYSTEM,
        current_user_message=str(state.get("normalized_query") or state.get("user_query") or ""),
        working_state=project_working_state(state),
        thread_rolling_summary=prompt_context["thread_rolling_summary"],
        recent_messages=prompt_context["recent_messages"],
        verified_policy_snippets=[],
        profile_memory_snippets=state.get("long_term_memory") or [],
        case_memory_snippets=state.get("case_memory") or [],
        tool_result_summaries=prompt_context["tool_result_summaries"],
        business_context={},
        memory_context_bundle=state.get("session_context_bundle"),
        node_hints=node_hints,
    )


def _messages_chars(messages: list[dict[str, str]]) -> int:
    return sum(len(message.get("content") or "") for message in messages)
