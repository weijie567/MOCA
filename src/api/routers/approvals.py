from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from langgraph.errors import GraphInterrupt
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.action_draft import action_draft
from src.agent.routing import project_action_draft_terminal
from src.agent.trace import append_agent_steps, update_agent_run_status
from src.api.routers.agent_runs import (
    ApprovalInterruptValidationError,
    _create_approval_wait_payload_from_interrupt,
    _extract_interrupt_data,
)
from src.api.services.agent_run_memory import (
    build_agent_run_finalizer_input_state,
    finalize_completed_agent_run_memory,
    persist_agent_run_memory_finalize_trace_steps,
)
from src.api.schemas.approvals import ApprovalInfoRequest, ApprovalListResponse, ApprovalResponse, DecideRequest
from src.api.schemas.common import ApiResponse
from src.approvals.events import emit_approval_resumed
from src.approvals.schemas import (
    ApprovalDecisionCommand,
    ApprovalDecisionResult,
    ApprovalInfoCommand,
    TrustedApprovalResultV1,
)
from src.approvals.service import ApprovalService, ApprovalTransitionError
from src.auth.permissions import get_current_user
from src.db.models import (
    ActionDraft,
    AgentRun,
    AgentStep,
    ApprovalAssignment,
    ApprovalDecision,
    ApprovalEvent,
    ApprovalLevel,
    ApprovalRequest,
    User,
)
from src.db.session import get_session
from src.platform.context_projections import project_to_legacy_agent_state_identity
from src.platform.trusted_context import TrustedContext, TrustedContextFactory


router = APIRouter(tags=["approvals"])

APPROVAL_ROLES = {"admin", "manager"}
RESUMABLE_DECISIONS = {"accept", "approve", "reject", "ignore", "edit"}
RESUME_RETRY_STATUSES = {"approved", "rejected", "cancelled", "superseded"}
RESUME_INCOMPLETE_STATUSES = {"attempted", "failed"}
ACTION_DRAFT_PERMISSION = "tool:create_coupon_grant_draft"
CANONICAL_RISK_ROUTE = "risk_gate"
HISTORICAL_RETRY_ROUTE_TO_CANONICAL = {"assess_risk_and_approval": CANONICAL_RISK_ROUTE}


@router.post("/{approval_id}/decide", response_model=ApiResponse)
async def decide_approval(
    approval_id: str,
    body: DecideRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    _assert_approval_reviewer(user)

    approval_uuid = _parse_approval_id(approval_id)
    service = ApprovalService(session)
    scoped_approval = await _get_scoped_approval_or_404(service, user, approval_uuid)
    if scoped_approval.requested_by == user.id:
        raise HTTPException(
            status_code=403, detail={"code": "SELF_APPROVAL", "message": "Cannot approve own request"}
        )
    try:
        retry_result = await _recoverable_resume_retry_result(
            session=session,
            service=service,
            approval_id=approval_uuid,
            tenant_id=user.tenant_id,
            body=body,
        )
    except ApprovalTransitionError as exc:
        raise _approval_http_error(exc) from exc
    if retry_result is not None:
        approval = await session.get(ApprovalRequest, retry_result.approval_id)
        if approval is None:
            raise _approval_not_found()
        _assert_approval_scope(user, approval)
        if approval.requested_by == user.id:
            raise HTTPException(
                status_code=403, detail={"code": "SELF_APPROVAL", "message": "Cannot approve own request"}
            )
        await _run_resume_lifecycle(
            request=request,
            session=session,
            result=retry_result,
            actor_id=user.id,
            actor_user=user,
        )
        await session.refresh(approval)
        return ApiResponse(
            success=True,
            data=_to_response(
                approval,
                result=retry_result,
            ).model_dump(mode="json"),
            trace_id=getattr(request.state, "trace_id", None),
        )

    try:
        context = await service.get_decision_context(approval_uuid, user.tenant_id)
    except ApprovalTransitionError as exc:
        raise _approval_http_error(exc) from exc
    if context is None:
        terminal_request = await service.get_request(approval_uuid, user.tenant_id)
        if terminal_request is None:
            raise _approval_not_found()
        _assert_approval_scope(user, terminal_request)
        raise _approval_http_error(ApprovalTransitionError("approval_conflict"))

    approval = context.request
    _assert_approval_scope(user, approval)
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

    if _should_resume_graph(result):
        await session.commit()
        await _run_resume_lifecycle(
            request=request,
            session=session,
            result=result,
            actor_id=user.id,
            actor_user=user,
        )
    else:
        await session.commit()
    return ApiResponse(
        success=True,
        data=_to_response(
            approval,
            result=result,
            decision_context=None,
        ).model_dump(mode="json"),
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.post("/{approval_id}/info", response_model=ApiResponse)
async def attach_approval_info(
    approval_id: str,
    body: ApprovalInfoRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    _assert_approval_reviewer(user)

    approval_uuid = _parse_approval_id(approval_id)
    service = ApprovalService(session)
    approval = await _get_scoped_approval_or_404(service, user, approval_uuid)
    command = ApprovalInfoCommand(
        approval_id=approval_uuid,
        clarification_request_id=body.clarification_request_id,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        actor_role=user.role,
        thread_id=body.thread_id,
        expected_request_version=body.expected_request_version,
        expected_level_version=body.expected_level_version,
        expected_assignment_version=body.expected_assignment_version,
        expected_revision=body.expected_revision,
        info_payload=body.info_payload,
    )

    try:
        result = await service.attach_info(command)
    except ApprovalTransitionError as exc:
        raise _approval_http_error(exc) from exc

    approval = await service.get_request(result.approval_id, user.tenant_id)
    if approval is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})

    await session.commit()
    return ApiResponse(
        success=True,
        data=_to_response(
            approval,
            result=result,
        ).model_dump(mode="json"),
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get("/{approval_id}", response_model=ApiResponse)
async def get_approval(
    approval_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    _assert_approval_reviewer(user)
    service = ApprovalService(session)
    approval_uuid = _parse_approval_id(approval_id)
    approval = await _get_scoped_approval_or_404(service, user, approval_uuid)
    decision_context = None
    if approval.status == "pending":
        try:
            context = await service.get_decision_context(approval_uuid, user.tenant_id)
        except ApprovalTransitionError as exc:
            raise _approval_http_error(exc) from exc
        if context is None:
            raise _approval_http_error(ApprovalTransitionError("approval_conflict"))
        decision_context = context.project()
    return ApiResponse(
        success=True,
        data=_to_response(approval, decision_context=decision_context).model_dump(mode="json"),
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get("", response_model=ApiResponse)
async def list_pending_approvals(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    _assert_approval_reviewer(user)
    service = ApprovalService(session)
    approvals = await service.list_pending_requests(user.tenant_id)
    approvals = [approval for approval in approvals if _approval_scope_allowed(user, approval)]
    responses = []
    try:
        for approval in approvals:
            context = await service.get_decision_context(approval.id, user.tenant_id)
            if context is not None:
                responses.append(_to_response(approval, decision_context=context.project()))
    except ApprovalTransitionError as exc:
        raise _approval_http_error(exc) from exc
    payload = ApprovalListResponse(approvals=responses, total=len(responses))
    return ApiResponse(
        success=True, data=payload.model_dump(mode="json"), trace_id=getattr(request.state, "trace_id", None)
    )


async def _run_resume_lifecycle(
    *, request: Request, session: AsyncSession, result: ApprovalDecisionResult, actor_id: UUID, actor_user: User
) -> None:
    try:
        if await _record_resume_completed_event_once(
            session=session,
            result=result,
            actor_id=actor_id,
            require_terminal_finalizer=True,
        ):
            return

        await _record_resume_event(
            session=session,
            result=result,
            actor_id=actor_id,
            resume_status="attempted",
        )
        await session.commit()

        await _resume_graph_after_decision(
            request=request,
            session=session,
            result=result,
            actor_user=actor_user,
        )
        run = await session.get(AgentRun, result.run_id)
        require_terminal_finalizer = run is not None and run.final_status == "completed"
        if not await _record_resume_completed_event_once(
            session=session,
            result=result,
            actor_id=actor_id,
            require_terminal_finalizer=require_terminal_finalizer,
        ):
            raise RuntimeError("approval resume completed run missing terminal finalizer evidence")
    except Exception as exc:
        await session.rollback()
        await _record_resume_event(
            session=session,
            result=result,
            actor_id=actor_id,
            resume_status="failed",
            error=exc,
        )
        await session.commit()
        raise HTTPException(
            status_code=500,
            detail={
                "code": "APPROVAL_RESUME_FAILED",
                "message": "Approval decision was saved, but graph resume did not complete. Retry the decision to reconcile.",
            },
        ) from exc


async def _resume_graph_after_decision(
    *, request: Request, session: AsyncSession, result: ApprovalDecisionResult, actor_user: User
) -> None:
    graph = request.app.state.agent_graph
    config = _resume_graph_config(request=request, session=session, result=result, actor_user=actor_user)
    t0 = time.perf_counter()
    try:
        final_state = await graph.ainvoke(Command(resume=result.resume_payload), config)
    except GraphInterrupt as exc:
        resume_latency_ms = round((time.perf_counter() - t0) * 1000)
        await _handle_resume_interrupt(
            exc,
            request=request,
            session=session,
            result=result,
            resume_latency_ms=resume_latency_ms,
        )
        return
    resume_latency_ms = round((time.perf_counter() - t0) * 1000)
    if isinstance(final_state, dict) and final_state.get("__interrupt__"):
        await _handle_resume_interrupt(
            final_state,
            request=request,
            session=session,
            result=result,
            resume_latency_ms=resume_latency_ms,
        )
        return
    final_state = await _reconcile_approved_action_draft(
        session=session,
        result=result,
        final_state=final_state,
        config=config,
    )

    run_id = str(result.run_id)
    final_response_text = final_state.get("final_response")
    action_terminal = project_action_draft_terminal(final_state)
    final_status = "completed"
    if action_terminal.applies and action_terminal.status == "error":
        final_status = "error"
        final_response_text = str(action_terminal.safe_message)
        final_state["final_response"] = final_response_text
    elif final_state.get("node_errors") or not final_response_text:
        final_status = "error"
    run = await session.get(AgentRun, result.run_id)
    total_latency_ms = (run.total_latency_ms if run and run.total_latency_ms else 0) + resume_latency_ms
    status_update = {
        "final_status": final_status,
        "final_response": final_response_text,
        "completed_at": datetime.now(UTC),
        "total_latency_ms": total_latency_ms,
        "trace_id": getattr(request.state, "trace_id", None),
    }
    if final_status == "error":
        status_update.update(
            reason_code="approval_resume_error",
            error_code="approval_resume_error",
        )
    else:
        status_update.update(
            reason_code="approval_resume_completed",
            error_code=None,
        )
    await update_agent_run_status(
        session,
        run_id=run_id,
        **status_update,
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

    if final_status == "completed" and final_response_text:
        if run is None:
            raise RuntimeError("approval resume run missing for terminal finalization")
        requester = await session.get(User, run.user_id)
        if requester is None:
            raise RuntimeError("approval resume requester missing for terminal finalization")
        input_state = build_agent_run_finalizer_input_state(run, requester)
        finalizer_result = await finalize_completed_agent_run_memory(
            session=session,
            run=run,
            user=requester,
            input_state=input_state,
            final_state=final_state,
            final_status=final_status,
            final_response=str(final_response_text),
            trace_steps=trace_steps,
            trace_id=getattr(request.state, "trace_id", None),
        )
        await session.commit()
        await persist_agent_run_memory_finalize_trace_steps(
            session=session,
            run=run,
            prior_trace_steps=trace_steps,
            finalizer_trace_steps=finalizer_result.trace_steps,
            suppress_errors=False,
        )


async def _handle_resume_interrupt(
    exc_or_data: object,
    *,
    request: Request,
    session: AsyncSession,
    result: ApprovalDecisionResult,
    resume_latency_ms: int,
) -> None:
    interrupt_data = _extract_interrupt_data(exc_or_data)
    original_approval = await session.get(ApprovalRequest, result.approval_id)
    if original_approval is None:
        raise RuntimeError("original approval missing for resume interrupt")
    requester = await session.get(User, original_approval.requested_by)
    if requester is None:
        raise RuntimeError("approval requester missing for resume interrupt")
    try:
        await _create_approval_wait_payload_from_interrupt(
            session=session,
            user=requester,
            run_id=result.run_id,
            thread_id=original_approval.thread_id,
            interrupt_data=interrupt_data,
        )
    except ApprovalInterruptValidationError as exc:
        raise RuntimeError(f"approval resume interrupt missing fields: {exc.missing_fields}") from exc

    run = await session.get(AgentRun, result.run_id)
    total_latency_ms = (run.total_latency_ms if run and run.total_latency_ms else 0) + resume_latency_ms
    await update_agent_run_status(
        session,
        run_id=str(result.run_id),
        final_status="interrupted",
        final_response=None,
        completed_at=datetime.now(UTC),
        total_latency_ms=total_latency_ms,
        trace_id=getattr(request.state, "trace_id", None),
        reason_code="approval_resume_interrupted",
        emit_if_unchanged=True,
    )

    if not isinstance(exc_or_data, dict):
        return
    trace_steps = exc_or_data.get("trace_steps") or []
    if not trace_steps:
        return
    pre_interrupt_count = next(
        (idx + 1 for idx, step in enumerate(trace_steps) if step.get("node") == "approval_gate"),
        len(trace_steps),
    )
    if pre_interrupt_count < len(trace_steps):
        await append_agent_steps(
            session,
            run_id=str(result.run_id),
            trace_steps=trace_steps,
            start_index=pre_interrupt_count,
        )


async def _record_resume_event(
    *,
    session: AsyncSession,
    result: ApprovalDecisionResult,
    actor_id: UUID,
    resume_status: str,
    error: Exception | None = None,
) -> ApprovalEvent:
    approval = await session.get(ApprovalRequest, result.approval_id)
    if approval is None:
        raise ApprovalTransitionError("approval_not_found")
    metadata = {
        "resume_status": resume_status,
        "decision_type": result.decision_type,
        "resume_payload_schema": (result.resume_payload or {}).get("schema_version"),
    }
    if error is not None:
        metadata["error_type"] = type(error).__name__
    return await emit_approval_resumed(
        session,
        request=approval,
        actor_id=actor_id,
        metadata=metadata,
        resource_refs={
            "resume_key": _resume_key(result.approval_id, result.revision),
            "approval_revision": result.revision,
            "approval_request_version": result.request_version,
            "approval_decision_ref": f"approval_decision:{result.decision_id}",
        },
        redacted_payload={
            "resume_status": resume_status,
            "decision_type": result.decision_type,
        },
    )


async def _recoverable_resume_retry_result(
    *,
    session: AsyncSession,
    service: ApprovalService,
    approval_id: UUID,
    tenant_id: UUID,
    body: DecideRequest,
) -> ApprovalDecisionResult | None:
    approval = await service.get_request(approval_id, tenant_id)
    if approval is None or approval.status not in RESUME_RETRY_STATUSES:
        return None
    if body.decision_type not in RESUMABLE_DECISIONS:
        return None

    latest_resume_status = await _latest_resume_status(session, approval)
    if latest_resume_status not in RESUME_INCOMPLETE_STATUSES:
        return None

    run = await session.get(AgentRun, approval.run_id)
    if run is not None:
        if run.final_status == "completed":
            if not run.final_response:
                return None
        elif run.final_status not in {"interrupted", "running", "pending"}:
            return None

    if (
        approval.decision != body.decision_type
        or approval.revision != body.expected_revision
        or approval.action_payload_hash != body.action_payload_hash
        or approval.safety_snapshot_hash != body.safety_snapshot_hash
    ):
        raise ApprovalTransitionError("approval_conflict")

    return await _terminal_decision_result_for_retry(session, approval, body)


async def _lock_approval_request_for_resume(session: AsyncSession, approval_id: UUID) -> ApprovalRequest:
    approval = (
        await session.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id).with_for_update())
    ).scalar_one_or_none()
    if approval is None:
        raise ApprovalTransitionError("approval_not_found")
    return approval


async def _record_resume_completed_event_once(
    *,
    session: AsyncSession,
    result: ApprovalDecisionResult,
    actor_id: UUID,
    require_terminal_finalizer: bool,
) -> bool:
    approval = await _lock_approval_request_for_resume(session, result.approval_id)
    latest_resume_status = await _latest_resume_status(session, approval)
    if latest_resume_status == "completed":
        return True
    if latest_resume_status not in RESUME_INCOMPLETE_STATUSES:
        return False
    if require_terminal_finalizer and not await _completed_resume_finalizer_reconciliation_ready(
        session=session,
        result=result,
    ):
        return False
    await _record_resume_event(
        session=session,
        result=result,
        actor_id=actor_id,
        resume_status="completed",
    )
    await session.commit()
    return True


async def _completed_resume_finalizer_reconciliation_ready(
    *, session: AsyncSession, result: ApprovalDecisionResult
) -> bool:
    run = await session.get(AgentRun, result.run_id)
    if run is None or run.final_status != "completed":
        return False
    if not run.final_response:
        return False
    finalizer_step = (
        await session.execute(
            select(AgentStep)
            .where(
                AgentStep.run_id == result.run_id,
                AgentStep.node_name == "agent_run_memory_finalize",
            )
            .order_by(AgentStep.completed_at.desc(), AgentStep.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    metrics = finalizer_step.metrics_json if finalizer_step is not None else None
    if not isinstance(metrics, dict) or metrics.get("memory_write_status") != "completed":
        raise RuntimeError("approval resume completed run missing terminal finalizer evidence")
    return True


async def _latest_resume_status(session: AsyncSession, approval: ApprovalRequest) -> str | None:
    resume_key = _resume_key(approval.id, int(approval.revision or 0))
    stmt = (
        select(ApprovalEvent)
        .where(
            ApprovalEvent.approval_request_id == approval.id,
            ApprovalEvent.event_type == "approval_resumed",
        )
        .order_by(ApprovalEvent.created_at.desc())
    )
    events = (await session.execute(stmt)).scalars().all()
    for event in events:
        if (event.resource_refs_json or {}).get("resume_key") != resume_key:
            continue
        status = (event.metadata_json or {}).get("resume_status")
        if status in {*RESUME_INCOMPLETE_STATUSES, "completed"}:
            return str(status)
    return None


async def _terminal_decision_result_for_retry(
    session: AsyncSession,
    approval: ApprovalRequest,
    body: DecideRequest,
) -> ApprovalDecisionResult:
    decision = (
        (
            await session.execute(
                select(ApprovalDecision)
                .where(
                    ApprovalDecision.approval_request_id == approval.id,
                    ApprovalDecision.deleted_at.is_(None),
                )
                .order_by(ApprovalDecision.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    level = (
        (
            await session.execute(
                select(ApprovalLevel)
                .where(
                    ApprovalLevel.approval_request_id == approval.id,
                    ApprovalLevel.deleted_at.is_(None),
                )
                .order_by(ApprovalLevel.level_number.desc())
            )
        )
        .scalars()
        .first()
    )
    assignment = None
    if level is not None:
        assignment = (
            (
                await session.execute(
                    select(ApprovalAssignment)
                    .where(
                        ApprovalAssignment.approval_level_id == level.id,
                        ApprovalAssignment.deleted_at.is_(None),
                    )
                    .order_by(ApprovalAssignment.created_at.desc())
                )
            )
            .scalars()
            .first()
        )
    event = None
    if decision is not None:
        event = (
            (
                await session.execute(
                    select(ApprovalEvent)
                    .where(
                        ApprovalEvent.approval_decision_id == decision.id,
                        ApprovalEvent.event_type == "approval_decided",
                    )
                    .order_by(ApprovalEvent.created_at.desc())
                )
            )
            .scalars()
            .first()
        )
    if decision is None or level is None or assignment is None or event is None:
        raise ApprovalTransitionError("approval_conflict")
    if (
        body.expected_request_version not in {decision.request_version, approval.version}
        or body.expected_level_version not in {decision.level_version, level.version}
        or body.expected_assignment_version not in {decision.assignment_version, assignment.version}
    ):
        raise ApprovalTransitionError("approval_conflict")

    metadata = event.metadata_json or {}
    resource_refs = event.resource_refs_json or {}
    edited_action = None
    new_action_payload_hash = None
    resume_route = None
    if decision.decision_type == "edit":
        edited_action = decision.edited_action_json
        new_action_payload_hash = resource_refs.get("new_action_payload_hash")
        resume_route = _historical_retry_resume_route_to_canonical(metadata.get("resume_route"))
        if (
            not edited_action
            or body.edited_action != edited_action
            or not new_action_payload_hash
            or resume_route != CANONICAL_RISK_ROUTE
        ):
            raise ApprovalTransitionError("approval_conflict")

    decided_at = approval.decided_at or decision.created_at
    binding_fields = _approval_binding_fields(approval)
    trusted = TrustedApprovalResultV1(
        approval_id=approval.id,
        tenant_id=approval.tenant_id,
        run_id=approval.run_id,
        status=approval.status,
        decision_type=decision.decision_type,
        revision=approval.revision,
        request_version=approval.version,
        level_version=level.version,
        assignment_version=assignment.version,
        action_payload_hash=approval.action_payload_hash,
        safety_snapshot_ref=approval.safety_snapshot_ref,
        safety_snapshot_hash=approval.safety_snapshot_hash,
        **binding_fields,
        decided_by=decision.actor_id,
        decided_at=decided_at,
        reason=approval.reason,
        edited_action=edited_action,
        new_action_payload_hash=new_action_payload_hash,
        resume_route=resume_route,
    ).model_dump(mode="json")
    return ApprovalDecisionResult(
        approval_id=approval.id,
        tenant_id=approval.tenant_id,
        run_id=approval.run_id,
        status=approval.status,
        decision_type=decision.decision_type,
        revision=approval.revision,
        request_version=approval.version,
        level_version=level.version,
        assignment_version=assignment.version,
        action_payload_hash=approval.action_payload_hash,
        safety_snapshot_ref=approval.safety_snapshot_ref,
        safety_snapshot_hash=approval.safety_snapshot_hash,
        **binding_fields,
        decided_by=decision.actor_id,
        decided_at=decided_at,
        decision_id=decision.id,
        event_id=event.id,
        reason=approval.reason,
        new_action_payload_hash=new_action_payload_hash,
        edited_action=edited_action,
        resume_payload=trusted,
        graph_thread_id=f"{approval.tenant_id}:{approval.requested_by}:{approval.thread_id}",
    )


async def _reconcile_approved_action_draft(
    *,
    session: AsyncSession,
    result: ApprovalDecisionResult,
    final_state: dict,
    config: dict,
) -> dict:
    if result.decision_type not in {"accept", "approve"} or result.status != "approved":
        return final_state
    existing = (
        await session.execute(
            select(ActionDraft.id).where(
                ActionDraft.run_id == result.run_id,
                ActionDraft.approval_request_id == result.approval_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return final_state

    approval = await session.get(ApprovalRequest, result.approval_id)
    if approval is None:
        return final_state

    state = {
        **final_state,
        "tenant_id": str(result.tenant_id),
        "user_id": str(approval.requested_by),
        "role": final_state.get("role") or "support",
        "thread_id": approval.thread_id,
        **_legacy_current_run_identity(config),
        "proposed_action": final_state.get("proposed_action") or approval.proposed_action,
        "approval_result": result.resume_payload,
        "claim_verification_bundle": final_state.get("claim_verification_bundle") or _approved_resume_claim_bundle(),
        "action_payload_hash": result.action_payload_hash,
        "safety_snapshot_ref": result.safety_snapshot_ref,
        "safety_snapshot_hash": result.safety_snapshot_hash,
        "safety_snapshot_verified": True,
        "risk_assessment": final_state.get("risk_assessment") or {"approval_required": True},
        "target_merchant_id": result.target_merchant_id,
        "target_merchant_ref": result.target_merchant_ref,
        "business_fact_refs": result.business_fact_refs,
        "verified_evidence_refs": result.verified_evidence_refs,
        "claim_verification_ref": result.claim_verification_ref,
        "claim_verification_summary": result.claim_verification_summary,
        "risk_decision_ref": result.risk_decision_ref,
        "risk_decision": result.risk_decision,
        "approval_idempotency_key": result.approval_idempotency_key,
    }
    update = await action_draft(state, config)
    reconciled = {**state, **update}
    if project_action_draft_terminal(reconciled, require_action=True).status != "completed":
        reconciled["node_errors"] = (final_state.get("node_errors") or []) + [
            {"node": "action_draft", "error": "action_draft_reconcile_failed"}
        ]
    return reconciled


def _approved_resume_claim_bundle() -> dict[str, object]:
    return {
        "schema_version": "claim_verification_bundle.v1",
        "overall_status": "verified",
        "route": "continue",
        "claim_results": [
            {
                "schema_version": "claim_verification_result.v1",
                "claim_id": "approval-service-approved-action",
                "claim_type": "action_recommendation",
                "support_status": "supported",
                "supporting_evidence_refs": [],
                "business_fact_refs": [],
                "rule_checks": [{"rule": "trusted_approval_resume", "passed": True}],
                "semantic_review_status": "not_needed",
                "allows_user_visible_claim": True,
                "allows_action_recommendation": True,
            }
        ],
        "blocked_claims": [],
        "safe_support_refs": [],
        "reason_codes": ["trusted_approval_resume"],
        "verifier_policy_version": "approval-service.v1",
    }


def _legacy_current_run_identity(config: dict) -> dict[str, str | None]:
    configurable = config.get("configurable") or {}
    trusted_context = TrustedContext.model_validate(configurable["trusted_context"])
    identity = project_to_legacy_agent_state_identity(trusted_context)
    return {"current_run_id": identity["current_run_id"]}


def _resume_graph_config(
    *, request: Request, session: AsyncSession, result: ApprovalDecisionResult, actor_user: User
) -> dict:
    permissions: list[str] = []
    if result.decision_type in {"accept", "approve"} and result.status == "approved":
        permissions.append(ACTION_DRAFT_PERMISSION)
    trusted_context = TrustedContextFactory.create_from_request(
        user=actor_user,
        verified_token_scopes=frozenset(),
        thread_id=result.graph_thread_id,
        run_id=str(result.run_id),
        trace_id=getattr(request.state, "trace_id", "") or "",
        server_tool_permissions=permissions,
    )
    return {
        "configurable": {
            "thread_id": result.graph_thread_id,
            "session": session,
            **_trusted_graph_config(trusted_context),
        }
    }


def _trusted_graph_config(trusted_context: TrustedContext) -> dict[str, object]:
    # Compatibility keys stay derived from canonical trusted_context for existing graph callers.
    return {
        "trusted_context": trusted_context.model_dump(mode="json"),
        "permissions": list(trusted_context.permissions),
        "merchant_scope": trusted_context.merchant_scope.model_dump(mode="json"),
        "trace_id": trusted_context.trace_id or "",
        "session_id": trusted_context.session_id,
    }


def _is_successful_demo_draft_outcome(draft_outcome: object) -> bool:
    return (
        isinstance(draft_outcome, dict)
        and draft_outcome.get("status") == "not_executed_demo"
        and draft_outcome.get("external_side_effect") is False
    )


def _should_resume_graph(result) -> bool:
    if not result.resume_payload:
        return False
    if result.decision_type == "edit":
        return result.resume_payload.get("resume_route") == CANONICAL_RISK_ROUTE
    return result.decision_type in {"accept", "approve", "reject", "ignore"}


def _historical_retry_resume_route_to_canonical(route: object) -> str | None:
    """Map persisted approval_decided retry metadata to current graph route authority."""
    if route == CANONICAL_RISK_ROUTE:
        return CANONICAL_RISK_ROUTE
    if isinstance(route, str):
        return HISTORICAL_RETRY_ROUTE_TO_CANONICAL.get(route)
    return None


def _resume_key(approval_id: UUID, revision: int) -> str:
    return f"{approval_id}:r{revision}"


def _assert_approval_reviewer(user: User) -> None:
    if user.role not in APPROVAL_ROLES:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Insufficient role for approval"},
        )


def _approval_scope_allowed(user: User, approval: ApprovalRequest) -> bool:
    if user.role == "admin":
        return True
    if user.role == "manager":
        return bool(
            approval.target_merchant_id
            and user.merchant_id
            and str(approval.target_merchant_id) == str(user.merchant_id)
        )
    return False


def _assert_approval_scope(user: User, approval: ApprovalRequest) -> None:
    if _approval_scope_allowed(user, approval):
        return
    raise _approval_not_found()


async def _get_scoped_approval_or_404(
    service: ApprovalService,
    user: User,
    approval_id: UUID,
) -> ApprovalRequest:
    approval = await service.get_request(approval_id, user.tenant_id)
    if approval is None or not _approval_scope_allowed(user, approval):
        raise _approval_not_found()
    return approval


def _approval_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})


def _approval_binding_fields(approval: ApprovalRequest) -> dict[str, object]:
    return {
        "target_merchant_id": approval.target_merchant_id,
        "target_merchant_ref": approval.target_merchant_ref,
        "business_fact_refs": list(approval.business_fact_refs or []),
        "verified_evidence_refs": list(approval.verified_evidence_refs or []),
        "claim_verification_ref": approval.claim_verification_ref,
        "claim_verification_summary": approval.claim_verification_summary,
        "risk_decision_ref": approval.risk_decision_ref,
        "risk_decision": approval.risk_decision,
        "approval_idempotency_key": approval.approval_idempotency_key,
    }


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


def _to_response(approval, *, result=None, decision_context=None) -> ApprovalResponse:
    return ApprovalResponse(
        decision_context=decision_context,
        id=str(approval.id),
        run_id=str(approval.run_id),
        thread_id=approval.thread_id,
        status=approval.status,
        revision=approval.revision,
        request_version=approval.version,
        action_payload_hash=approval.action_payload_hash,
        safety_snapshot_ref=approval.safety_snapshot_ref,
        safety_snapshot_hash=approval.safety_snapshot_hash,
        target_merchant_id=approval.target_merchant_id,
        business_fact_refs=list(approval.business_fact_refs or []),
        verified_evidence_refs=list(approval.verified_evidence_refs or []),
        claim_verification_ref=approval.claim_verification_ref,
        claim_verification_summary=approval.claim_verification_summary,
        risk_decision_ref=approval.risk_decision_ref,
        risk_decision=approval.risk_decision,
        clarification_request_id=approval.clarification_request_id,
        superseded_by_request_id=(
            str(getattr(result, "superseded_by_request_id", None) or approval.superseded_by_request_id)
            if getattr(result, "superseded_by_request_id", None) or approval.superseded_by_request_id
            else None
        ),
        new_action_payload_hash=getattr(result, "new_action_payload_hash", None) if result else None,
        resume_route=(result.resume_payload or {}).get("resume_route") if result and result.resume_payload else None,
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
