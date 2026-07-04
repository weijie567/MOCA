from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.common import ApiResponse
from src.api.schemas.memory import (
    LongTermPreferenceSaveRequest,
    LongTermPreferenceSaveResponse,
    MemoryPendingItem,
    MemoryPendingListResponse,
    MemoryReviewActionRequest,
)
from src.auth.permissions import get_current_user
from src.db.models import AgentRun, CaseMemory, LongTermMemory, Merchant, User
from src.db.session import get_session
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.long_term import LongTermMemoryService
from src.memory.preference_capture import classify_preference_pii, validate_soft_preference_text
from src.memory.repository import LongTermMemoryRepository
from src.memory.schemas import CaseMemoryReviewDecision, LongTermMemoryWriteCandidate, MemorySourceRefV1


router = APIRouter(tags=["memory"])

MEMORY_REVIEW_ROLES = {"admin"}


@router.get("/review/pending", response_model=ApiResponse)
async def list_pending_memory(
    request: Request,
    memory_type: Literal["all", "long_term", "case"] = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    _assert_memory_reviewer(user)
    items: list[MemoryPendingItem] = []

    if memory_type in {"all", "long_term"}:
        memories = await LongTermMemoryService(LongTermMemoryRepository(session)).list_pending_review(
            tenant_id=user.tenant_id,
            limit=limit,
        )
        items.extend(_long_term_pending_item(memory) for memory in memories)

    if memory_type in {"all", "case"}:
        memories = await CaseMemoryService(CaseMemoryRepository(session)).list_pending_review(
            tenant_id=user.tenant_id,
            limit=limit,
        )
        items.extend(_case_pending_item(memory) for memory in memories)

    items.sort(key=lambda item: item.created_at.timestamp() if item.created_at else 0.0, reverse=True)
    payload = MemoryPendingListResponse(items=items[:limit], total=len(items))
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.post("/long-term/preferences", response_model=ApiResponse)
async def save_long_term_preference(
    body: LongTermPreferenceSaveRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["memory:write"]),
) -> ApiResponse:
    _assert_memory_admin(user)
    await _ensure_run_in_tenant(session=session, tenant_id=user.tenant_id, run_id=body.run_id)
    await _validate_preference_scope(session=session, tenant_id=user.tenant_id, body=body)
    validation = validate_soft_preference_text(body.content)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_PREFERENCE",
                "message": "Long-term preference content must be a soft preference, not a hard rule",
                "details": {"reason_code": validation.reason_code},
            },
        )

    candidate = LongTermMemoryWriteCandidate(
        tenant_id=user.tenant_id,
        run_id=body.run_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        memory_kind="preference",
        content=body.content,
        source_type="explicit_admin_preference",
        source_ref=MemorySourceRefV1(
            source_type="explicit_admin_preference",
            run_id=str(body.run_id),
            agent_run_id=str(body.run_id),
            business_object_type=body.scope_type,
            business_object_id=body.scope_id,
        ),
        confidence=1.0,
        pii_classification=classify_preference_pii(body.content),
    )
    try:
        result = await LongTermMemoryService(LongTermMemoryRepository(session)).write_memory(candidate)
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise _memory_action_error(exc) from exc

    payload = LongTermPreferenceSaveResponse(
        memory_type="long_term",
        memory_id=str(result.memory_id) if result.memory_id is not None else None,
        event_id=str(result.event_id) if result.event_id is not None else None,
        decision=result.decision,
        reason_code=result.reason_code,
        review_status=result.review_status,
        source_type="explicit_admin_preference",
    )
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.post("/long-term/{memory_id}/approve", response_model=ApiResponse)
async def approve_long_term_memory(
    memory_id: str,
    body: MemoryReviewActionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    return await _run_long_term_action(
        memory_id=memory_id,
        body=body,
        request=request,
        session=session,
        user=user,
        action="approve",
    )


@router.post("/long-term/{memory_id}/reject", response_model=ApiResponse)
async def reject_long_term_memory(
    memory_id: str,
    body: MemoryReviewActionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    return await _run_long_term_action(
        memory_id=memory_id,
        body=body,
        request=request,
        session=session,
        user=user,
        action="reject",
    )


@router.post("/long-term/{memory_id}/delete", response_model=ApiResponse)
async def delete_long_term_memory(
    memory_id: str,
    body: MemoryReviewActionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    return await _run_long_term_action(
        memory_id=memory_id,
        body=body,
        request=request,
        session=session,
        user=user,
        action="delete",
    )


@router.post("/long-term/{memory_id}/forget", response_model=ApiResponse)
async def forget_long_term_memory(
    memory_id: str,
    body: MemoryReviewActionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    return await _run_long_term_action(
        memory_id=memory_id,
        body=body,
        request=request,
        session=session,
        user=user,
        action="forget",
    )


@router.post("/case/{memory_id}/approve", response_model=ApiResponse)
async def approve_case_memory(
    memory_id: str,
    body: MemoryReviewActionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    return await _run_case_action(
        memory_id=memory_id,
        body=body,
        request=request,
        session=session,
        user=user,
        action="approve",
    )


@router.post("/case/{memory_id}/reject", response_model=ApiResponse)
async def reject_case_memory(
    memory_id: str,
    body: MemoryReviewActionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    return await _run_case_action(
        memory_id=memory_id,
        body=body,
        request=request,
        session=session,
        user=user,
        action="reject",
    )


@router.post("/case/{memory_id}/delete", response_model=ApiResponse)
async def delete_case_memory(
    memory_id: str,
    body: MemoryReviewActionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    return await _run_case_action(
        memory_id=memory_id,
        body=body,
        request=request,
        session=session,
        user=user,
        action="delete",
    )


@router.post("/case/{memory_id}/forget", response_model=ApiResponse)
async def forget_case_memory(
    memory_id: str,
    body: MemoryReviewActionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    return await _run_case_action(
        memory_id=memory_id,
        body=body,
        request=request,
        session=session,
        user=user,
        action="forget",
    )


async def _run_long_term_action(
    *,
    memory_id: str,
    body: MemoryReviewActionRequest,
    request: Request,
    session: AsyncSession,
    user: User,
    action: Literal["approve", "reject", "delete", "forget"],
) -> ApiResponse:
    _assert_memory_reviewer(user)
    memory_uuid = _parse_memory_id(memory_id)
    await _ensure_run_in_tenant(session=session, tenant_id=user.tenant_id, run_id=body.run_id)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    reason_code = _reason_code(body, action)
    try:
        if action == "approve":
            event = await service.approve_memory(
                tenant_id=user.tenant_id,
                memory_id=memory_uuid,
                run_id=body.run_id,
                reason_code=reason_code,
            )
        elif action == "reject":
            event = await service.reject_memory(
                tenant_id=user.tenant_id,
                memory_id=memory_uuid,
                run_id=body.run_id,
                reason_code=reason_code,
            )
        elif action == "delete":
            event = await service.delete_memory(
                tenant_id=user.tenant_id,
                memory_id=memory_uuid,
                run_id=body.run_id,
                reason_code=reason_code,
            )
        else:
            event = await service.forget_memory(
                tenant_id=user.tenant_id,
                memory_id=memory_uuid,
                run_id=body.run_id,
                reason_code=reason_code,
            )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise _memory_action_error(exc) from exc

    return _event_response(request=request, memory_type="long_term", memory_id=memory_uuid, event=event)


async def _run_case_action(
    *,
    memory_id: str,
    body: MemoryReviewActionRequest,
    request: Request,
    session: AsyncSession,
    user: User,
    action: Literal["approve", "reject", "delete", "forget"],
) -> ApiResponse:
    _assert_memory_reviewer(user)
    memory_uuid = _parse_memory_id(memory_id)
    await _ensure_run_in_tenant(session=session, tenant_id=user.tenant_id, run_id=body.run_id)
    service = CaseMemoryService(CaseMemoryRepository(session))
    reason_code = _reason_code(body, action)
    try:
        if action == "approve":
            event = await service.approve_case_memory(
                CaseMemoryReviewDecision(
                    tenant_id=user.tenant_id,
                    run_id=body.run_id,
                    case_memory_id=memory_uuid,
                    reviewer_user_id=user.id,
                    reason_code=reason_code,
                    review_reason=body.review_reason,
                )
            )
        elif action == "reject":
            event = await service.reject_case_memory(
                CaseMemoryReviewDecision(
                    tenant_id=user.tenant_id,
                    run_id=body.run_id,
                    case_memory_id=memory_uuid,
                    reviewer_user_id=user.id,
                    reason_code=reason_code,
                    review_reason=body.review_reason,
                )
            )
        elif action == "delete":
            event = await service.delete_case_memory(
                tenant_id=user.tenant_id,
                case_memory_id=memory_uuid,
                run_id=body.run_id,
                reason_code=reason_code,
            )
        else:
            event = await service.forget_case_memory(
                tenant_id=user.tenant_id,
                case_memory_id=memory_uuid,
                run_id=body.run_id,
                reason_code=reason_code,
            )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise _memory_action_error(exc) from exc

    return _event_response(request=request, memory_type="case", memory_id=memory_uuid, event=event)


async def _ensure_run_in_tenant(*, session: AsyncSession, tenant_id: UUID, run_id: UUID) -> None:
    exists = (
        await session.execute(select(AgentRun.id).where(AgentRun.id == run_id, AgentRun.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Agent run not found"})


def _long_term_pending_item(memory: LongTermMemory) -> MemoryPendingItem:
    return MemoryPendingItem(
        memory_type="long_term",
        memory_id=str(memory.id),
        scope_type=memory.scope_type,
        scope_id=memory.scope_id,
        review_status=memory.review_status,
        pii_classification=memory.pii_classification,
        source_type=memory.source_type,
        content=memory.content,
        created_by_run_id=str(memory.created_by_run_id) if memory.created_by_run_id is not None else None,
        created_at=memory.created_at,
    )


def _case_pending_item(memory: CaseMemory) -> MemoryPendingItem:
    source_type = str((memory.source_ref_json or {}).get("source_type") or "")
    return MemoryPendingItem(
        memory_type="case",
        memory_id=str(memory.id),
        scope_type=memory.scope_type,
        scope_id=memory.scope_id,
        review_status=memory.review_status,
        pii_classification=memory.pii_classification,
        source_type=source_type,
        summary=memory.summary,
        excerpt=memory.excerpt,
        created_by_run_id=str(memory.created_by_run_id) if memory.created_by_run_id is not None else None,
        created_at=memory.created_at,
    )


def _event_response(*, request: Request, memory_type: str, memory_id: UUID, event) -> ApiResponse:
    return ApiResponse(
        success=True,
        data={
            "memory_type": memory_type,
            "memory_id": str(memory_id),
            "event_id": str(event.id),
            "decision": event.decision,
            "reason_code": event.reason_code,
        },
        trace_id=getattr(request.state, "trace_id", None),
    )


def _reason_code(body: MemoryReviewActionRequest, action: str) -> str:
    if body.reason_code:
        return body.reason_code
    return {
        "approve": "approved",
        "reject": "rejected",
        "delete": "deleted",
        "forget": "forgotten",
    }[action]


def _assert_memory_reviewer(user: User) -> None:
    if user.role not in MEMORY_REVIEW_ROLES:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Insufficient role for memory review"},
        )


def _assert_memory_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Insufficient role for admin memory write"},
        )


async def _validate_preference_scope(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    body: LongTermPreferenceSaveRequest,
) -> None:
    if body.scope_type == "tenant":
        if body.scope_id != str(tenant_id):
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "message": "Tenant preference scope must match actor tenant"},
            )
        return

    try:
        merchant_id = UUID(body.scope_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Merchant not found"}) from exc
    exists = (
        await session.execute(select(Merchant.id).where(Merchant.id == merchant_id, Merchant.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Merchant not found"})


def _parse_memory_id(memory_id: str) -> UUID:
    try:
        return UUID(memory_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Memory not found"}) from exc


def _memory_action_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if "not found" in message:
        return HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Memory not found"})
    return HTTPException(status_code=409, detail={"code": "CONFLICT", "message": message})
