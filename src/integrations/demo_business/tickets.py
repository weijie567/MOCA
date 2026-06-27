from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.demo_business.authz import merchant_can_access, order_merchant_id
from src.repositories.ticket_repo import TicketRepository


def _tool_success(data: dict[str, Any]) -> dict[str, Any]:
    return {"status": "success", "data": data, "error": {}}


def _tool_error(error_code: str, message: str, retryable: bool, should_stop: bool = False) -> dict[str, Any]:
    return {
        "status": "error",
        "data": {},
        "error": {
            "error_code": error_code,
            "message": message,
            "retryable": retryable,
            "should_stop": should_stop,
        },
    }


async def get_ticket(
    ticket_id: str,
    tenant_id: str,
    user_id: str,
    role: str,
    session: AsyncSession,
) -> dict[str, Any]:
    """Fetch a support ticket by id or ticket number. Read-only; excludes PII-heavy messages."""

    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        return _tool_error("VALIDATION_ERROR", "Invalid tenant_id", retryable=False)

    try:
        ticket_uuid = UUID(ticket_id)
    except ValueError:
        ticket_uuid = None

    try:
        repo = TicketRepository(session)
        if ticket_uuid is not None:
            ticket = await asyncio.wait_for(repo.get_by_id(ticket_uuid, tenant_uuid), timeout=10.0)
        else:
            ticket = await asyncio.wait_for(repo.get_by_ticket_no(ticket_id, tenant_uuid), timeout=10.0)
        if ticket is None:
            return _tool_error(
                "TICKET_NOT_FOUND",
                f"Ticket {ticket_id} not found for this tenant",
                retryable=False,
            )

        merchant_id = await order_merchant_id(session, tenant_id=tenant_uuid, order_id=ticket.order_id)
        if merchant_id is None or not await merchant_can_access(
            session,
            tenant_id=tenant_uuid,
            user_id=user_id,
            role=role,
            merchant_id=merchant_id,
        ):
            return _tool_error(
                "FORBIDDEN",
                "Merchant access is limited to the merchant's own tickets",
                retryable=False,
                should_stop=True,
            )

        return _tool_success(
            {
                "ticket_no": ticket.ticket_no,
                "status": ticket.status,
                "channel": ticket.channel,
                "summary": ticket.summary,
            }
        )
    except asyncio.TimeoutError:
        return _tool_error("DB_TIMEOUT", "Database timeout fetching ticket", retryable=True)
    except Exception:
        return _tool_error("DB_ERROR", "Failed to fetch ticket", retryable=False)
