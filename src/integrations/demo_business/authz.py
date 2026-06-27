from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Order, User


MERCHANT_BOUND_ROLES = {"support", "manager", "merchant"}
PLATFORM_ADMIN_ROLES = {"admin"}


async def merchant_can_access(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: str,
    role: str,
    merchant_id: UUID,
) -> bool:
    """Return whether the caller may read data owned by merchant_id."""

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return False

    stmt = select(User).where(
        User.id == user_uuid,
        User.tenant_id == tenant_id,
        User.is_active.is_(True),
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None or user.role != role:
        return False
    if user.role in PLATFORM_ADMIN_ROLES:
        return True
    if user.role not in MERCHANT_BOUND_ROLES:
        return False
    return user.merchant_id is not None and user.merchant_id == merchant_id


async def order_merchant_id(session: AsyncSession, *, tenant_id: UUID, order_id: UUID) -> UUID | None:
    stmt = select(Order.merchant_id).where(Order.id == order_id, Order.tenant_id == tenant_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
