from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.graph_vocabulary import target_graph_name
from src.agent.nodes.extract_slots import _assemble_slot_prompt, _messages_chars
from src.agent.routing import resolve_slots_with_provenance
from src.agent.schemas import SlotExtractionResult
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
            extracted = result.model_dump()
            resolution = resolve_slots_with_provenance({**state, "extracted_slots": extracted})
            return _node_update(
                state,
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
