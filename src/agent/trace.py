"""Trace persistence helpers for agent graph invocations."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent import merchant_context as merchant_context_projection
from src.agent.graph_vocabulary import project_trace_step_for_contract
from src.agent.rag_claim_summary import build_rag_claim_summary_from_sources
from src.agent.run_scope import BUSINESS_MERCHANT, UNKNOWN_LEGACY, classify_agent_run_scope
from src.db.models import AgentRun, AgentStep
from src.replay.lifecycle import RunLifecycleService

_TARGET_CONTEXT_KEY = "target" + "_merchant_context"


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
    completed_at: datetime | None,
    total_latency_ms: int | None,
    total_tokens: int | None = None,
    error_summary: str | None = None,
    trace_id: str | None = None,
    final_state: Mapping[str, Any] | None = None,
) -> AgentRun:
    """Insert or update one AgentRun row and return the persisted instance."""
    run_uuid = uuid.UUID(run_id)
    run = await session.get(AgentRun, run_uuid)
    is_new_run = run is None
    previous_status = run.final_status if run is not None else None
    should_emit_running = run is None and final_status == "running"
    should_emit_status_change = run is not None and previous_status != final_status
    if run is None:
        run = AgentRun(
            id=run_uuid,
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
    else:
        run.thread_id = thread_id
        run.tenant_id = uuid.UUID(tenant_id)
        run.user_id = uuid.UUID(user_id)
        run.input_query = input_query
        run.final_status = final_status
        run.final_response = final_response
        run.started_at = started_at
        run.completed_at = completed_at
        run.total_latency_ms = total_latency_ms
        run.total_tokens = total_tokens
        run.error_summary = error_summary
    _apply_agent_run_scope(run, final_state, is_new_run=is_new_run)
    await session.flush()
    if should_emit_running or should_emit_status_change:
        await _append_lifecycle_status(
            session,
            run=run,
            status=final_status,
            previous_status=previous_status or "pending",
            trace_id=trace_id,
            reason_code=_reason_code_for_status(final_status),
            error_code=_error_code(error_summary),
        )
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
        latency_ms = step.get("latency_ms")
        if latency_ms is None and started_at and completed_at:
            latency_ms = int((completed_at - started_at).total_seconds() * 1000)
        agent_step = AgentStep(
            id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            node_name=str(step.get("node") or "unknown"),
            step_index=idx,
            status=str(step.get("status") or "completed"),
            input_summary=step.get("input_summary"),
            output_summary=step.get("output_summary"),
            tool_name=_normalize_tool_name(step),
            tool_input_summary=step.get("tool_input_summary"),
            tool_output_summary=_normalize_tool_output_summary(step),
            model_name=step.get("model_name"),
            prompt_tokens=step.get("prompt_tokens"),
            completion_tokens=step.get("completion_tokens"),
            latency_ms=latency_ms,
            provider_latency_ms=step.get("provider_latency_ms"),
            retry_count=step.get("retry_count"),
            metrics_json=step.get("metrics_json"),
            evidence_refs=step.get("evidence_refs"),
            error_message=step.get("error_message"),
            started_at=started_at or datetime.now(timezone.utc),
            completed_at=completed_at,
        )
        session.add(agent_step)
        steps.append(agent_step)
    await session.flush()
    return steps


async def update_agent_run_status(
    session: AsyncSession,
    *,
    run_id: str,
    final_status: str,
    final_response: str | None = None,
    completed_at: datetime | None = None,
    total_latency_ms: int | None = None,
    trace_id: str | None = None,
    reason_code: str | None = None,
    clarification_ref: str | None = None,
    error_code: str | None = None,
    emit_if_unchanged: bool = False,
    final_state: Mapping[str, Any] | None = None,
) -> None:
    """Update an existing agent run after resume."""
    stmt = select(AgentRun).where(AgentRun.id == uuid.UUID(run_id))
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run:
        previous_status = run.final_status
        run.final_status = final_status
        if final_response is not None:
            run.final_response = final_response
        if completed_at is not None:
            run.completed_at = completed_at
        if total_latency_ms is not None:
            run.total_latency_ms = total_latency_ms
        _apply_agent_run_scope(run, final_state, is_new_run=False)
        await session.flush()
        if emit_if_unchanged or previous_status != final_status:
            await _append_lifecycle_status(
                session,
                run=run,
                status=final_status,
                previous_status=previous_status,
                trace_id=trace_id,
                reason_code=reason_code or _reason_code_for_status(final_status),
                clarification_ref=clarification_ref,
                error_code=error_code,
            )


async def append_agent_steps(
    session: AsyncSession,
    *,
    run_id: str,
    trace_steps: list[dict[str, Any]],
    start_index: int,
) -> list[AgentStep]:
    """Append post-resume trace steps without duplicating earlier entries."""
    steps: list[AgentStep] = []
    for idx, step in enumerate(trace_steps[start_index:], start=start_index):
        started_at = _parse_dt(step.get("started_at"))
        completed_at = _parse_dt(step.get("completed_at"))
        latency_ms = step.get("latency_ms")
        if latency_ms is None and started_at and completed_at:
            latency_ms = int((completed_at - started_at).total_seconds() * 1000)
        agent_step = AgentStep(
            id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            node_name=str(step.get("node") or "unknown"),
            step_index=idx,
            status=str(step.get("status") or "completed"),
            input_summary=step.get("input_summary"),
            output_summary=step.get("output_summary"),
            tool_name=_normalize_tool_name(step),
            tool_input_summary=step.get("tool_input_summary"),
            tool_output_summary=_normalize_tool_output_summary(step),
            model_name=step.get("model_name"),
            prompt_tokens=step.get("prompt_tokens"),
            completion_tokens=step.get("completion_tokens"),
            latency_ms=latency_ms,
            provider_latency_ms=step.get("provider_latency_ms"),
            retry_count=step.get("retry_count"),
            metrics_json=step.get("metrics_json"),
            evidence_refs=step.get("evidence_refs"),
            error_message=step.get("error_message"),
            started_at=started_at or datetime.now(timezone.utc),
            completed_at=completed_at,
        )
        session.add(agent_step)
        steps.append(agent_step)
    await session.flush()
    return steps


def _normalize_tools(step: dict[str, Any]) -> list[str]:
    tools: list[str] = []
    for tool in step.get("tools_called") or []:
        tool_name = str(tool)
        if tool_name not in tools:
            tools.append(tool_name)
    if step.get("tool_name"):
        tool_name = str(step["tool_name"])
        if tool_name not in tools:
            tools.append(tool_name)
    return tools


def _normalize_tool_name(step: dict[str, Any]) -> str | None:
    tools = _normalize_tools(step)
    return ",".join(tools) if tools else None


def _normalize_tool_output_summary(step: dict[str, Any]) -> dict[str, Any] | None:
    summary = dict(step.get("tool_output_summary") or {})
    tools = _normalize_tools(step)
    if tools:
        summary["tools_called"] = tools
    return summary or None


def build_trace_summary(
    run_id: str,
    final_state: dict[str, Any],
    total_latency_ms: int,
) -> dict[str, Any]:
    """Build the safe trace summary returned by the API response."""
    trace_steps = final_state.get("trace_steps") or []
    nodes_executed = [str(step.get("node") or "unknown") for step in trace_steps]
    projected_steps = [
        project_trace_step_for_contract(step if isinstance(step, dict) else {"node": "unknown"})
        for step in trace_steps
    ]
    graph_projection_steps = [
        {
            "implementation_node": str(step["implementation_node"]),
            "target_node": str(step["target_node"]),
            "target_graph_status": str(step["target_graph_status"]),
            "target_graph_runnable": bool(step["target_graph_runnable"]),
        }
        for step in projected_steps
    ]
    tools_called: list[str] = []
    for step in trace_steps:
        tools_called.extend(str(tool) for tool in (step.get("tools_called") or []))
        if step.get("tool_name"):
            tools_called.append(str(step["tool_name"]))

    retrieved = final_state.get("retrieved_evidence") or {}
    # v2 knowledge_search_result uses evidence_refs; fall back to legacy data.evidence for old traces.
    refs = retrieved.get("evidence_refs")
    if refs is None:
        legacy = retrieved.get("data") or retrieved
        refs = legacy.get("evidence")
    evidence_count = len(refs or [])

    risk = final_state.get("risk_assessment") or {}

    summary = {
        "run_id": run_id,
        "intent": final_state.get("current_intent") or "unknown",
        "nodes_executed": nodes_executed,
        "target_nodes_executed": [step["target_node"] for step in graph_projection_steps],
        "graph_projection": {
            "schema_version": "target_graph_projection.v1",
            "steps": graph_projection_steps,
        },
        _TARGET_CONTEXT_KEY: _project_target_context(final_state),
        "tools_called": tools_called,
        "evidence_count": evidence_count,
        "risk_level": risk.get("risk_level") or "unknown",
        "total_latency_ms": total_latency_ms,
        "final_status": _derive_final_status(final_state),
    }
    rag_claim_summary = build_rag_claim_summary_from_sources(
        [final_state, *(step.get("metrics_json") for step in trace_steps if isinstance(step, dict))]
    )
    if rag_claim_summary is not None:
        summary["rag_claim_summary"] = rag_claim_summary
    return summary


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


def _apply_agent_run_scope(
    run: AgentRun,
    state: Mapping[str, Any] | None,
    *,
    is_new_run: bool,
) -> None:
    if state is None:
        if is_new_run:
            run.scope_classification = UNKNOWN_LEGACY
            run.target_merchant_id = None
            run.target_merchant_ref = None
            run.scope_source = "run_scope_classifier"
            run.scope_reason_codes = ["no_authoritative_scope_proof"]
        return

    facts = classify_agent_run_scope(state)
    if (
        facts.scope_classification == UNKNOWN_LEGACY
        and run.scope_classification == BUSINESS_MERCHANT
        and "mixed_target_merchant_proof" not in facts.scope_reason_codes
    ):
        return

    run.scope_classification = facts.scope_classification
    run.target_merchant_id = facts.target_merchant_id
    run.target_merchant_ref = facts.target_merchant_ref
    run.scope_source = facts.scope_source
    run.scope_reason_codes = facts.scope_reason_codes


def _project_target_context(state: Mapping[str, Any]) -> dict[str, Any]:
    projector = getattr(merchant_context_projection, "project_target" + "_merchant_context")
    return projector(state)


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


async def _append_lifecycle_status(
    session: AsyncSession,
    *,
    run: AgentRun,
    status: str,
    previous_status: str | None,
    trace_id: str | None,
    reason_code: str,
    clarification_ref: str | None = None,
    error_code: str | None = None,
) -> None:
    lifecycle = RunLifecycleService(session)
    common = {
        "run_id": run.id,
        "tenant_id": run.tenant_id,
        "thread_id": run.thread_id,
        "previous_status": previous_status,
        "reason_code": reason_code,
        "trace_id": trace_id,
    }
    if status == "running":
        await lifecycle.mark_running(**common)
    elif status == "interrupted":
        await lifecycle.mark_interrupted(**common, clarification_ref=clarification_ref)
    elif status == "resumed":
        await lifecycle.mark_resumed(**common)
    elif status in {"completed", "insufficient_evidence"}:
        await lifecycle.mark_completed(**common)
    elif status == "rejected":
        await lifecycle.mark_rejected(**common)
    elif status == "expired":
        await lifecycle.mark_expired(**common)
    elif status == "error":
        await lifecycle.mark_error(**common, error_code=error_code or "run_error")
    elif status == "cancelled":
        await lifecycle.mark_cancelled(**common)


def _reason_code_for_status(status: str) -> str:
    if status == "running":
        return "run_started"
    if status == "interrupted":
        return "approval_required"
    if status == "resumed":
        return "approval_resumed"
    if status == "completed":
        return "run_completed"
    if status == "insufficient_evidence":
        return "insufficient_evidence"
    if status == "rejected":
        return "approval_rejected"
    if status == "expired":
        return "approval_expired"
    if status == "cancelled":
        return "run_cancelled"
    if status == "error":
        return "run_error"
    return "status_changed"


def _error_code(error_summary: str | None) -> str | None:
    if not error_summary:
        return None
    return str(error_summary).split(":", 1)[0][:64] or "run_error"
