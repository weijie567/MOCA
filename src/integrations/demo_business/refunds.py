from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.demo_business.authz import merchant_can_access, order_merchant_id
from src.repositories.refund_repo import RefundRepository


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


async def get_refund_case(
    refund_case_no: str,
    tenant_id: str,
    user_id: str,
    role: str,
    session: AsyncSession,
) -> dict[str, Any]:
    """Fetch a refund case by case number. Read-only; tenant and merchant scoping are enforced."""

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

        merchant_id = await order_merchant_id(session, tenant_id=tenant_uuid, order_id=refund_case.order_id)
        if merchant_id is None or not await merchant_can_access(
            session,
            tenant_id=tenant_uuid,
            user_id=user_id,
            role=role,
            merchant_id=merchant_id,
        ):
            return _tool_error(
                "FORBIDDEN",
                "Merchant access is limited to the merchant's own refund cases",
                retryable=False,
                should_stop=True,
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
