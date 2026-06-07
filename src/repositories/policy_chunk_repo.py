from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import PolicyChunk, PolicyDocument


class PolicyChunkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def delete_by_document_id(self, document_id: UUID, tenant_id: UUID) -> int:
        stmt = delete(PolicyChunk).where(
            PolicyChunk.doc_id == document_id,
            PolicyChunk.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def bulk_insert(self, chunks: list[PolicyChunk]) -> None:
        self.session.add_all(chunks)
        await self.session.flush()

    async def search_similar(
        self,
        query_embedding: list[float],
        tenant_id: UUID,
        top_k: int = 5,
        min_similarity: float = 0.55,
        doc_type: str | None = None,
        risk_level: str | None = None,
        effective_date: date | None = None,
    ) -> list[tuple[PolicyChunk, float]]:
        """
        Vector similarity search with metadata filters.
        Returns list of (chunk, similarity_score) tuples.
        """
        similarity_expr = 1 - PolicyChunk.embedding.cosine_distance(query_embedding)

        stmt = (
            select(PolicyChunk, similarity_expr.label("score"))
            .join(
                PolicyDocument,
                and_(
                    PolicyChunk.doc_id == PolicyDocument.id,
                    PolicyDocument.tenant_id == tenant_id,
                ),
            )
            .options(selectinload(PolicyChunk.document))
            .where(
                and_(
                    PolicyChunk.tenant_id == tenant_id,
                    similarity_expr >= min_similarity,
                )
            )
            .order_by(PolicyChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )

        if doc_type:
            stmt = stmt.where(PolicyDocument.doc_type == doc_type)
        if risk_level:
            stmt = stmt.where(PolicyChunk.risk_level == risk_level)
        if effective_date is not None:
            stmt = stmt.where(PolicyChunk.effective_date <= effective_date)

        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]
