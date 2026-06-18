from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import PolicyChunk
from src.rag.search_text import build_policy_chunk_search_text


async def rebuild_policy_chunk_search_texts(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
) -> int:
    """Rebuild retrieval-only search text for existing policy chunks.

    Phase 20's original migration could only backfill a lossy SQL expression.
    This maintenance path applies the same Python tokenizer used by ingestion
    without changing citation content.
    """
    stmt = select(PolicyChunk).options(selectinload(PolicyChunk.document))
    if tenant_id is not None:
        stmt = stmt.where(PolicyChunk.tenant_id == tenant_id)

    chunks = list((await session.execute(stmt)).scalars().all())
    for chunk in chunks:
        chunk.search_text = build_policy_chunk_search_text(
            title=str(chunk.document.title),
            section=str(chunk.section),
            content=str(chunk.content),
            doc_type=str(chunk.document.doc_type),
            risk_level=str(chunk.risk_level),
        )
    await session.flush()
    return len(chunks)
