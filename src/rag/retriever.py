from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from src.knowledge.retrieval import (
    CANDIDATE_MULTIPLIER as CANDIDATE_MULTIPLIER,
    INTERNAL_SEARCH_THRESHOLD as INTERNAL_SEARCH_THRESHOLD,
    MIN_SIMILARITY_THRESHOLD as MIN_SIMILARITY_THRESHOLD,
    POLICY_NO_EVIDENCE_MESSAGE,
    QUERY_PREFIX as QUERY_PREFIX,
    STRONG_EVIDENCE_THRESHOLD as STRONG_EVIDENCE_THRESHOLD,
    PolicyRetrievalEngine,
)
from src.knowledge.schemas import KnowledgeContext
from src.rag.embedder import EmbeddingService
from src.rag.schemas import EvidenceItem, RetrievalResult
from src.repositories.policy_chunk_repo import PolicyChunkRepository


FALLBACK_MESSAGE = POLICY_NO_EVIDENCE_MESSAGE

__all__ = [
    "CANDIDATE_MULTIPLIER",
    "FALLBACK_MESSAGE",
    "INTERNAL_SEARCH_THRESHOLD",
    "MIN_SIMILARITY_THRESHOLD",
    "QUERY_PREFIX",
    "Retriever",
    "STRONG_EVIDENCE_THRESHOLD",
]


class Retriever:
    """Compatibility facade over the knowledge-owned retrieval engine."""

    def __init__(self, chunk_repo: PolicyChunkRepository, embedder: EmbeddingService):
        self.chunk_repo = chunk_repo
        self.embedder = embedder

    async def search(
        self,
        query: str,
        tenant_id: UUID,
        top_k: int = 5,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> RetrievalResult:
        engine = PolicyRetrievalEngine(chunk_repo=self.chunk_repo, embedder=self.embedder)
        status, hits, best_score = await engine.retrieve_hits(
            query=query,
            context=KnowledgeContext(
                tenant_id=str(tenant_id),
                user_id="api",
                role="knowledge_reader",
                merchant_scope=["*"],
                run_id="api-search",
                trace_id="api-search",
                effective_at=datetime.now(UTC).isoformat(),
            ),
            max_results=top_k,
            doc_type=doc_type,
            risk_level=risk_level,
        )
        retrieval_status = status if status != "error" else "no_evidence"
        evidence = [
            EvidenceItem(
                doc_key=hit.doc_key,
                chunk_id=hit.chunk_id,
                title=hit.title,
                section=hit.section,
                score=hit.score,
                text=hit.text[:300],
            )
            for hit in hits
        ]
        return RetrievalResult(
            query=query,
            retrieval_status=retrieval_status,
            evidence=evidence,
            best_score=best_score,
            fallback_message=FALLBACK_MESSAGE if retrieval_status == "no_evidence" else None,
        )
