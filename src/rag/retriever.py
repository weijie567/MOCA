from __future__ import annotations

import re
from uuid import UUID

from src.rag.embedder import EmbeddingService
from src.rag.schemas import EvidenceItem, RetrievalResult
from src.repositories.policy_chunk_repo import PolicyChunkRepository


STRONG_EVIDENCE_THRESHOLD = 0.70
MIN_SIMILARITY_THRESHOLD = 0.55
QUERY_PREFIX = "电商售后政策查询: "
INTERNAL_SEARCH_THRESHOLD = 0.40
CANDIDATE_MULTIPLIER = 4
TITLE_SECTION_BOOST = 0.12
CONTENT_OVERLAP_BOOST = 0.08
FALLBACK_MESSAGE = "当前知识库中没有找到足够证据支持这个问题，建议转人工或补充规则文档。"

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


def _query_terms(text: str) -> set[str]:
    normalized = text.lower()
    terms = set(_ALNUM_PATTERN.findall(normalized))

    for segment in _CJK_PATTERN.findall(normalized):
        terms.update(segment)
        for size in (2, 3, 4):
            if len(segment) >= size:
                terms.update(segment[index : index + size] for index in range(len(segment) - size + 1))

    return {term for term in terms if term.strip()}


def _overlap_ratio(query_terms: set[str], text: str) -> float:
    if not query_terms or not text:
        return 0.0

    text_terms = _query_terms(text)
    if not text_terms:
        return 0.0

    return len(query_terms & text_terms) / min(len(query_terms), len(text_terms))


def _rerank_candidates(query: str, raw_results: list[tuple[object, float]]) -> list[tuple[object, float]]:
    query_terms = _query_terms(query)
    scored = []

    for rank, (chunk, vector_score) in enumerate(raw_results):
        title_section = f"{chunk.document.title} {chunk.section}"
        title_section_boost = TITLE_SECTION_BOOST * _overlap_ratio(query_terms, title_section)
        content_boost = CONTENT_OVERLAP_BOOST * _overlap_ratio(query_terms, chunk.content)
        hybrid_score = vector_score + title_section_boost + content_boost
        scored.append((chunk, vector_score, hybrid_score, rank))

    scored.sort(key=lambda item: (-item[2], item[3]))
    return [(chunk, vector_score) for chunk, vector_score, _, _ in scored]


def _has_domain_anchor(query: str) -> bool:
    return any(anchor in query for anchor in _DOMAIN_ANCHORS)


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
        query_embedding = await self.embedder.embed_query(f"{QUERY_PREFIX}{query}")

        raw_results = await self.chunk_repo.search_similar(
            query_embedding=query_embedding,
            tenant_id=tenant_id,
            top_k=max(top_k * CANDIDATE_MULTIPLIER, top_k),
            min_similarity=INTERNAL_SEARCH_THRESHOLD,
            doc_type=doc_type,
            risk_level=risk_level,
        )
        results = []
        if _has_domain_anchor(query):
            results = [
                (chunk, score)
                for chunk, score in _rerank_candidates(query, raw_results)
                if score >= MIN_SIMILARITY_THRESHOLD
            ][:top_k]

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
