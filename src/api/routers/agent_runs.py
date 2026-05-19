"""Run-based agent APIs with Server-Sent Events streaming."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from sqlalchemy import select
from langgraph.errors import GraphInterrupt
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from src.agent.nodes.final_response import final_response as build_final_response
from src.agent.trace import build_trace_summary, write_agent_run, write_agent_steps
from src.api.schemas.agent_runs import CreateRunRequest, RunStatusResponse
from src.api.schemas.common import ApiResponse
from src.auth.permissions import get_current_user
from src.db.models import AgentRun, User
from src.db.session import get_session
from src.repositories.approval_repo import ApprovalRepository
from src.repositories.trace_repo import TraceRepository


router = APIRouter(tags=["agent-runs"])

SUPERVISOR_ROLES = {"supervisor", "admin", "approval_manager", "manager"}
SSE_HEARTBEAT_SECONDS = 15.0

NODE_MESSAGES: dict[str, str] = {
    "receive_request": "正在接收请求",
    "classify_intent": "正在识别意图",
    "extract_slots": "正在提取关键信息",
    "load_business_context": "正在读取订单信息",
    "retrieve_policy_evidence": "正在检索退款规则",
    "generate_recommendation": "正在生成处理建议",
    "assess_risk_and_approval": "正在评估风险",
    "approval_gate": "需要审批，等待人工决策",
    "execute_action": "正在执行操作",
    "final_response": "已完成",
}


@router.post("", response_model=ApiResponse)
async def create_agent_run(
    body: CreateRunRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
    """Create a pending agent run that can be executed by the SSE endpoint."""
    run_id = str(uuid.uuid4())
    await write_agent_run(
        session,
        run_id=run_id,
        thread_id=body.thread_id,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        input_query=body.query,
        final_status="pending",
        final_response=None,
        started_at=datetime.now(timezone.utc),
        completed_at=None,
        total_latency_ms=None,
    )
    await session.commit()
    return ApiResponse(
        success=True,
        data={"run_id": run_id, "status": "pending"},
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get("/{run_id}", response_model=ApiResponse)
async def get_agent_run_status(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
    """Return the current persisted status for an agent run."""
    run_uuid = _parse_run_id(run_id)
    repo = TraceRepository(session)
    run = await repo.get_run(run_uuid, user.tenant_id)
    _ensure_can_view_run(run, user=user)

    payload = RunStatusResponse(
        run_id=str(run.id),
        final_status=run.final_status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        final_response=run.final_response,
    )
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get("/{run_id}/events")
async def stream_agent_run_events(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> EventSourceResponse:
    """Execute a pending run and stream node-level status events."""
    run_uuid = _parse_run_id(run_id)
    run = await _claim_pending_run_for_stream(session, run_uuid, user)

    graph = request.app.state.agent_graph
    input_state = {
        "user_query": run.input_query,
        "thread_id": run.thread_id,
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.id),
        "role": user.role,
        "current_run_id": str(run.id),
    }
    config = {
        "configurable": {
            "thread_id": _checkpoint_thread_id(user=user, thread_id=run.thread_id),
            "session": session,
        }
    }

    return EventSourceResponse(_event_generator(graph, input_state, config, run=run, session=session, user=user))


@router.get("/{run_id}/evidence", response_model=ApiResponse)
async def get_agent_run_evidence(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
    """Return deduplicated evidence references persisted by run trace steps."""
    run_uuid = _parse_run_id(run_id)
    repo = TraceRepository(session)
    run = await repo.get_run(run_uuid, user.tenant_id)
    _ensure_can_view_run(run, user=user)

    steps = await repo.get_steps(run_uuid)
    evidence = _dedupe_evidence_refs(step.evidence_refs for step in steps)
    return ApiResponse(
        success=True,
        data={"evidence": evidence},
        trace_id=getattr(request.state, "trace_id", None),
    )


async def _event_generator(
    graph: Any,
    input_state: dict[str, Any],
    config: dict[str, Any],
    *,
    run: AgentRun,
    session: AsyncSession,
    user: User,
):
    run_id_str = str(run.id)
    t0 = time.perf_counter()
    step_index = 0
    trace_steps: list[dict[str, Any]] = []
    final_state: dict[str, Any] = {}

    yield _sse_event(
        event_type="run_started",
        run_id=run_id_str,
        step_index=0,
        status="running",
        message="正在接收请求",
        payload={},
    )

    try:
        async for stream_item in _stream_graph_updates_with_heartbeats(graph, input_state, config):
            if stream_item is None:
                yield {"comment": "keepalive"}
                continue

            node_name, update = _normalize_stream_update(stream_item)
            if _is_interrupt_stream_item(node_name, update):
                async for event in _handle_approval_required(
                    update,
                    run=run,
                    session=session,
                    user=user,
                    step_index=step_index + 1,
                    t0=t0,
                    trace_steps=trace_steps,
                ):
                    yield event
                return

            step_index += 1
            message = NODE_MESSAGES.get(node_name, f"正在执行 {node_name}")
            yield _sse_event(
                event_type="step_started",
                run_id=run_id_str,
                step_index=step_index,
                node_name=node_name,
                status="running",
                message=message,
                payload={},
            )

            payload = _extract_step_payload(node_name, update)
            yield _sse_event(
                event_type="step_completed",
                run_id=run_id_str,
                step_index=step_index,
                node_name=node_name,
                status="completed",
                message=message,
                payload=payload,
            )

            update_mapping = _as_mapping(update)
            final_state.update(update_mapping)
            if isinstance(update_mapping.get("trace_steps"), list):
                trace_steps = update_mapping["trace_steps"]

        if not final_state.get("final_response"):
            final_state.update(await build_final_response(final_state))

        final_response = final_state.get("final_response")
        if isinstance(final_state.get("trace_steps"), list):
            trace_steps = final_state["trace_steps"]
        total_ms = round((time.perf_counter() - t0) * 1000)
        final_status = build_trace_summary(run_id_str, final_state, total_ms).get("final_status", "completed")
        if not final_response:
            final_status = "error"
            final_response = None
        completed_at = datetime.now(timezone.utc)
        await _complete_run(
            session=session,
            run=run,
            final_status=str(final_status),
            final_response=str(final_response) if final_response else None,
            completed_at=completed_at,
            total_latency_ms=total_ms,
            trace_steps=trace_steps,
        )
        if final_response:
            yield _sse_event(
                event_type="final_response",
                run_id=run_id_str,
                step_index=step_index + 1,
                status="completed",
                message="已完成",
                payload={"final_response": str(final_response)},
            )
        else:
            yield _sse_event(
                event_type="error",
                run_id=run_id_str,
                step_index=step_index + 1,
                status="failed",
                message="未生成最终回复，请重试",
                payload={"error_message": "Agent finished without a final response"},
            )
    except asyncio.CancelledError as exc:
        await _mark_run_error(session=session, run=run, exc=exc, t0=t0)
        raise
    except Exception as exc:
        if _is_graph_interrupt(exc):
            async for event in _handle_approval_required(
                exc,
                run=run,
                session=session,
                user=user,
                step_index=step_index + 1,
                t0=t0,
                trace_steps=trace_steps,
            ):
                yield event
            return

        yield _sse_event(
            event_type="error",
            run_id=run_id_str,
            step_index=step_index + 1,
            status="failed",
            message="执行遇到问题，请重试",
            payload={"error_message": str(exc)},
        )
        await _mark_run_error(session=session, run=run, exc=exc, t0=t0)


async def _stream_graph_updates_with_heartbeats(graph: Any, input_state: dict[str, Any], config: dict[str, Any]):
    stream = graph.astream(input_state, config, stream_mode="updates")
    iterator = stream.__aiter__()
    pending: asyncio.Task[Any] | None = None
    try:
        while True:
            pending = asyncio.create_task(anext(iterator))
            while True:
                done, _ = await asyncio.wait({pending}, timeout=SSE_HEARTBEAT_SECONDS)
                if pending in done:
                    break
                yield None
            try:
                yield pending.result()
            except StopAsyncIteration:
                break
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pending
        aclose = getattr(iterator, "aclose", None)
        if callable(aclose):
            await aclose()


async def _handle_approval_required(
    exc_or_data: Any,
    *,
    run: AgentRun,
    session: AsyncSession,
    user: User,
    step_index: int,
    t0: float,
    trace_steps: list[dict[str, Any]],
):
    completed_at = datetime.now(timezone.utc)
    interrupt_data = _extract_interrupt_data(exc_or_data)
    persisted_steps = _with_approval_gate_step(trace_steps, completed_at)
    approval_repo = ApprovalRepository(session)
    expires_at = _parse_expires_at(interrupt_data.get("expires_at"))
    approval = await approval_repo.create(
        run_id=run.id,
        tenant_id=user.tenant_id,
        requested_by=user.id,
        proposed_action=interrupt_data.get("proposed_action") or {},
        risk_level=interrupt_data.get("risk_level") or "high",
        risk_rule_ref=interrupt_data.get("risk_rule_ref"),
        risk_reason=interrupt_data.get("risk_reason"),
        expires_at=expires_at,
        thread_id=run.thread_id,
    )
    await approval_repo.add_step(approval.id, event_type="created", actor_id=user.id)
    await _complete_run(
        session=session,
        run=run,
        final_status="interrupted",
        final_response=None,
        completed_at=completed_at,
        total_latency_ms=round((time.perf_counter() - t0) * 1000),
        trace_steps=persisted_steps,
    )
    yield _sse_event(
        event_type="approval_required",
        run_id=str(run.id),
        step_index=step_index,
        node_name="approval_gate",
        status="waiting_approval",
        message="需要审批，等待人工决策",
        payload={
            "approval_id": str(approval.id),
            "proposed_action": interrupt_data.get("proposed_action"),
            "risk_level": interrupt_data.get("risk_level"),
        },
    )


async def _claim_pending_run_for_stream(session: AsyncSession, run_id: UUID, user: User) -> AgentRun:
    result = await session.execute(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.tenant_id == user.tenant_id).with_for_update()
    )
    run = result.scalar_one_or_none()
    _ensure_can_view_run(run, user=user)
    if run.final_status != "pending":
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "RUN_ALREADY_STARTED",
                "message": "Run event stream has already been started",
            },
        )

    try:
        run.final_status = "running"
        await session.commit()
        return run
    except Exception:
        await session.rollback()
        raise


async def _complete_run(
    *,
    session: AsyncSession,
    run: AgentRun,
    final_status: str,
    final_response: str | None,
    completed_at: datetime,
    total_latency_ms: int,
    trace_steps: list[dict[str, Any]],
) -> None:
    try:
        run.final_status = final_status
        run.final_response = final_response
        run.completed_at = completed_at
        run.total_latency_ms = total_latency_ms
        run.total_tokens = _count_tokens(trace_steps)
        if trace_steps:
            await write_agent_steps(session, run_id=str(run.id), trace_steps=trace_steps)
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def _mark_run_error(*, session: AsyncSession, run: AgentRun, exc: BaseException, t0: float) -> None:
    try:
        run.final_status = "error"
        run.final_response = None
        run.completed_at = datetime.now(timezone.utc)
        run.total_latency_ms = round((time.perf_counter() - t0) * 1000)
        run.error_summary = (str(exc) or type(exc).__name__)[:500]
        await session.commit()
    except Exception:
        await session.rollback()


def _sse_event(
    *,
    event_type: str,
    run_id: str,
    step_index: int,
    status: str,
    message: str,
    payload: dict[str, Any],
    node_name: str | None = None,
) -> dict[str, str]:
    data = {
        "event_type": event_type,
        "run_id": run_id,
        "step_index": step_index,
        "node_name": node_name,
        "status": status,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    return {"data": json.dumps(data, ensure_ascii=False)}


def _normalize_stream_update(stream_item: Any) -> tuple[str, Any]:
    if isinstance(stream_item, tuple) and len(stream_item) == 2:
        return str(stream_item[0]), stream_item[1]
    if isinstance(stream_item, dict) and len(stream_item) == 1:
        node_name, update = next(iter(stream_item.items()))
        return str(node_name), update
    return "unknown", stream_item


def _extract_step_payload(node_name: str, update: Any) -> dict[str, Any]:
    update_mapping = _as_mapping(update)
    payload: dict[str, Any] = {}

    if node_name == "retrieve_policy_evidence":
        retrieved = _as_mapping(update_mapping.get("retrieved_evidence"))
        retrieval_data = _as_mapping(retrieved.get("data") or retrieved)
        evidence = retrieval_data.get("evidence") or []
        payload["evidence_count"] = len(evidence) if isinstance(evidence, list) else 0

    if node_name == "assess_risk_and_approval":
        risk = _as_mapping(update_mapping.get("risk_assessment"))
        if risk.get("risk_level"):
            payload["risk_level"] = risk["risk_level"]

    if node_name == "generate_recommendation":
        recommendation = _as_mapping(update_mapping.get("recommendation_draft"))
        summary = recommendation.get("recommended_action") or recommendation.get("short_summary")
        if summary:
            payload["short_summary"] = str(summary)

    trace_steps = update_mapping.get("trace_steps")
    if isinstance(trace_steps, list) and trace_steps:
        tool_name = trace_steps[-1].get("tool_name")
        if tool_name:
            payload["tool_name"] = tool_name

    return payload


def _dedupe_evidence_refs(ref_groups: Any) -> list[dict[str, Any]]:
    seen: set[str] = set()
    evidence: list[dict[str, Any]] = []
    for refs in ref_groups:
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            key = str(ref.get("chunk_id") or json.dumps(ref, sort_keys=True, default=str))
            if key in seen:
                continue
            seen.add(key)
            evidence.append(ref)
    return evidence


def _with_approval_gate_step(trace_steps: list[dict[str, Any]], completed_at: datetime) -> list[dict[str, Any]]:
    steps = list(trace_steps)
    if not any(step.get("node") == "approval_gate" for step in steps):
        steps.append(
            {
                "node": "approval_gate",
                "status": "interrupted",
                "started_at": completed_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "latency_ms": 0,
                "provider_latency_ms": None,
                "retry_count": 0,
                "metrics_json": None,
            }
        )
    return steps


def _ensure_can_view_run(run: AgentRun | None, *, user: User) -> None:
    if not run:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})
    if run.user_id != user.id and user.role not in SUPERVISOR_ROLES:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})


def _parse_run_id(run_id: str) -> UUID:
    try:
        return UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"}) from exc


def _checkpoint_thread_id(*, user: User, thread_id: str) -> str:
    return f"{user.tenant_id}:{user.id}:{thread_id}"


def _is_graph_interrupt(exc: Exception) -> bool:
    return isinstance(exc, GraphInterrupt) or "GraphInterrupt" in type(exc).__name__


def _is_interrupt_payload(value: Any) -> bool:
    value_mapping = _as_mapping(value)
    return "__interrupt__" in value_mapping


def _is_interrupt_stream_item(node_name: str, update: Any) -> bool:
    return node_name == "__interrupt__" or _is_interrupt_payload(update)


def _extract_interrupt_data(exc_or_data: Any) -> dict[str, Any]:
    if isinstance(exc_or_data, dict):
        interrupts = exc_or_data.get("__interrupt__") or []
        if interrupts:
            first = interrupts[0]
            value = getattr(first, "value", first)
            return value if isinstance(value, dict) else {}
        return exc_or_data

    if isinstance(exc_or_data, (list, tuple)) and exc_or_data:
        first = exc_or_data[0]
        value = getattr(first, "value", first)
        if isinstance(value, dict):
            return value

    args = getattr(exc_or_data, "args", ())
    for arg in args:
        if isinstance(arg, dict):
            return arg
        if isinstance(arg, (list, tuple)) and arg:
            first = arg[0]
            value = getattr(first, "value", first)
            if isinstance(value, dict):
                return value
    return {}


def _parse_expires_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            parsed = None
        if parsed:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) + timedelta(hours=24)


def _count_tokens(trace_steps: list[dict[str, Any]]) -> int | None:
    total = sum((step.get("prompt_tokens") or 0) + (step.get("completion_tokens") or 0) for step in trace_steps)
    return total or None


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}
