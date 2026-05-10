from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from src.db.models import Order, RefundCase, Ticket
from src.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    model = Order

    async def get_by_order_no(self, order_no: str, tenant_id: UUID) -> Order | None:
        stmt = select(Order).where(Order.order_no == order_no, Order.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_hints(self, order_no: str, tenant_id: UUID) -> dict | None:
        order = await self.get_by_order_no(order_no, tenant_id)
        if not order:
            return None

        refund_stmt = (
            select(RefundCase)
            .where(
                RefundCase.order_id == order.id,
                RefundCase.tenant_id == tenant_id,
                RefundCase.status.not_in(["refunded", "rejected", "closed"]),
            )
            .order_by(RefundCase.created_at.desc())
            .limit(1)
        )
        active_refund = (await self.session.execute(refund_stmt)).scalar_one_or_none()

        ticket_stmt = (
            select(Ticket)
            .where(
                Ticket.order_id == order.id,
                Ticket.tenant_id == tenant_id,
                Ticket.status.in_(["open", "in_progress"]),
            )
            .order_by(Ticket.created_at.desc())
            .limit(1)
        )
        open_ticket = (await self.session.execute(ticket_stmt)).scalar_one_or_none()

        return {
            "order": order,
            "relation_hints": {
                "has_active_refund": active_refund is not None,
                "latest_refund_case_id": active_refund.id if active_refund else None,
                "has_open_ticket": open_ticket is not None,
                "latest_ticket_id": open_ticket.id if open_ticket else None,
            },
        }
