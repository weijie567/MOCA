from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.refund_repo import RefundRepository


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


async def get_refund_case(
    refund_case_no: str,
    tenant_id: str,
    user_id: str,
    role: str,
    session: AsyncSession,
) -> dict:
    """Fetch a refund case by case number. Read-only; tenant scoping is enforced by the repository."""
    del user_id, role

    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        return _tool_error("VALIDATION_ERROR", "Invalid tenant_id", retryable=False)

    try:
        repo = RefundRepository(session)
        refund_case = await asyncio.wait_for(
            repo.get_by_case_no(refund_case_no, tenant_uuid),
            timeout=10.0,
        )
        if refund_case is None:
            return _tool_error(
                "REFUND_CASE_NOT_FOUND",
                f"Refund case {refund_case_no} not found for this tenant",
                retryable=False,
            )

        return _tool_success(
            {
                "refund_case_no": refund_case.refund_case_no,
                "status": refund_case.status,
                "reason_code": refund_case.reason_code,
                "reason_text": refund_case.reason_text,
                "requested_amount": str(refund_case.requested_amount),
                "approved_amount": str(refund_case.approved_amount) if refund_case.approved_amount else None,
            }
        )
    except asyncio.TimeoutError:
        return _tool_error("DB_TIMEOUT", "Database timeout fetching refund case", retryable=True)
    except Exception:
        return _tool_error("DB_ERROR", "Failed to fetch refund case", retryable=False)
