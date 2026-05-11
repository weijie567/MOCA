"""Refund agent API endpoint."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, Security
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import build_trace_summary, write_agent_run, write_agent_steps
from src.api.schemas.agent import ChatRequest, ChatResponse, TraceSummary
from src.api.schemas.common import ApiResponse, ErrorDetail, INTERNAL_ERROR
from src.auth.permissions import get_current_user
from src.db.models import User
from src.db.session import get_session


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
    except Exception:
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
