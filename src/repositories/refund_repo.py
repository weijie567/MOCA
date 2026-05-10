from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

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
