from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db.models import RefundCase
from src.repositories.base import BaseRepository


class RefundRepository(BaseRepository[RefundCase]):
    model = RefundCase

    async def get_by_case_no(self, refund_case_no: str, tenant_id: UUID) -> RefundCase | None:
        stmt = select(RefundCase).where(
            RefundCase.refund_case_no == refund_case_no,
            RefundCase.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_order(self, case_id: UUID, tenant_id: UUID) -> RefundCase | None:
        stmt = (
            select(RefundCase)
            .options(selectinload(RefundCase.order))
            .where(
                RefundCase.id == case_id,
                RefundCase.tenant_id == tenant_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
