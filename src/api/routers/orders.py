from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.common import ApiResponse, FORBIDDEN, ORDER_NOT_FOUND
from src.api.schemas.orders import OrderResponse, RelationHints
from src.auth.permissions import get_current_user
from src.db.models import User
from src.db.session import get_session
from src.repositories.audit_repo import AuditRepository
from src.repositories.order_repo import OrderRepository


router = APIRouter(tags=["orders"])


@router.get("/{order_no}", response_model=ApiResponse)
async def get_order(
    order_no: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["orders:read"]),
) -> ApiResponse:
    start = time.perf_counter()
    repository = OrderRepository(session)
    result = await repository.get_with_hints(order_no, user.tenant_id)
    order = result["order"] if result else None
    if order and user.role == "merchant" and user.merchant_id != order.merchant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": FORBIDDEN, "message": "Merchant access is limited to the merchant's own orders"},
        )
    if result is None:
        await AuditRepository(session).record_tool_call(
            action="get_order",
            resource_type="order",
            resource_id=None,
            trace_id=request.state.trace_id,
            run_id=request.state.run_id,
            latency_ms=round((time.perf_counter() - start) * 1000),
            status="not_found",
            error_code=ORDER_NOT_FOUND,
            tenant_id=user.tenant_id,
            user=user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        raise HTTPException(status_code=404, detail={"code": ORDER_NOT_FOUND, "message": "Order not found"})

    await AuditRepository(session).record_tool_call(
        action="get_order",
        resource_type="order",
        resource_id=order.id,
        trace_id=request.state.trace_id,
        run_id=request.state.run_id,
        latency_ms=round((time.perf_counter() - start) * 1000),
        status="success",
        tenant_id=user.tenant_id,
        user=user,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    payload = OrderResponse(
        id=order.id,
        tenant_id=order.tenant_id,
        merchant_id=order.merchant_id,
        order_no=order.order_no,
        buyer_name=order.buyer_name,
        item_name=order.item_name,
        amount=order.amount,
        currency=order.currency,
        status=order.status,
        created_at=order.created_at,
        delivered_at=order.delivered_at,
        relation_hints=RelationHints(**result["relation_hints"]),
    )
    return ApiResponse(success=True, data=payload.model_dump(mode="json"), trace_id=request.state.trace_id)
