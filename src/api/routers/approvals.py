from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.action_draft import action_draft
from src.agent.trace import append_agent_steps, update_agent_run_status
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
RESUMABLE_DECISIONS = {"accept", "approve", "reject", "ignore"}
RESUME_TERMINAL_STATUSES = {"approved", "rejected", "cancelled"}
RESUME_INCOMPLETE_STATUSES = {"attempted", "failed"}
ACTION_DRAFT_PERMISSION = "tool:create_coupon_grant_draft"


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
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})
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
            data=_to_response(approval, result=retry_result).model_dump(mode="json"),
            trace_id=getattr(request.state, "trace_id", None),
        )

    try:
        context = await service.get_decision_context(approval_uuid, user.tenant_id)
    except ApprovalTransitionError as exc:
        raise _approval_http_error(exc) from exc
    if context is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})

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
        data=_to_response(approval, result=result).model_dump(mode="json"),
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
    approval = await service.get_request(approval_uuid, user.tenant_id)
    if approval is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})
    _assert_approval_scope(user, approval)
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
        data=_to_response(approval, result=result).model_dump(mode="json"),
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
    approval = await ApprovalService(session).get_request(_parse_approval_id(approval_id), user.tenant_id)
    if not approval:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})
    _assert_approval_scope(user, approval)
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
    _assert_approval_reviewer(user)
    approvals = await ApprovalService(session).list_pending_requests(user.tenant_id)
    approvals = [approval for approval in approvals if _approval_scope_allowed(user, approval)]
    payload = ApprovalListResponse(approvals=[_to_response(approval) for approval in approvals], total=len(approvals))
    return ApiResponse(
        success=True, data=payload.model_dump(mode="json"), trace_id=getattr(request.state, "trace_id", None)
    )


async def _run_resume_lifecycle(
    *, request: Request, session: AsyncSession, result: ApprovalDecisionResult, actor_id: UUID, actor_user: User
) -> None:
    try:
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
        await _record_resume_event(
            session=session,
            result=result,
            actor_id=actor_id,
            resume_status="completed",
        )
        await session.commit()
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
    final_state = await graph.ainvoke(Command(resume=result.resume_payload), config)
    resume_latency_ms = round((time.perf_counter() - t0) * 1000)
    final_state = await _reconcile_approved_action_draft(
        session=session,
        result=result,
        final_state=final_state,
        config=config,
    )

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
        trace_id=getattr(request.state, "trace_id", None),
        reason_code="approval_resume_completed" if final_status == "completed" else "approval_resume_error",
        error_code="approval_resume_error" if final_status == "error" else None,
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
    if approval is None or approval.status not in RESUME_TERMINAL_STATUSES:
        return None
    if body.decision_type not in RESUMABLE_DECISIONS:
        return None

    latest_resume_status = await _latest_resume_status(session, approval)
    if latest_resume_status not in RESUME_INCOMPLETE_STATUSES:
        return None

    run = await session.get(AgentRun, approval.run_id)
    if run is not None and run.final_status not in {"interrupted", "running", "pending"}:
        return None

    if (
        approval.decision != body.decision_type
        or approval.revision != body.expected_revision
        or approval.action_payload_hash != body.action_payload_hash
        or approval.safety_snapshot_hash != body.safety_snapshot_hash
    ):
        raise ApprovalTransitionError("approval_conflict")

    return await _terminal_decision_result_for_retry(session, approval, body)


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
    reconciled = {**final_state, **update}
    if not _is_successful_demo_draft_outcome(update.get("draft_outcome")):
        reconciled["node_errors"] = (final_state.get("node_errors") or []) + [
            {"node": "action_draft", "error": "action_draft_reconcile_failed"}
        ]
    return reconciled


def _approved_resume_claim_bundle() -> dict[str, object]:
    return {
        "schema_version": "claim_verification_bundle.v1",
        "overall_status": "not_required",
        "route": "continue",
        "claim_results": [],
        "blocked_claims": [],
        "safe_support_refs": [],
        "reason_codes": [],
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
        return result.resume_payload.get("resume_route") == "assess_risk_and_approval"
    return result.decision_type in {"accept", "approve", "reject", "ignore"}


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
    raise HTTPException(
        status_code=403,
        detail={"code": "FORBIDDEN", "message": "Approval target merchant is outside actor scope"},
    )


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


def _to_response(approval, *, result=None) -> ApprovalResponse:
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
