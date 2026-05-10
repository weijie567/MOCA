from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from src.db.models import Ticket
from src.repositories.base import BaseRepository


class TicketRepository(BaseRepository[Ticket]):
    model = Ticket

    async def get_by_ticket_no(self, ticket_no: str, tenant_id: UUID) -> Ticket | None:
        stmt = select(Ticket).where(Ticket.ticket_no == ticket_no, Ticket.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
