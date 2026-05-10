from __future__ import annotations

from uuid import UUID

from src.rag.embedder import EmbeddingService
from src.rag.schemas import EvidenceItem, RetrievalResult
from src.repositories.policy_chunk_repo import PolicyChunkRepository


STRONG_EVIDENCE_THRESHOLD = 0.70
MIN_SIMILARITY_THRESHOLD = 0.55
FALLBACK_MESSAGE = "当前知识库中没有找到足够证据支持这个问题，建议转人工或补充规则文档。"


class Retriever:
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
        query_embedding = await self.embedder.embed_query(query)

        results = await self.chunk_repo.search_similar(
            query_embedding=query_embedding,
            tenant_id=tenant_id,
            top_k=top_k,
            min_similarity=MIN_SIMILARITY_THRESHOLD,
            doc_type=doc_type,
            risk_level=risk_level,
        )

        evidence = [
            EvidenceItem(
                doc_key=chunk.document.doc_key,
                chunk_id=chunk.chunk_id,
                title=chunk.document.title,
                section=chunk.section,
                score=score,
                text=chunk.content[:300],
            )
            for chunk, score in results
        ]

        best_score = max((item.score for item in evidence), default=0.0)
        if not evidence or best_score < MIN_SIMILARITY_THRESHOLD:
            status = "no_evidence"
        elif best_score >= STRONG_EVIDENCE_THRESHOLD:
            status = "strong_evidence"
        else:
            status = "partial_evidence"

        return RetrievalResult(
            query=query,
            retrieval_status=status,
            evidence=evidence,
            best_score=best_score,
            fallback_message=FALLBACK_MESSAGE if status == "no_evidence" else None,
        )
