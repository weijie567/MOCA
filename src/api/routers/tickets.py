from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.common import ApiResponse, TICKET_NOT_FOUND
from src.api.schemas.tickets import TicketHistoryResponse
from src.auth.permissions import get_current_user, require_merchant_access
from src.db.models import Order, User
from src.db.session import get_session
from src.repositories.audit_repo import AuditRepository
from src.repositories.ticket_repo import TicketRepository


router = APIRouter(tags=["tickets"])


@router.get("/{ticket_no}", response_model=ApiResponse)
async def get_ticket_history(
    ticket_no: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["tickets:read"]),
) -> ApiResponse:
    start = time.perf_counter()
    repository = TicketRepository(session)
    ticket = await repository.get_by_ticket_no(ticket_no, user.tenant_id)
    if ticket is None:
        await AuditRepository(session).record_tool_call(
            action="get_ticket_history",
            resource_type="ticket",
            resource_id=None,
            trace_id=request.state.trace_id,
            run_id=request.state.run_id,
            latency_ms=round((time.perf_counter() - start) * 1000),
            status="not_found",
            error_code=TICKET_NOT_FOUND,
            tenant_id=user.tenant_id,
            user=user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        raise HTTPException(status_code=404, detail={"code": TICKET_NOT_FOUND, "message": "Ticket not found"})
    merchant_id = (
        await session.execute(
            select(Order.merchant_id).where(Order.id == ticket.order_id, Order.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    if merchant_id is None:
        raise HTTPException(status_code=404, detail={"code": TICKET_NOT_FOUND, "message": "Ticket not found"})
    require_merchant_access(user, merchant_id, resource_name="tickets")

    await AuditRepository(session).record_tool_call(
        action="get_ticket_history",
        resource_type="ticket",
        resource_id=ticket.id,
        trace_id=request.state.trace_id,
        run_id=request.state.run_id,
        latency_ms=round((time.perf_counter() - start) * 1000),
        status="success",
        tenant_id=user.tenant_id,
        user=user,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    payload = TicketHistoryResponse(
        id=ticket.id,
        tenant_id=ticket.tenant_id,
        order_id=ticket.order_id,
        refund_case_id=ticket.refund_case_id,
        ticket_no=ticket.ticket_no,
        channel=ticket.channel,
        status=ticket.status,
        summary=ticket.summary,
        created_at=ticket.created_at,
        messages=ticket.messages,
    )
    return ApiResponse(success=True, data=payload.model_dump(mode="json"), trace_id=request.state.trace_id)
