from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.tools.search_policy import search_policy as legacy_search_policy
from src.knowledge.config import (
    MIN_SIMILARITY_THRESHOLD,
    RETRIEVAL_CONFIG_VERSION,
    STRONG_EVIDENCE_THRESHOLD,
)
from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext
from src.rag.embedder import EmbeddingService
from src.rag.retriever import (
    CANDIDATE_MULTIPLIER,
    INTERNAL_SEARCH_THRESHOLD,
    QUERY_PREFIX,
    _has_candidate_overlap,
    _has_domain_anchor,
    _query_terms,
    _rerank_candidates,
)
from src.repositories.policy_chunk_repo import PolicyChunkRepository

__all__ = ["LegacyRagKnowledgeAdapter", "legacy_search_policy"]

RETRIEVAL_TIMEOUT_SECONDS = 15.0


class LegacyRagKnowledgeAdapter:
    """Adapt the existing repository/embedder retrieval path to EvidenceRefV1."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        *,
        chunk_repo: PolicyChunkRepository | None = None,
        embedder: EmbeddingService | None = None,
    ):
        if chunk_repo is None:
            if session is None:
                raise ValueError("session or chunk_repo is required")
            chunk_repo = PolicyChunkRepository(session)
        self.chunk_repo = chunk_repo
        self.embedder = embedder or EmbeddingService()

    async def retrieve(
        self,
        *,
        query: str,
        context: KnowledgeContext,
        max_results: int,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> tuple[str, list[EvidenceRefV1], float]:
        try:
            return await asyncio.wait_for(
                self._retrieve(
                    query=query,
                    context=context,
                    max_results=max_results,
                    doc_type=doc_type,
                    risk_level=risk_level,
                ),
                timeout=RETRIEVAL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return "error", [], 0.0

    async def _retrieve(
        self,
        *,
        query: str,
        context: KnowledgeContext,
        max_results: int,
        doc_type: str | None,
        risk_level: str | None,
    ) -> tuple[str, list[EvidenceRefV1], float]:
        effective_at = datetime.fromisoformat(context.effective_at.replace("Z", "+00:00"))
        effective_date = effective_at.date()
        query_embedding = await self.embedder.embed_query(f"{QUERY_PREFIX}{query}")
        raw_results = await self.chunk_repo.search_similar(
            query_embedding=query_embedding,
            tenant_id=UUID(context.tenant_id),
            top_k=max(max_results * CANDIDATE_MULTIPLIER, max_results),
            min_similarity=INTERNAL_SEARCH_THRESHOLD,
            doc_type=doc_type,
            risk_level=risk_level,
            effective_date=effective_date,
        )

        # Effective-time filtering precedes reranking and final top-k truncation.
        effective_results = [
            (chunk, score) for chunk, score in raw_results if chunk.effective_date <= effective_date
        ]
        reranked_results = [
            (chunk, score)
            for chunk, score in _rerank_candidates(query, effective_results)
            if score >= MIN_SIMILARITY_THRESHOLD
        ]
        if _has_domain_anchor(query):
            results = reranked_results[:max_results]
        else:
            query_terms = _query_terms(query)
            results = [
                (chunk, score)
                for chunk, score in reranked_results
                if score >= STRONG_EVIDENCE_THRESHOLD and _has_candidate_overlap(query_terms, chunk)
            ][:max_results]

        evidence_refs = [
            EvidenceRefV1.build(
                tenant_id=context.tenant_id,
                doc_key=chunk.document.doc_key,
                chunk_id=chunk.chunk_id,
                policy_version=f"v{chunk.document.version}",
                text=chunk.content,
                retrieved_at=context.effective_at,
                retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
                score=score,
                rank=rank,
            )
            for rank, (chunk, score) in enumerate(results, start=1)
        ]
        best_score = max((ref.score or 0.0 for ref in evidence_refs), default=0.0)
        if not evidence_refs or best_score < MIN_SIMILARITY_THRESHOLD:
            status = "no_evidence"
        elif best_score >= STRONG_EVIDENCE_THRESHOLD:
            status = "strong_evidence"
        else:
            status = "partial_evidence"
        return status, evidence_refs, best_score
