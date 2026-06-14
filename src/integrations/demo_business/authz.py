from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Order, User


async def merchant_can_access(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: str,
    role: str,
    merchant_id: UUID,
) -> bool:
    """Return whether the caller may read data owned by merchant_id."""

    if role != "merchant":
        return True

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return False

    stmt = select(User.merchant_id).where(
        User.id == user_uuid,
        User.tenant_id == tenant_id,
        User.role == "merchant",
        User.is_active.is_(True),
    )
    result = await session.execute(stmt)
    caller_merchant_id = result.scalar_one_or_none()
    return caller_merchant_id is not None and caller_merchant_id == merchant_id


async def order_merchant_id(session: AsyncSession, *, tenant_id: UUID, order_id: UUID) -> UUID | None:
    stmt = select(Order.merchant_id).where(Order.id == order_id, Order.tenant_id == tenant_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
