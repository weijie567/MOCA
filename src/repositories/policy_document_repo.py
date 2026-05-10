from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PolicyDocument


class PolicyDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_doc_key(self, doc_key: str, tenant_id: UUID) -> PolicyDocument | None:
        stmt = select(PolicyDocument).where(
            PolicyDocument.tenant_id == tenant_id,
            PolicyDocument.doc_key == doc_key,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, doc: PolicyDocument) -> PolicyDocument:
        """Merge (insert or update) a policy document."""
        merged = await self.session.merge(doc)
        await self.session.flush()
        return merged
