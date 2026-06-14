from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.demo_business.authz import merchant_can_access
from src.repositories.order_repo import OrderRepository


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


async def get_order(
    order_no: str,
    tenant_id: str,
    user_id: str,
    role: str,
    session: AsyncSession,
) -> dict[str, Any]:
    """Fetch order with relation hints. Read-only; tenant and merchant scoping are enforced."""

    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        return _tool_error("VALIDATION_ERROR", "Invalid tenant_id", retryable=False)

    try:
        repo = OrderRepository(session)
        result = await asyncio.wait_for(repo.get_with_hints(order_no, tenant_uuid), timeout=10.0)
        if result is None:
            return _tool_error(
                "ORDER_NOT_FOUND",
                f"Order {order_no} not found for this tenant",
                retryable=False,
            )

        order = result["order"]
        if not await merchant_can_access(
            session,
            tenant_id=tenant_uuid,
            user_id=user_id,
            role=role,
            merchant_id=order.merchant_id,
        ):
            return _tool_error(
                "FORBIDDEN",
                "Merchant access is limited to the merchant's own orders",
                retryable=False,
                should_stop=True,
            )

        hints = result["relation_hints"]
        return _tool_success(
            {
                "order_no": order.order_no,
                "status": order.status,
                "amount": str(order.amount),
                "currency": order.currency,
                "buyer_name": order.buyer_name,
                "item_name": order.item_name,
                "paid_at": order.paid_at.isoformat() if order.paid_at else None,
                "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
                "relation_hints": {
                    "has_active_refund": hints["has_active_refund"],
                    "latest_refund_case_id": str(hints["latest_refund_case_id"])
                    if hints["latest_refund_case_id"]
                    else None,
                    "has_open_ticket": hints["has_open_ticket"],
                    "latest_ticket_id": str(hints["latest_ticket_id"]) if hints["latest_ticket_id"] else None,
                },
            }
        )
    except asyncio.TimeoutError:
        return _tool_error("DB_TIMEOUT", "Database timeout fetching order", retryable=True)
    except Exception:
        return _tool_error("DB_ERROR", "Failed to fetch order", retryable=False)
