from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.common import ApiResponse, FORBIDDEN, REFUND_CASE_NOT_FOUND
from src.api.schemas.refund_cases import RefundCaseResponse
from src.auth.permissions import get_current_user
from src.db.models import Order, User
from src.db.session import get_session
from src.repositories.audit_repo import AuditRepository
from src.repositories.refund_repo import RefundRepository


router = APIRouter(tags=["refund_cases"])


@router.get("/{refund_case_no}", response_model=ApiResponse)
async def get_refund_case(
    refund_case_no: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["refunds:read"]),
) -> ApiResponse:
    start = time.perf_counter()
    repository = RefundRepository(session)
    refund_case = await repository.get_by_case_no(refund_case_no, user.tenant_id)
    if refund_case is None:
        await AuditRepository(session).record_tool_call(
            action="get_refund_case",
            resource_type="refund_case",
            resource_id=None,
            trace_id=request.state.trace_id,
            run_id=request.state.run_id,
            latency_ms=round((time.perf_counter() - start) * 1000),
            status="not_found",
            error_code=REFUND_CASE_NOT_FOUND,
            tenant_id=user.tenant_id,
            user=user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        raise HTTPException(status_code=404, detail={"code": REFUND_CASE_NOT_FOUND, "message": "Refund case not found"})
    merchant_id = (
        await session.execute(select(Order.merchant_id).where(Order.id == refund_case.order_id))
    ).scalar_one()
    if user.role == "merchant" and user.merchant_id is not None and merchant_id != user.merchant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": FORBIDDEN, "message": "Merchant access is limited to the merchant's own refund cases"},
        )

    await AuditRepository(session).record_tool_call(
        action="get_refund_case",
        resource_type="refund_case",
        resource_id=refund_case.id,
        trace_id=request.state.trace_id,
        run_id=request.state.run_id,
        latency_ms=round((time.perf_counter() - start) * 1000),
        status="success",
        tenant_id=user.tenant_id,
        user=user,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    payload = RefundCaseResponse(
        id=refund_case.id,
        tenant_id=refund_case.tenant_id,
        order_id=refund_case.order_id,
        refund_case_no=refund_case.refund_case_no,
        reason_code=refund_case.reason_code,
        reason_text=refund_case.reason_text,
        status=refund_case.status,
        requested_amount=refund_case.requested_amount,
        approved_amount=refund_case.approved_amount,
        created_at=refund_case.created_at,
    )
    return ApiResponse(success=True, data=payload.model_dump(mode="json"), trace_id=request.state.trace_id)
