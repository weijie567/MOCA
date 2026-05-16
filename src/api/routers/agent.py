"""Refund agent API endpoint."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Security
from langgraph.errors import GraphInterrupt
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import build_trace_summary, write_agent_run, write_agent_steps
from src.api.schemas.agent import ChatRequest, ChatResponse, TraceSummary
from src.api.schemas.common import ApiResponse, ErrorDetail, INTERNAL_ERROR
from src.auth.permissions import get_current_user
from src.db.models import User
from src.db.session import get_session
from src.repositories.approval_repo import ApprovalRepository


router = APIRouter(tags=["agent"])


@router.post("/chat", response_model=ApiResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
    """Submit a refund/order question to the agent."""
    graph = request.app.state.agent_graph
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    run_id = getattr(request.state, "run_id", str(uuid.uuid4()))

    input_state = {
        "user_query": body.query,
        "thread_id": body.thread_id,
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.id),
        "role": user.role,
    }
    config = {
        "configurable": {
            "thread_id": _checkpoint_thread_id(user=user, thread_id=body.thread_id),
            "session": session,
        }
    }

    try:
        final_state = await graph.ainvoke(input_state, config)
    except Exception as exc:
        if _is_graph_interrupt(exc):
            return await _handle_interrupt(
                exc,
                request=request,
                session=session,
                user=user,
                body=body,
                fallback_run_id=run_id,
                started_at=started_at,
                t0=t0,
            )
        total_ms = round((time.perf_counter() - t0) * 1000)
        completed_at = datetime.now(timezone.utc)
        fallback_response = "系统处理出现问题，请稍后重试或联系人工客服。"
        trace_summary = {
            "run_id": run_id,
            "intent": "unknown",
            "nodes_executed": [],
            "tools_called": [],
            "evidence_count": 0,
            "risk_level": "unknown",
            "total_latency_ms": total_ms,
            "final_status": "error",
        }
        await _persist_error_run(
            session=session,
            run_id=run_id,
            body=body,
            user=user,
            started_at=started_at,
            completed_at=completed_at,
            total_latency_ms=total_ms,
            final_response=fallback_response,
        )
        return ApiResponse(
            success=False,
            data=ChatResponse(response=fallback_response, trace_summary=TraceSummary(**trace_summary)).model_dump(),
            error=ErrorDetail(code=INTERNAL_ERROR, message=fallback_response),
            trace_id=request.state.trace_id,
        )

    if isinstance(final_state, dict) and "__interrupt__" in final_state:
        return await _handle_interrupt(
            final_state,
            request=request,
            session=session,
            user=user,
            body=body,
            fallback_run_id=run_id,
            started_at=started_at,
            t0=t0,
        )

    total_ms = round((time.perf_counter() - t0) * 1000)
    completed_at = datetime.now(timezone.utc)
    run_id = final_state.get("current_run_id") or run_id
    trace_steps = final_state.get("trace_steps") or []
    final_response_text = final_state.get("final_response") or "处理完成，但未生成回复。"
    final_status = build_trace_summary(run_id, final_state, total_ms)["final_status"]
    total_tokens = _count_tokens(trace_steps)

    try:
        await write_agent_run(
            session,
            run_id=run_id,
            thread_id=body.thread_id,
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            input_query=body.query,
            final_status=final_status,
            final_response=final_response_text,
            started_at=started_at,
            completed_at=completed_at,
            total_latency_ms=total_ms,
            total_tokens=total_tokens,
        )
        await write_agent_steps(session, run_id=run_id, trace_steps=trace_steps)
        await session.commit()
    except Exception:
        await session.rollback()

    trace_summary = build_trace_summary(run_id, final_state, total_ms)
    return ApiResponse(
        success=True,
        data=ChatResponse(
            response=final_response_text,
            trace_summary=TraceSummary(**trace_summary),
        ).model_dump(),
        trace_id=request.state.trace_id,
    )


def _checkpoint_thread_id(*, user: User, thread_id: str) -> str:
    return f"{user.tenant_id}:{user.id}:{thread_id}"


def _is_graph_interrupt(exc: Exception) -> bool:
    return isinstance(exc, GraphInterrupt) or "GraphInterrupt" in type(exc).__name__


async def _handle_interrupt(
    exc_or_data: Any,
    *,
    request: Request,
    session: AsyncSession,
    user: User,
    body: ChatRequest,
    fallback_run_id: str,
    started_at: datetime,
    t0: float,
) -> ApiResponse:
    total_ms = round((time.perf_counter() - t0) * 1000)
    completed_at = datetime.now(timezone.utc)
    interrupt_data = _extract_interrupt_data(exc_or_data)

    graph = request.app.state.agent_graph
    checkpoint_tid = _checkpoint_thread_id(user=user, thread_id=body.thread_id)
    state_snapshot = await graph.aget_state({"configurable": {"thread_id": checkpoint_tid}})
    snapshot_values = getattr(state_snapshot, "values", None) or {}
    pre_interrupt_steps = snapshot_values.get("trace_steps") or []
    run_id = str(interrupt_data.get("run_id") or snapshot_values.get("current_run_id") or fallback_run_id)

    await write_agent_run(
        session,
        run_id=run_id,
        thread_id=body.thread_id,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        input_query=body.query,
        final_status="interrupted",
        final_response=None,
        started_at=started_at,
        completed_at=completed_at,
        total_latency_ms=total_ms,
        total_tokens=_count_tokens(pre_interrupt_steps),
    )
    if pre_interrupt_steps:
        await write_agent_steps(session, run_id=run_id, trace_steps=pre_interrupt_steps)

    approval_repo = ApprovalRepository(session)
    expires_at = _parse_expires_at(interrupt_data.get("expires_at"))
    approval = await approval_repo.create(
        run_id=UUID(run_id),
        tenant_id=user.tenant_id,
        requested_by=user.id,
        proposed_action=interrupt_data.get("proposed_action") or {},
        risk_level=interrupt_data.get("risk_level") or "high",
        risk_rule_ref=interrupt_data.get("risk_rule_ref"),
        risk_reason=interrupt_data.get("risk_reason"),
        expires_at=expires_at,
        thread_id=body.thread_id,
    )
    await approval_repo.add_step(approval.id, event_type="created", actor_id=user.id)
    await session.commit()

    return ApiResponse(
        success=True,
        data={
            "status": "interrupted",
            "message": "High-risk action requires approval",
            "approval_id": str(approval.id),
            "run_id": run_id,
            "proposed_action": interrupt_data.get("proposed_action"),
            "risk_level": interrupt_data.get("risk_level"),
            "expires_at": expires_at.isoformat(),
        },
        trace_id=getattr(request.state, "trace_id", None),
    )


def _extract_interrupt_data(exc_or_data: Any) -> dict[str, Any]:
    if isinstance(exc_or_data, dict):
        interrupts = exc_or_data.get("__interrupt__") or []
        if interrupts:
            first = interrupts[0]
            value = getattr(first, "value", first)
            return value if isinstance(value, dict) else {}
        return exc_or_data

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


async def _persist_error_run(
    *,
    session: AsyncSession,
    run_id: str,
    body: ChatRequest,
    user: User,
    started_at: datetime,
    completed_at: datetime,
    total_latency_ms: int,
    final_response: str,
) -> None:
    try:
        await write_agent_run(
            session,
            run_id=run_id,
            thread_id=body.thread_id,
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            input_query=body.query,
            final_status="error",
            final_response=final_response,
            started_at=started_at,
            completed_at=completed_at,
            total_latency_ms=total_latency_ms,
            error_summary="graph invocation failed",
        )
        await session.commit()
    except Exception:
        await session.rollback()
