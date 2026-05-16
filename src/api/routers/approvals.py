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
from src.auth.permissions import get_current_user
from src.db.models import User
from src.db.session import get_session
from src.repositories.approval_repo import ApprovalRepository


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
    repo = ApprovalRepository(session)
    approval = await repo.get_by_id(approval_uuid, user.tenant_id)
    if not approval:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})

    if approval.requested_by == user.id:
        raise HTTPException(status_code=403, detail={"code": "SELF_APPROVAL", "message": "Cannot approve own request"})

    if approval.expires_at < datetime.now(UTC):
        await repo.mark_expired(approval.id, user.tenant_id)
        await repo.add_step(approval.id, event_type="expired")
        await session.commit()
        raise HTTPException(status_code=409, detail={"code": "EXPIRED", "message": "Approval has expired"})

    was_pending = approval.status == "pending"
    try:
        updated = await repo.decide(
            approval.id,
            user.tenant_id,
            decision=body.decision,
            reason=body.reason,
            decided_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": str(exc)}) from exc

    event_type = "approved" if body.decision == "approve" else "rejected"
    await repo.add_step(approval.id, event_type=event_type, actor_id=user.id)

    if was_pending:
        graph = request.app.state.agent_graph
        checkpoint_tid = f"{approval.tenant_id}:{approval.requested_by}:{approval.thread_id}"
        config = {"configurable": {"thread_id": checkpoint_tid, "session": session}}
        resume_payload = {
            "approval_id": str(approval.id),
            "decision": body.decision,
            "reason": body.reason,
            "decided_by": str(user.id),
            "decided_at": datetime.now(UTC).isoformat(),
        }

        t0 = time.perf_counter()
        final_state = await graph.ainvoke(Command(resume=resume_payload), config)
        resume_latency_ms = round((time.perf_counter() - t0) * 1000)

        run_id = str(approval.run_id)
        final_response_text = final_state.get("final_response")
        final_status = "error" if final_state.get("node_errors") else "completed"
        await update_agent_run_status(
            session,
            run_id=run_id,
            final_status=final_status,
            final_response=final_response_text,
            completed_at=datetime.now(UTC),
            total_latency_ms=resume_latency_ms,
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
        await repo.add_step(approval.id, event_type="resumed")

    await session.commit()
    return ApiResponse(
        success=True,
        data=_to_response(updated).model_dump(mode="json"),
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get("/{approval_id}", response_model=ApiResponse)
async def get_approval(
    approval_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    repo = ApprovalRepository(session)
    approval = await repo.get_by_id(_parse_approval_id(approval_id), user.tenant_id)
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
    repo = ApprovalRepository(session)
    approvals = await repo.get_pending_by_tenant(user.tenant_id)
    payload = ApprovalListResponse(approvals=[_to_response(approval) for approval in approvals], total=len(approvals))
    return ApiResponse(success=True, data=payload.model_dump(mode="json"), trace_id=getattr(request.state, "trace_id", None))


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
