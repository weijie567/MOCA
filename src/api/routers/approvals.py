from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import append_agent_steps, update_agent_run_status
from src.api.schemas.approvals import ApprovalListResponse, ApprovalResponse, DecideRequest
from src.api.schemas.common import ApiResponse
from src.approvals.schemas import ApprovalDecisionCommand
from src.approvals.service import ApprovalService, ApprovalTransitionError
from src.auth.permissions import get_current_user
from src.db.models import AgentRun, User
from src.db.session import get_session


router = APIRouter(tags=["approvals"])

APPROVAL_ROLES = {"admin", "manager"}


@router.post("/{approval_id}/decide", response_model=ApiResponse)
async def decide_approval(
    approval_id: str,
    body: DecideRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    if user.role not in APPROVAL_ROLES:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Insufficient role for approval"},
        )

    approval_uuid = _parse_approval_id(approval_id)
    service = ApprovalService(session)
    try:
        context = await service.get_decision_context(approval_uuid, user.tenant_id)
    except ApprovalTransitionError as exc:
        raise _approval_http_error(exc) from exc
    if context is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})

    approval = context.request
    if approval.requested_by == user.id:
        raise HTTPException(status_code=403, detail={"code": "SELF_APPROVAL", "message": "Cannot approve own request"})

    command = ApprovalDecisionCommand(
        approval_id=approval.id,
        tenant_id=user.tenant_id,
        run_id=approval.run_id,
        thread_id=approval.thread_id,
        level_id=context.level.id,
        assignment_id=context.assignment.id,
        actor_id=user.id,
        actor_role=user.role,
        decision_type=body.decision_type,
        expected_request_version=body.expected_request_version,
        expected_level_version=body.expected_level_version,
        expected_assignment_version=body.expected_assignment_version,
        expected_revision=body.expected_revision,
        action_payload_hash=body.action_payload_hash,
        safety_snapshot_hash=body.safety_snapshot_hash,
        reason=body.reason,
        edited_action=body.edited_action,
        response_text=body.response_text,
    )

    try:
        result = await service.decide(command)
    except ApprovalTransitionError as exc:
        raise _approval_http_error(exc) from exc

    if result.resume_payload:
        await _resume_graph_after_decision(
            request=request,
            session=session,
            result=result,
        )

    await session.commit()
    return ApiResponse(
        success=True,
        data=_to_response(approval).model_dump(mode="json"),
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get("/{approval_id}", response_model=ApiResponse)
async def get_approval(
    approval_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    approval = await ApprovalService(session).get_request(_parse_approval_id(approval_id), user.tenant_id)
    if not approval:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})
    return ApiResponse(
        success=True,
        data=_to_response(approval).model_dump(mode="json"),
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get("", response_model=ApiResponse)
async def list_pending_approvals(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    approvals = await ApprovalService(session).list_pending_requests(user.tenant_id)
    payload = ApprovalListResponse(approvals=[_to_response(approval) for approval in approvals], total=len(approvals))
    return ApiResponse(
        success=True, data=payload.model_dump(mode="json"), trace_id=getattr(request.state, "trace_id", None)
    )


async def _resume_graph_after_decision(*, request: Request, session: AsyncSession, result) -> None:
    graph = request.app.state.agent_graph
    config = {"configurable": {"thread_id": result.graph_thread_id, "session": session}}
    t0 = time.perf_counter()
    final_state = await graph.ainvoke(Command(resume=result.resume_payload), config)
    resume_latency_ms = round((time.perf_counter() - t0) * 1000)

    run_id = str(result.run_id)
    final_response_text = final_state.get("final_response")
    final_status = "completed"
    if final_state.get("node_errors") or not final_response_text:
        final_status = "error"
    run = await session.get(AgentRun, result.run_id)
    total_latency_ms = (run.total_latency_ms if run and run.total_latency_ms else 0) + resume_latency_ms
    await update_agent_run_status(
        session,
        run_id=run_id,
        final_status=final_status,
        final_response=final_response_text,
        completed_at=datetime.now(UTC),
        total_latency_ms=total_latency_ms,
    )

    trace_steps = final_state.get("trace_steps") or []
    pre_interrupt_count = next(
        (idx + 1 for idx, step in enumerate(trace_steps) if step.get("node") == "approval_gate"),
        len(trace_steps),
    )
    if pre_interrupt_count < len(trace_steps):
        await append_agent_steps(
            session,
            run_id=run_id,
            trace_steps=trace_steps,
            start_index=pre_interrupt_count,
        )


def _approval_http_error(exc: ApprovalTransitionError) -> HTTPException:
    if exc.code == "approval_not_found":
        return HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})
    if exc.code == "approval_forbidden":
        return HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": str(exc)})
    if exc.code == "approval_hash_mismatch":
        return HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Approval hash mismatch"})
    if exc.code == "approval_not_executable":
        return HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Approval is not executable"})
    return HTTPException(status_code=409, detail={"code": "CONFLICT", "message": str(exc)})


def _parse_approval_id(approval_id: str) -> UUID:
    try:
        return UUID(approval_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"}) from exc


def _to_response(approval) -> ApprovalResponse:
    return ApprovalResponse(
        id=str(approval.id),
        run_id=str(approval.run_id),
        status=approval.status,
        revision=approval.revision,
        request_version=approval.version,
        action_payload_hash=approval.action_payload_hash,
        safety_snapshot_ref=approval.safety_snapshot_ref,
        safety_snapshot_hash=approval.safety_snapshot_hash,
        requested_by=str(approval.requested_by),
        proposed_action=approval.proposed_action,
        risk_level=approval.risk_level,
        risk_rule_ref=approval.risk_rule_ref,
        risk_reason=approval.risk_reason,
        decision=approval.decision,
        reason=approval.reason,
        decided_by=str(approval.decided_by) if approval.decided_by else None,
        decided_at=approval.decided_at,
        expires_at=approval.expires_at,
        created_at=approval.created_at,
    )
