"""Refund agent API endpoint."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Security
from langgraph.errors import GraphInterrupt
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import build_trace_summary, write_agent_run, write_agent_steps
from src.api.routers.agent_runs import (
    APPROVAL_NOT_EXECUTABLE,
    ApprovalInterruptValidationError,
    _create_approval_wait_payload_from_interrupt,
    _schedule_memory_write_after_response,
    _session_factory_from_session,
)
from src.api.schemas.agent import ChatRequest, ChatResponse, TraceSummary
from src.api.schemas.common import ApiResponse, ErrorDetail, INTERNAL_ERROR
from src.auth.permissions import get_current_user
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.db.models import User
from src.db.session import get_session
from src.memory.thread_summary import ThreadRollingSummaryService
from src.platform.context_projections import project_to_legacy_agent_state_identity
from src.platform.trusted_context import TrustedContext, TrustedContextFactory


router = APIRouter(tags=["agent"])
logger = logging.getLogger(__name__)


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
    trusted_context = TrustedContextFactory.create_from_request(
        user=user,
        verified_token_scopes=getattr(request.state, "verified_token_scopes", None) or [],
        thread_id=body.thread_id,
        run_id=str(run_id),
        trace_id=getattr(request.state, "trace_id", None),
        locale=getattr(request.state, "locale", None),
    )
    input_state = {
        "user_query": body.query,
        **_legacy_agent_state_identity(trusted_context),
    }
    config = {
        "configurable": {
            "thread_id": _checkpoint_thread_id(user=user, thread_id=body.thread_id),
            "session": session,
            **_trusted_graph_config(trusted_context),
        }
    }

    try:
        conversation_repository = ConversationRepository(session)
        conversation_service = ConversationService(conversation_repository)
        await write_agent_run(
            session,
            run_id=run_id,
            thread_id=body.thread_id,
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            input_query=body.query,
            final_status="running",
            final_response=None,
            started_at=started_at,
            completed_at=None,
            total_latency_ms=0,
            trace_id=getattr(request.state, "trace_id", None),
        )
        user_message = await conversation_service.append_user_message(
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=body.thread_id,
            run_id=UUID(str(run_id)),
            content=body.query,
            trace_id=getattr(request.state, "trace_id", None),
            prompt_template_version="chat.request.v1",
        )
        config["configurable"]["conversation_message_id"] = str(user_message.message_id)
        config["configurable"]["conversation_thread_id"] = str(user_message.conversation_thread_id)
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
            trace_id=getattr(request.state, "trace_id", None),
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

    trace_summary = build_trace_summary(run_id, final_state, total_ms)
    response_data = ChatResponse(
        response=final_response_text,
        trace_summary=TraceSummary(**trace_summary),
    ).model_dump()

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
            trace_id=getattr(request.state, "trace_id", None),
        )
        await write_agent_steps(session, run_id=run_id, trace_steps=trace_steps)
        await conversation_service.append_assistant_message(
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=body.thread_id,
            run_id=UUID(str(run_id)),
            content=final_response_text,
            trace_id=getattr(request.state, "trace_id", None),
            metadata_json={"status": final_status},
        )
        await ThreadRollingSummaryService(conversation_repository).persist_thread_summary(
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=body.thread_id,
            run_id=UUID(str(run_id)),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Failed to persist completed chat turn")
        return ApiResponse(
            success=False,
            data=response_data,
            error=ErrorDetail(
                code=INTERNAL_ERROR,
                message="回复已生成，但会话记录保存失败，请重试。",
            ),
            trace_id=request.state.trace_id,
        )

    memory_state = {
        **input_state,
        **final_state,
        **_legacy_agent_state_identity(trusted_context),
        "final_response": final_response_text,
    }
    _schedule_memory_write_after_response(
        memory_state,
        session_factory=_session_factory_from_session(session),
        trace_id=request.state.trace_id,
    )
    return ApiResponse(
        success=True,
        data=response_data,
        trace_id=request.state.trace_id,
    )


def _checkpoint_thread_id(*, user: User, thread_id: str) -> str:
    return f"{user.tenant_id}:{user.id}:{thread_id}"


def _trusted_graph_config(trusted_context: TrustedContext) -> dict[str, Any]:
    # Compatibility keys stay derived from canonical trusted_context for existing callers.
    return {
        "trusted_context": trusted_context.model_dump(mode="json"),
        "permissions": list(trusted_context.permissions),
        "merchant_scope": trusted_context.merchant_scope.model_dump(mode="json"),
        "trace_id": trusted_context.trace_id or "",
        "session_id": trusted_context.session_id,
    }


def _legacy_agent_state_identity(trusted_context: TrustedContext) -> dict[str, str | None]:
    identity = project_to_legacy_agent_state_identity(trusted_context)
    legacy_keys = ("tenant_id", "user_id", "role", "thread_id", "current_run_id")
    return {key: identity[key] for key in legacy_keys}


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
    pre_interrupt_steps = list(snapshot_values.get("trace_steps") or [])
    run_id = str(interrupt_data.get("run_id") or snapshot_values.get("current_run_id") or fallback_run_id)
    if not any(step.get("node") == "approval_gate" for step in pre_interrupt_steps):
        pre_interrupt_steps.append(
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
        trace_id=getattr(request.state, "trace_id", None),
    )
    if pre_interrupt_steps:
        await write_agent_steps(session, run_id=run_id, trace_steps=pre_interrupt_steps)

    # ApprovalService request creation is centralized in the shared interrupt helper.
    try:
        wait_payload = await _create_approval_wait_payload_from_interrupt(
            session=session,
            user=user,
            run_id=UUID(run_id),
            thread_id=body.thread_id,
            interrupt_data=interrupt_data,
        )
    except ApprovalInterruptValidationError as exc:
        await session.commit()
        message = "Approval request is missing executable snapshot bindings"
        return ApiResponse(
            success=False,
            data={
                "status": "interrupted",
                "run_id": run_id,
                "missing_fields": exc.missing_fields,
            },
            error=ErrorDetail(
                code=APPROVAL_NOT_EXECUTABLE,
                message=message,
                details={"missing_fields": exc.missing_fields},
            ),
            trace_id=getattr(request.state, "trace_id", None),
        )

    await ConversationService(ConversationRepository(session)).append_assistant_message(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id=body.thread_id,
        run_id=UUID(str(run_id)),
        content="请求需要审批，已暂停等待处理。",
        trace_id=getattr(request.state, "trace_id", None),
        metadata_json={"status": "interrupted"},
    )
    await session.commit()
    return ApiResponse(
        success=True,
        data=wait_payload,
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
    trace_id: str | None = None,
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
            trace_id=trace_id,
        )
        await ConversationService(ConversationRepository(session)).append_assistant_message(
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=body.thread_id,
            run_id=UUID(str(run_id)),
            content=final_response,
            trace_id=trace_id,
            metadata_json={"status": "error"},
        )
        await session.commit()
    except Exception:
        await session.rollback()
