from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


T = TypeVar("T")


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> T | None:
        stmt = select(self.model).where(self.model.id == id, self.model.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, tenant_id: UUID, limit: int = 50, offset: int = 0, **filters) -> list[T]:
        stmt = select(self.model).where(self.model.tenant_id == tenant_id)
        for key, value in filters.items():
            if value is not None and hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        stmt = stmt.order_by(self.model.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
