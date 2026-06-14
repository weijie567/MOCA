from __future__ import annotations

import asyncio
import re
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge.config import (
    MIN_SIMILARITY_THRESHOLD,
    RETRIEVAL_CONFIG_VERSION,
    STRONG_EVIDENCE_THRESHOLD,
)
from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext
from src.rag.embedder import EmbeddingService
from src.repositories.policy_chunk_repo import PolicyChunkRepository


QUERY_PREFIX = "电商售后政策查询: "
INTERNAL_SEARCH_THRESHOLD = 0.40
CANDIDATE_MULTIPLIER = 4
TITLE_SECTION_BOOST = 0.12
CONTENT_OVERLAP_BOOST = 0.08
RETRIEVAL_TIMEOUT_SECONDS = 15.0

_ALNUM_PATTERN = re.compile(r"[a-z0-9]+")
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
_DOMAIN_ANCHORS = {
    "补偿",
    "审批",
    "订单",
    "客服",
    "商家",
    "商品",
    "售后",
    "投诉",
    "物流",
    "申诉",
    "质量",
    "退款",
    "退货",
    "运费",
    "跨境",
    "证据",
    "争议",
}


def query_terms(text: str) -> set[str]:
    normalized = text.lower()
    terms = set(_ALNUM_PATTERN.findall(normalized))

    for segment in _CJK_PATTERN.findall(normalized):
        terms.update(segment)
        for size in (2, 3, 4):
            if len(segment) >= size:
                terms.update(segment[index : index + size] for index in range(len(segment) - size + 1))

    return {term for term in terms if term.strip()}


def overlap_ratio(query_terms_value: set[str], text: str) -> float:
    if not query_terms_value or not text:
        return 0.0

    text_terms = query_terms(text)
    if not text_terms:
        return 0.0

    return len(query_terms_value & text_terms) / min(len(query_terms_value), len(text_terms))


def rerank_candidates(query: str, raw_results: list[tuple[object, float]]) -> list[tuple[object, float]]:
    terms = query_terms(query)
    scored = []

    for rank, (chunk, vector_score) in enumerate(raw_results):
        title_section = f"{chunk.document.title} {chunk.section}"
        title_section_boost = TITLE_SECTION_BOOST * overlap_ratio(terms, title_section)
        content_boost = CONTENT_OVERLAP_BOOST * overlap_ratio(terms, chunk.content)
        hybrid_score = vector_score + title_section_boost + content_boost
        scored.append((chunk, vector_score, hybrid_score, rank))

    scored.sort(key=lambda item: (-item[2], item[3]))
    return [(chunk, vector_score) for chunk, vector_score, _, _ in scored]


def has_domain_anchor(query: str) -> bool:
    return any(anchor in query for anchor in _DOMAIN_ANCHORS)


def has_candidate_overlap(query_terms_value: set[str], chunk: object) -> bool:
    candidate_text = f"{chunk.document.title} {chunk.section} {chunk.content}"
    return overlap_ratio(query_terms_value, candidate_text) > 0


class PolicyRetrievalEngine:
    """Public policy retrieval engine owned by the knowledge domain."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        *,
        chunk_repo: PolicyChunkRepository | None = None,
        embedder: EmbeddingService | None = None,
    ) -> None:
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

        effective_results = [
            (chunk, score) for chunk, score in raw_results if chunk.effective_date <= effective_date
        ]
        reranked_results = [
            (chunk, score)
            for chunk, score in rerank_candidates(query, effective_results)
            if score >= MIN_SIMILARITY_THRESHOLD
        ]
        if has_domain_anchor(query):
            results = reranked_results[:max_results]
        else:
            terms = query_terms(query)
            results = [
                (chunk, score)
                for chunk, score in reranked_results
                if score >= STRONG_EVIDENCE_THRESHOLD and has_candidate_overlap(terms, chunk)
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
