from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.ticket_repo import TicketRepository


def _tool_success(data: dict) -> dict:
    return {"status": "success", "data": data, "error": {}}


def _tool_error(error_code: str, message: str, retryable: bool, should_stop: bool = False) -> dict:
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
) -> dict:
    """Fetch a support ticket by id. Read-only; excludes conversation history containing PII."""
    del user_id, role

    try:
        ticket_uuid = UUID(ticket_id)
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        return _tool_error("VALIDATION_ERROR", "Invalid ticket_id or tenant_id", retryable=False)

    try:
        repo = TicketRepository(session)
        ticket = await asyncio.wait_for(repo.get_by_id(ticket_uuid, tenant_uuid), timeout=10.0)
        if ticket is None:
            return _tool_error(
                "TICKET_NOT_FOUND",
                f"Ticket {ticket_id} not found for this tenant",
                retryable=False,
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
