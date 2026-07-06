from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.agent.intent_policy import PreRouteDecision, detect_pre_route
from src.agent.state import AgentState


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _query_text(state: AgentState) -> str:
    normalized = state.get("normalized_query")
    if isinstance(normalized, str) and normalized:
        return normalized
    return str(state.get("user_query") or "")


def _routing_hints(state: AgentState, decision: PreRouteDecision) -> dict[str, Any]:
    current = state.get("routing_hints")
    hints = dict(current) if isinstance(current, dict) else {}
    if decision.disposition == "none":
        return hints
    hints["pre_route_disposition"] = decision.disposition
    if decision.requires_clarification:
        hints["requires_clarification"] = True
        hints["clarification_reason"] = decision.disposition
    return hints


def _safety_flags(decision: PreRouteDecision) -> dict[str, Any]:
    if decision.disposition == "none":
        return {}
    flags: dict[str, Any] = {
        "disposition": decision.disposition,
        "reason_codes": list(decision.reason_codes),
        "requires_clarification": decision.requires_clarification,
    }
    if decision.requested_operation is not None:
        flags["requested_operation"] = decision.requested_operation
    return flags


def _trace_step(started_at: str, decision: PreRouteDecision) -> dict[str, Any]:
    return {
        "node": "safety_pre_route",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": {
            "disposition": decision.disposition,
            "requested_operation": decision.requested_operation,
            "reason_codes": list(decision.reason_codes),
            "requires_clarification": decision.requires_clarification,
        },
    }


async def safety_pre_route(state: AgentState) -> dict[str, Any]:
    started_at = _now_iso()
    decision = detect_pre_route(_query_text(state))

    return {
        "pre_route_decision": decision.model_dump(),
        "safety_flags": _safety_flags(decision),
        "routing_hints": _routing_hints(state, decision),
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, decision)],
    }
