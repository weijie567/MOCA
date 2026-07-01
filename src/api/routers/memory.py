from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.common import ApiResponse
from src.api.schemas.memory import MemoryPendingItem, MemoryPendingListResponse, MemoryReviewActionRequest
from src.auth.permissions import get_current_user
from src.db.models import AgentRun, CaseMemory, LongTermMemory, User
from src.db.session import get_session
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.long_term import LongTermMemoryService
from src.memory.repository import LongTermMemoryRepository
from src.memory.schemas import CaseMemoryReviewDecision


router = APIRouter(tags=["memory"])

MEMORY_REVIEW_ROLES = {"admin", "manager"}


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
