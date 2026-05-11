"""Trace persistence helpers for agent graph invocations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, AgentStep


async def write_agent_run(
    session: AsyncSession,
    *,
    run_id: str,
    thread_id: str,
    tenant_id: str,
    user_id: str,
    input_query: str,
    final_status: str,
    final_response: str | None,
    started_at: datetime,
    completed_at: datetime,
    total_latency_ms: int,
    total_tokens: int | None = None,
    error_summary: str | None = None,
) -> AgentRun:
    """Insert one AgentRun row and return the persisted instance."""
    run = AgentRun(
        id=uuid.UUID(run_id),
        thread_id=thread_id,
        tenant_id=uuid.UUID(tenant_id),
        user_id=uuid.UUID(user_id),
        input_query=input_query,
        final_status=final_status,
        final_response=final_response,
        started_at=started_at,
        completed_at=completed_at,
        total_latency_ms=total_latency_ms,
        total_tokens=total_tokens,
        error_summary=error_summary,
    )
    session.add(run)
    await session.flush()
    return run


async def write_agent_steps(
    session: AsyncSession,
    *,
    run_id: str,
    trace_steps: list[dict[str, Any]],
) -> list[AgentStep]:
    """Insert one AgentStep row per trace step and return persisted instances."""
    steps: list[AgentStep] = []
    for idx, step in enumerate(trace_steps):
        started_at = _parse_dt(step.get("started_at"))
        completed_at = _parse_dt(step.get("completed_at"))
        agent_step = AgentStep(
            id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            node_name=str(step.get("node") or "unknown"),
            step_index=idx,
            status=str(step.get("status") or "completed"),
            input_summary=step.get("input_summary"),
            output_summary=step.get("output_summary"),
            tool_name=step.get("tool_name"),
            tool_input_summary=step.get("tool_input_summary"),
            tool_output_summary=step.get("tool_output_summary"),
            model_name=step.get("model_name"),
            prompt_tokens=step.get("prompt_tokens"),
            completion_tokens=step.get("completion_tokens"),
            latency_ms=step.get("latency_ms"),
            evidence_refs=step.get("evidence_refs"),
            error_message=step.get("error_message"),
            started_at=started_at or datetime.now(timezone.utc),
            completed_at=completed_at,
        )
        session.add(agent_step)
        steps.append(agent_step)
    await session.flush()
    return steps


def build_trace_summary(
    run_id: str,
    final_state: dict[str, Any],
    total_latency_ms: int,
) -> dict[str, Any]:
    """Build the safe trace summary returned by the API response."""
    trace_steps = final_state.get("trace_steps") or []
    nodes_executed = [str(step.get("node") or "unknown") for step in trace_steps]
    tools_called: list[str] = []
    for step in trace_steps:
        tools_called.extend(str(tool) for tool in (step.get("tools_called") or []))
        if step.get("tool_name"):
            tools_called.append(str(step["tool_name"]))

    retrieved = final_state.get("retrieved_evidence") or {}
    retrieval_data = retrieved.get("data") or retrieved
    evidence_count = len(retrieval_data.get("evidence") or [])

    risk = final_state.get("risk_assessment") or {}

    return {
        "run_id": run_id,
        "intent": final_state.get("current_intent") or "unknown",
        "nodes_executed": nodes_executed,
        "tools_called": tools_called,
        "evidence_count": evidence_count,
        "risk_level": risk.get("risk_level") or "unknown",
        "total_latency_ms": total_latency_ms,
        "final_status": _derive_final_status(final_state),
    }


def _derive_final_status(state: dict[str, Any]) -> str:
    draft = state.get("recommendation_draft") or {}
    action = draft.get("recommended_action") or ""
    if action in {"insufficient_evidence", "citation_invalid"}:
        return "insufficient_evidence"
    if state.get("node_errors"):
        return "error"
    if state.get("final_response"):
        return "completed"
    return "error"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
