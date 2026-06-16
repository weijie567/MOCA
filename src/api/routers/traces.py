from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.approvals import ApprovalResponse, TraceResponse
from src.api.schemas.common import ApiResponse
from src.auth.permissions import get_current_user
from src.db.models import ApprovalRequest, User
from src.db.session import get_session
from src.repositories.trace_repo import TraceRepository, _safe_draft_outcome, _safe_proposed_action
from src.replay.service import ReplayService


router = APIRouter(tags=["traces"])

SUPERVISOR_ROLES = {"supervisor", "admin", "approval_manager", "manager"}


@router.get("/{run_id}/trace", response_model=ApiResponse)
async def get_run_trace(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
    run_uuid = _parse_run_id(run_id)
    repo = TraceRepository(session)
    run = await repo.get_run(run_uuid, user.tenant_id)

    if not run:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})

    if run.user_id != user.id and user.role not in SUPERVISOR_ROLES:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})

    steps = await repo.get_steps(run_uuid)
    approvals = await repo.get_approvals(run_uuid)
    approval_steps = await repo.get_approval_steps([approval.id for approval in approvals])
    drafts = await repo.get_action_drafts(run_uuid)
    timeline = repo.build_timeline(steps, approvals, approval_steps, drafts)

    trace_data = TraceResponse(
        run_id=str(run.id),
        thread_id=run.thread_id,
        final_status=run.final_status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_latency_ms=run.total_latency_ms,
        steps=[
            {
                "node": step.node_name,
                "status": step.status,
                "latency_ms": step.latency_ms,
                "tool_name": step.tool_name,
            }
            for step in steps
        ],
        approvals=[_to_approval_response(approval) for approval in approvals],
        action_drafts=[
            {
                "id": str(draft.id),
                "action_type": draft.action_type,
                "status": draft.status,
                "draft_outcome": _safe_draft_outcome(draft),
            }
            for draft in drafts
        ],
        timeline=timeline,
    )

    return ApiResponse(
        success=True,
        data=trace_data.model_dump(mode="json"),
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get("/{run_id}/replay", response_model=ApiResponse)
async def get_run_replay(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
    run_uuid = _parse_run_id(run_id)
    repo = TraceRepository(session)
    run = await repo.get_run(run_uuid, user.tenant_id)

    if not run:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})

    if run.user_id != user.id and user.role not in SUPERVISOR_ROLES:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})

    replay_response = await ReplayService(session).get_replay(run_uuid)
    return ApiResponse(
        success=True,
        data=replay_response,
        trace_id=getattr(request.state, "trace_id", None),
    )


def _parse_run_id(run_id: str) -> UUID:
    try:
        return UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"}) from exc


def _to_approval_response(approval: ApprovalRequest) -> ApprovalResponse:
    return ApprovalResponse(
        id=str(approval.id),
        run_id=str(approval.run_id),
        thread_id=approval.thread_id,
        status=approval.status,
        revision=approval.revision,
        request_version=approval.version,
        action_payload_hash=approval.action_payload_hash,
        safety_snapshot_ref=approval.safety_snapshot_ref,
        safety_snapshot_hash=approval.safety_snapshot_hash,
        clarification_request_id=str(approval.clarification_request_id)
        if approval.clarification_request_id
        else None,
        superseded_by_request_id=str(approval.superseded_by_request_id)
        if approval.superseded_by_request_id
        else None,
        requested_by=str(approval.requested_by),
        proposed_action=_safe_proposed_action(approval.proposed_action),
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
