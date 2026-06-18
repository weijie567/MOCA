from __future__ import annotations

from collections import Counter
from datetime import date
from uuid import UUID

from sqlalchemy import and_, delete, func, select, tuple_
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

    async def get_contents_by_evidence_keys(
        self,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], str]:
        if not keys:
            return {}

        stmt = (
            select(PolicyDocument.doc_key, PolicyChunk.chunk_id, PolicyChunk.content)
            .join(
                PolicyDocument,
                and_(
                    PolicyChunk.doc_id == PolicyDocument.id,
                    PolicyDocument.tenant_id == tenant_id,
                ),
            )
            .where(
                PolicyChunk.tenant_id == tenant_id,
                tuple_(PolicyDocument.doc_key, PolicyChunk.chunk_id).in_(keys),
            )
        )
        rows = (await self.session.execute(stmt)).all()
        counts = Counter((row[0], row[1]) for row in rows)
        return {
            (doc_key, chunk_id): content
            for doc_key, chunk_id, content in rows
            if counts[(doc_key, chunk_id)] == 1
        }

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

    async def search_sparse(
        self,
        query_text: str,
        tenant_id: UUID,
        top_k: int = 50,
        doc_type: str | None = None,
        risk_level: str | None = None,
        effective_date: date | None = None,
    ) -> list[tuple[PolicyChunk, float]]:
        """PostgreSQL full-text search over retrieval-ready chunk text."""
        query_expr = func.plainto_tsquery("simple", query_text)
        rank_expr = func.ts_rank_cd(PolicyChunk.search_vector, query_expr)

        stmt = (
            select(PolicyChunk, rank_expr.label("score"))
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
                    PolicyChunk.search_vector.op("@@")(query_expr),
                    rank_expr > 0,
                )
            )
            .order_by(rank_expr.desc())
            .limit(top_k)
        )

        stmt = _apply_policy_filters(
            stmt,
            doc_type=doc_type,
            risk_level=risk_level,
            effective_date=effective_date,
        )

        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def search_fuzzy(
        self,
        query_text: str,
        tenant_id: UUID,
        top_k: int = 20,
        min_similarity: float = 0.10,
        doc_type: str | None = None,
        risk_level: str | None = None,
        effective_date: date | None = None,
    ) -> list[tuple[PolicyChunk, float]]:
        """pg_trgm fuzzy search over retrieval-ready chunk text."""
        similarity_expr = func.similarity(PolicyChunk.search_text, query_text)

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
            .order_by(similarity_expr.desc())
            .limit(top_k)
        )

        stmt = _apply_policy_filters(
            stmt,
            doc_type=doc_type,
            risk_level=risk_level,
            effective_date=effective_date,
        )

        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]


def _apply_policy_filters(
    stmt,
    *,
    doc_type: str | None,
    risk_level: str | None,
    effective_date: date | None,
):
    if doc_type:
        stmt = stmt.where(PolicyDocument.doc_type == doc_type)
    if risk_level:
        stmt = stmt.where(PolicyChunk.risk_level == risk_level)
    if effective_date is not None:
        stmt = stmt.where(PolicyChunk.effective_date <= effective_date)
    return stmt
