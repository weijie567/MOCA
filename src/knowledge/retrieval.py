from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date, datetime
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
POLICY_NO_EVIDENCE_MESSAGE = "当前知识库中没有找到足够证据支持这个问题，建议转人工或补充规则文档。"

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


@dataclass(frozen=True)
class PolicyRetrievalHit:
    doc_key: str
    chunk_id: str
    title: str
    section: str
    policy_version: str
    text: str
    score: float
    rank: int


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
        status, hits, best_score = await self.retrieve_hits(
            query=query,
            context=context,
            max_results=max_results,
            doc_type=doc_type,
            risk_level=risk_level,
        )
        evidence_refs = [
            EvidenceRefV1.build(
                tenant_id=context.tenant_id,
                doc_key=hit.doc_key,
                chunk_id=hit.chunk_id,
                policy_version=hit.policy_version,
                text=hit.text,
                retrieved_at=context.effective_at,
                retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
                score=hit.score,
                rank=hit.rank,
            )
            for hit in hits
        ]
        return status, evidence_refs, best_score

    async def retrieve_hits(
        self,
        *,
        query: str,
        context: KnowledgeContext,
        max_results: int,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> tuple[str, list[PolicyRetrievalHit], float]:
        try:
            return await asyncio.wait_for(
                self._retrieve_hits(
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

    async def get_contents_by_evidence_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], str]:
        return await self.chunk_repo.get_contents_by_evidence_keys(tenant_id, keys)

    async def _retrieve_hits(
        self,
        *,
        query: str,
        context: KnowledgeContext,
        max_results: int,
        doc_type: str | None,
        risk_level: str | None,
    ) -> tuple[str, list[PolicyRetrievalHit], float]:
        effective_at = _parse_effective_at(context.effective_at)
        effective_date = effective_at.date()
        limit = max(max_results, 1)
        query_embedding = await self.embedder.embed_query(f"{QUERY_PREFIX}{query}")
        raw_results = await self.chunk_repo.search_similar(
            query_embedding=query_embedding,
            tenant_id=UUID(context.tenant_id),
            top_k=max(limit * CANDIDATE_MULTIPLIER, limit),
            min_similarity=INTERNAL_SEARCH_THRESHOLD,
            doc_type=doc_type,
            risk_level=risk_level,
            effective_date=effective_date,
        )

        effective_results = [
            (chunk, score)
            for chunk, score in raw_results
            if _chunk_effective_date(chunk) is None or _chunk_effective_date(chunk) <= effective_date
        ]
        reranked_results = [
            (chunk, score)
            for chunk, score in rerank_candidates(query, effective_results)
            if score >= MIN_SIMILARITY_THRESHOLD
        ]
        if has_domain_anchor(query):
            results = reranked_results[:limit]
        else:
            terms = query_terms(query)
            results = [
                (chunk, score)
                for chunk, score in reranked_results
                if score >= STRONG_EVIDENCE_THRESHOLD and has_candidate_overlap(terms, chunk)
            ][:limit]

        hits = [
            PolicyRetrievalHit(
                doc_key=str(chunk.document.doc_key),
                chunk_id=chunk.chunk_id,
                title=str(chunk.document.title),
                section=str(chunk.section),
                policy_version=f"v{getattr(chunk.document, 'version', 1)}",
                text=chunk.content,
                score=score,
                rank=rank,
            )
            for rank, (chunk, score) in enumerate(results, start=1)
        ]
        best_score = max((hit.score for hit in hits), default=0.0)
        if not hits or best_score < MIN_SIMILARITY_THRESHOLD:
            status = "no_evidence"
        elif best_score >= STRONG_EVIDENCE_THRESHOLD:
            status = "strong_evidence"
        else:
            status = "partial_evidence"
        return status, hits, best_score


def _parse_effective_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _chunk_effective_date(chunk: object) -> date | None:
    value = getattr(chunk, "effective_date", None)
    if isinstance(value, date):
        return value
    return None
