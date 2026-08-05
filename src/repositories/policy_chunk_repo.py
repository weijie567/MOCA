from __future__ import annotations

from collections import Counter
from datetime import date
from uuid import UUID

from sqlalchemy import and_, delete, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import PolicyChunk, PolicyDocument
from src.knowledge.provenance import EvidenceProvenance, source_locator_from_block
from src.repositories.document_block_repo import DocumentBlockRepository


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

    async def list_by_document_id_for_update(
        self,
        document_id: UUID,
        tenant_id: UUID,
    ) -> list[PolicyChunk]:
        """Lock current chunk heads after the rollout/document locks."""

        stmt = (
            select(PolicyChunk)
            .where(
                PolicyChunk.tenant_id == tenant_id,
                PolicyChunk.doc_id == document_id,
            )
            .order_by(PolicyChunk.tenant_id, PolicyChunk.doc_id, PolicyChunk.id)
            .with_for_update()
        )
        return list((await self.session.execute(stmt)).scalars())

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
        return {(doc_key, chunk_id): content for doc_key, chunk_id, content in rows if counts[(doc_key, chunk_id)] == 1}

    async def get_provenance_by_evidence_keys(
        self,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], EvidenceProvenance]:
        if not keys:
            return {}

        stmt = (
            select(
                PolicyDocument.doc_key,
                PolicyDocument.version,
                PolicyChunk.chunk_id,
                PolicyChunk.doc_id,
                PolicyChunk.source_block_refs_json,
            )
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
        row_counts = Counter((row[0], row[2]) for row in rows)
        block_repo = DocumentBlockRepository(self.session)
        provenance: dict[tuple[str, str], EvidenceProvenance] = {}

        for doc_key, document_version, chunk_id, doc_id, source_refs in rows:
            key = (doc_key, chunk_id)
            if row_counts[key] != 1 or not isinstance(source_refs, list):
                continue

            valid_source_refs = [
                (ref, str(ref.get("source_block_id")))
                for ref in source_refs
                if isinstance(ref, dict) and str(ref.get("source_block_id") or "").strip()
            ]
            source_block_ids = [source_block_id for _, source_block_id in valid_source_refs]
            if not source_block_ids:
                continue

            blocks = await block_repo.get_by_source_block_ids(
                tenant_id=tenant_id,
                document_id=doc_id,
                source_block_ids=source_block_ids,
            )
            block_counts = Counter(block.source_block_id for block in blocks)
            if any(block_counts[source_block_id] != 1 for source_block_id in set(source_block_ids)):
                continue
            block_by_id = {block.source_block_id: block for block in blocks}
            if any(source_block_id not in block_by_id for source_block_id in source_block_ids):
                continue

            locators = []
            for ref, source_block_id in valid_source_refs:
                locators.append(source_locator_from_block(block_by_id[source_block_id], source_ref=ref))
            if not locators:
                continue
            provenance[key] = EvidenceProvenance(
                evidence_id=f"{doc_key}/{chunk_id}@v{document_version or 1}",
                doc_key=doc_key,
                chunk_id=chunk_id,
                source_locators=locators,
            )
        return provenance

    async def get_canonical_evidence_rows_by_keys(
        self,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict[str, object]]:
        if not keys:
            return {}

        stmt = (
            select(
                PolicyDocument.doc_key,
                PolicyDocument.version,
                PolicyDocument.doc_type,
                PolicyDocument.effective_date,
                PolicyChunk.chunk_id,
                PolicyChunk.content,
                PolicyChunk.risk_level,
                PolicyChunk.effective_date,
            )
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
        counts = Counter((row[0], row[4]) for row in rows)
        result: dict[tuple[str, str], dict[str, object]] = {}
        for (
            doc_key,
            document_version,
            doc_type,
            document_effective_date,
            chunk_id,
            content,
            risk_level,
            chunk_effective_date,
        ) in rows:
            key = (doc_key, chunk_id)
            if counts[key] != 1:
                continue
            version = int(document_version or 1)
            result[key] = {
                "tenant_id": str(tenant_id),
                "doc_key": doc_key,
                "chunk_id": chunk_id,
                "content": content,
                "policy_document_version": version,
                "current_policy_version": f"v{version}",
                "effective_date": chunk_effective_date or document_effective_date,
                "expires_at": None,
                "doc_type": doc_type,
                "risk_level": risk_level,
                "merchant_ids": [],
            }
        return result

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
        if not query_text.strip():
            return []
        query_expr = func.to_tsquery("simple", query_text)
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
