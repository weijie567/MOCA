from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge.config import (
    MERGED_CANDIDATE_CAP,
    MIN_SIMILARITY_THRESHOLD,
    ORIGINAL_QUERY_TOP_K,
    RERANK_TEXT_MAX_CHARS,
    RETRIEVAL_CONFIG_VERSION,
    RETRIEVAL_TOTAL_TIMEOUT_SECONDS,
    REWRITE_QUERY_TOP_K,
    STRONG_EVIDENCE_THRESHOLD,
)
from src.knowledge.diagnostics import RankingExplanation, RetrievalDiagnostics, build_retrieval_diagnostics
from src.knowledge.provenance import EvidenceProvenance
from src.knowledge.rerank import RerankCandidate, RerankConfig, rerank_candidates_for_query
from src.knowledge.rewrite import build_query_rewrite_plan, safe_rewrite_summary
from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext
from src.rag.embedder import EmbeddingService
from src.rag.search_text import build_policy_chunk_search_text, build_sparse_query_text
from src.repositories.policy_chunk_repo import PolicyChunkRepository


QUERY_PREFIX = "电商售后政策查询: "
INTERNAL_SEARCH_THRESHOLD = 0.40
CANDIDATE_MULTIPLIER = 4
SPARSE_CANDIDATE_TOP_K = 50
FUZZY_CANDIDATE_TOP_K = 20
FUZZY_MIN_SIMILARITY = 0.10
RRF_K = 60
SPARSE_SCORE_SCALE = 0.20
TITLE_SECTION_BOOST = 0.12
CONTENT_OVERLAP_BOOST = 0.08
RETRIEVAL_TIMEOUT_SECONDS = RETRIEVAL_TOTAL_TIMEOUT_SECONDS
POLICY_NO_EVIDENCE_MESSAGE = "当前知识库中没有找到足够证据支持这个问题，建议转人工或补充规则文档。"
_SAFE_CHANNEL_LABEL_EXAMPLES = ("original_dense", "rewrite_1_sparse")

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
    selected_by: tuple[str, ...] = ()
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fuzzy_rank: int | None = None
    rrf_score: float | None = None
    filter_status: str = "passed"


@dataclass(frozen=True)
class PolicyRetrievalRun:
    status: str
    hits: list[PolicyRetrievalHit]
    evidence_refs: list[EvidenceRefV1]
    best_score: float
    original_query: str
    query_rewrite_summary: str | None = None
    fallback_reason: str | None = None
    diagnostics: RetrievalDiagnostics | None = None


@dataclass
class _FusedCandidate:
    chunk: object
    dense_score: float | None = None
    sparse_score: float | None = None
    fuzzy_score: float | None = None
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fuzzy_rank: int | None = None
    rrf_score: float = 0.0
    channel_labels: list[str] = field(default_factory=list)

    @property
    def selected_by(self) -> tuple[str, ...]:
        if any(label.startswith("rewrite_") for label in self.channel_labels):
            return tuple(self.channel_labels)

        channels: list[str] = []
        if self.dense_rank is not None:
            channels.append("dense")
        if self.sparse_rank is not None:
            channels.append("sparse")
        if self.fuzzy_rank is not None:
            channels.append("fuzzy")
        return tuple(channels)

    @property
    def confidence(self) -> float:
        scores = []
        if self.dense_score is not None:
            scores.append(_clamp_score(self.dense_score))
        if self.sparse_score is not None:
            scores.append(normalize_sparse_score(self.sparse_score))
        if self.fuzzy_score is not None:
            scores.append(_clamp_score(self.fuzzy_score))
        return max(scores, default=0.0)


def normalize_sparse_score(raw_score: float) -> float:
    return _clamp_score(raw_score / SPARSE_SCORE_SCALE)


def rrf_fuse_candidates(
    channel_results: dict[str, list[tuple[object, float]]],
    *,
    channel_prefix: str | None = None,
) -> list[_FusedCandidate]:
    candidates: dict[tuple[str, str, str], _FusedCandidate] = {}

    for channel, results in channel_results.items():
        seen_in_channel: set[tuple[str, str, str]] = set()
        for rank, (chunk, raw_score) in enumerate(results, start=1):
            key = _candidate_key(chunk)
            if key in seen_in_channel:
                continue
            seen_in_channel.add(key)

            candidate = candidates.setdefault(key, _FusedCandidate(chunk=chunk))
            score = float(raw_score or 0.0)
            if channel == "dense":
                candidate.dense_rank = rank
                candidate.dense_score = score
            elif channel == "sparse":
                candidate.sparse_rank = rank
                candidate.sparse_score = score
            elif channel == "fuzzy":
                candidate.fuzzy_rank = rank
                candidate.fuzzy_score = score
            if channel_prefix is not None:
                _append_safe_channel_label(candidate, f"{channel_prefix}_{channel}")
            candidate.rrf_score += 1 / (RRF_K + rank)

    return sorted(
        candidates.values(),
        key=lambda candidate: (
            -candidate.rrf_score,
            -candidate.confidence,
            str(candidate.chunk.document.doc_key),
            str(candidate.chunk.chunk_id),
        ),
    )


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
        run = await self.retrieve_run(
            query=query,
            context=context,
            max_results=max_results,
            doc_type=doc_type,
            risk_level=risk_level,
        )
        return run.status, run.evidence_refs, run.best_score

    async def retrieve_hits(
        self,
        *,
        query: str,
        context: KnowledgeContext,
        max_results: int,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> tuple[str, list[PolicyRetrievalHit], float]:
        run = await self.retrieve_run(
            query=query,
            context=context,
            max_results=max_results,
            doc_type=doc_type,
            risk_level=risk_level,
        )
        return run.status, run.hits, run.best_score

    async def retrieve_run(
        self,
        *,
        query: str,
        context: KnowledgeContext,
        max_results: int,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> PolicyRetrievalRun:
        try:
            return await asyncio.wait_for(
                self._retrieve_run(
                    query=query,
                    context=context,
                    max_results=max_results,
                    doc_type=doc_type,
                    risk_level=risk_level,
                ),
                timeout=RETRIEVAL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return PolicyRetrievalRun(
                status="error",
                hits=[],
                evidence_refs=[],
                best_score=0.0,
                original_query=query,
                fallback_reason="rewrite_timeout",
            )

    async def get_contents_by_evidence_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], str]:
        return await self.chunk_repo.get_contents_by_evidence_keys(tenant_id, keys)

    async def get_provenance_by_evidence_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], EvidenceProvenance]:
        return await self.chunk_repo.get_provenance_by_evidence_keys(tenant_id, keys)

    async def get_canonical_evidence_rows_by_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict[str, object]]:
        return await self.chunk_repo.get_canonical_evidence_rows_by_keys(tenant_id, keys)

    async def _retrieve_run(
        self,
        *,
        query: str,
        context: KnowledgeContext,
        max_results: int,
        doc_type: str | None,
        risk_level: str | None,
    ) -> PolicyRetrievalRun:
        effective_at = _parse_effective_at(context.effective_at)
        effective_date = effective_at.date()
        limit = max(max_results, 1)
        original_candidates = await self._retrieve_query_channel(
            query_text=query,
            channel_prefix="original",
            tenant_id=UUID(context.tenant_id),
            effective_date=effective_date,
            limit=limit,
            top_k=max(limit * CANDIDATE_MULTIPLIER, limit),
            doc_type=doc_type,
            risk_level=risk_level,
        )
        candidates = original_candidates
        query_rewrite_summary: str | None = None
        fallback_reason: str | None = None

        try:
            rewrite_plan = build_query_rewrite_plan(query, context)
            query_rewrite_summary = safe_rewrite_summary(rewrite_plan)
        except asyncio.TimeoutError:
            fallback_reason = "rewrite_timeout"
            rewrite_plan = None
        except Exception:
            fallback_reason = "rewrite_error"
            rewrite_plan = None

        if rewrite_plan is not None and rewrite_plan.skip_reason is None:
            try:
                rewrite_candidates: list[_FusedCandidate] = []
                for index, rewrite_query in enumerate(rewrite_plan.rewritten_queries, start=1):
                    rewrite_candidates.extend(
                        await self._retrieve_query_channel(
                            query_text=rewrite_query,
                            channel_prefix=f"rewrite_{index}",
                            tenant_id=UUID(context.tenant_id),
                            effective_date=effective_date,
                            limit=limit,
                            top_k=REWRITE_QUERY_TOP_K,
                            doc_type=doc_type,
                            risk_level=risk_level,
                        )
                    )
            except asyncio.TimeoutError:
                fallback_reason = "rewrite_timeout"
                rewrite_candidates = []
            except Exception:
                fallback_reason = "rewrite_channel_error"
                rewrite_candidates = []

            if fallback_reason is None:
                try:
                    candidates = _merge_query_candidates(original_candidates, rewrite_candidates)
                except Exception:
                    fallback_reason = "merge_error"

        hits, best_score, status = await _finalize_hits(
            query=query,
            candidates=candidates,
            limit=limit,
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
        return PolicyRetrievalRun(
            status=status,
            hits=hits,
            evidence_refs=evidence_refs,
            best_score=best_score,
            original_query=query,
            query_rewrite_summary=query_rewrite_summary,
            fallback_reason=fallback_reason,
            diagnostics=_build_internal_diagnostics(
                query=query,
                query_rewrite_summary=query_rewrite_summary,
                hits=hits,
                fallback_reason=fallback_reason,
            ),
        )

    async def _retrieve_query_channel(
        self,
        *,
        query_text: str,
        channel_prefix: str,
        tenant_id: UUID,
        effective_date: date,
        limit: int,
        top_k: int,
        doc_type: str | None,
        risk_level: str | None,
    ) -> list[_FusedCandidate]:
        query_embedding = await self.embedder.embed_query(f"{QUERY_PREFIX}{query_text}")
        query_search_text = build_policy_chunk_search_text(title="", section="", content=query_text)
        sparse_query_text = build_sparse_query_text(query_text)
        dense_raw_results = await self.chunk_repo.search_similar(
            query_embedding=query_embedding,
            tenant_id=tenant_id,
            top_k=min(max(top_k, limit), ORIGINAL_QUERY_TOP_K if top_k != REWRITE_QUERY_TOP_K else REWRITE_QUERY_TOP_K),
            min_similarity=INTERNAL_SEARCH_THRESHOLD,
            doc_type=doc_type,
            risk_level=risk_level,
            effective_date=effective_date,
        )
        sparse_raw_results = await _call_optional_channel(
            self.chunk_repo,
            "search_sparse",
            query_text=sparse_query_text,
            tenant_id=tenant_id,
            top_k=SPARSE_CANDIDATE_TOP_K,
            doc_type=doc_type,
            risk_level=risk_level,
            effective_date=effective_date,
        )
        fuzzy_raw_results = await _call_optional_channel(
            self.chunk_repo,
            "search_fuzzy",
            query_text=query_search_text,
            tenant_id=tenant_id,
            top_k=FUZZY_CANDIDATE_TOP_K,
            min_similarity=FUZZY_MIN_SIMILARITY,
            doc_type=doc_type,
            risk_level=risk_level,
            effective_date=effective_date,
        )

        dense_results = rerank_candidates(query_text, _filter_effective_results(dense_raw_results, effective_date))
        sparse_results = _filter_effective_results(sparse_raw_results, effective_date)
        fuzzy_results = _filter_effective_results(fuzzy_raw_results, effective_date)
        return rrf_fuse_candidates(
            {
                "dense": dense_results,
                "sparse": sparse_results,
                "fuzzy": fuzzy_results,
            },
            channel_prefix=channel_prefix,
        )


def _merge_query_candidates(
    original_candidates: list[_FusedCandidate],
    rewrite_candidates: list[_FusedCandidate],
) -> list[_FusedCandidate]:
    merged: dict[tuple[str, str, str], _FusedCandidate] = {}
    for candidate in [*original_candidates, *rewrite_candidates]:
        key = _candidate_key(candidate.chunk)
        existing = merged.get(key)
        if existing is None:
            merged[key] = candidate
            continue
        existing.rrf_score += candidate.rrf_score
        for label in candidate.channel_labels:
            _append_safe_channel_label(existing, label)
        if candidate.dense_score is not None and (
            existing.dense_score is None or candidate.dense_score > existing.dense_score
        ):
            existing.dense_score = candidate.dense_score
            existing.dense_rank = candidate.dense_rank
        if candidate.sparse_score is not None and (
            existing.sparse_score is None or candidate.sparse_score > existing.sparse_score
        ):
            existing.sparse_score = candidate.sparse_score
            existing.sparse_rank = candidate.sparse_rank
        if candidate.fuzzy_score is not None and (
            existing.fuzzy_score is None or candidate.fuzzy_score > existing.fuzzy_score
        ):
            existing.fuzzy_score = candidate.fuzzy_score
            existing.fuzzy_rank = candidate.fuzzy_rank
    return _sort_candidates(list(merged.values()))[:MERGED_CANDIDATE_CAP]


async def _finalize_hits(
    *,
    query: str,
    candidates: list[_FusedCandidate],
    limit: int,
) -> tuple[list[PolicyRetrievalHit], float, str]:
    fused_results = [
        candidate
        for candidate in _sort_candidates(candidates)
        if candidate.confidence >= MIN_SIMILARITY_THRESHOLD
    ][:MERGED_CANDIDATE_CAP]
    if has_domain_anchor(query):
        results = fused_results[:limit]
    else:
        terms = query_terms(query)
        results = [
            candidate
            for candidate in fused_results
            if candidate.confidence >= STRONG_EVIDENCE_THRESHOLD and has_candidate_overlap(terms, candidate.chunk)
        ][:limit]

    rerank_candidates = tuple(
        _to_rerank_candidate(candidate, baseline_rank=rank)
        for rank, candidate in enumerate(results, start=1)
    )
    fused_by_rerank_id = {
        rerank_candidate.candidate_id: candidate
        for rerank_candidate, candidate in zip(rerank_candidates, results, strict=True)
    }
    try:
        rerank_output = await rerank_candidates_for_query(
            query=query,
            candidates=rerank_candidates,
            config=RerankConfig(),
        )
        ordered_candidates = rerank_output.ranked_candidates
    except Exception:
        ordered_candidates = rerank_candidates

    hits = []
    for rank, reranked_candidate in enumerate(ordered_candidates, start=1):
        candidate = fused_by_rerank_id[reranked_candidate.candidate_id]
        # Rerank final_score is diagnostic-only; evidence scores and thresholds
        # stay on baseline normalized confidence.
        hits.append(
            PolicyRetrievalHit(
                doc_key=str(candidate.chunk.document.doc_key),
                chunk_id=candidate.chunk.chunk_id,
                title=str(candidate.chunk.document.title),
                section=str(candidate.chunk.section),
                policy_version=_policy_version(candidate.chunk),
                text=candidate.chunk.content,
                score=reranked_candidate.baseline_score,
                rank=rank,
                selected_by=candidate.selected_by,
                dense_rank=candidate.dense_rank,
                sparse_rank=candidate.sparse_rank,
                fuzzy_rank=candidate.fuzzy_rank,
                rrf_score=candidate.rrf_score,
            )
        )
    best_score = max((hit.score for hit in hits), default=0.0)
    if not hits or best_score < MIN_SIMILARITY_THRESHOLD:
        status = "no_evidence"
    elif best_score >= STRONG_EVIDENCE_THRESHOLD:
        status = "strong_evidence"
    else:
        status = "partial_evidence"
    return hits, best_score, status


def _sort_candidates(candidates: list[_FusedCandidate]) -> list[_FusedCandidate]:
    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.rrf_score,
            -candidate.confidence,
            str(candidate.chunk.document.doc_key),
            str(candidate.chunk.chunk_id),
        ),
    )


def _to_rerank_candidate(candidate: _FusedCandidate, *, baseline_rank: int) -> RerankCandidate:
    doc_key = str(candidate.chunk.document.doc_key)
    chunk_id = candidate.chunk.chunk_id
    policy_version = _policy_version(candidate.chunk)
    return RerankCandidate(
        candidate_id=f"{doc_key}/{chunk_id}@{policy_version}",
        doc_key=doc_key,
        chunk_id=chunk_id,
        policy_version=policy_version,
        title=str(candidate.chunk.document.title),
        section=str(candidate.chunk.section),
        text_snippet=str(candidate.chunk.content)[:RERANK_TEXT_MAX_CHARS],
        baseline_score=candidate.confidence,
        baseline_rank=baseline_rank,
        selected_by=candidate.selected_by,
        rrf_score=candidate.rrf_score,
    )


def _build_internal_diagnostics(
    *,
    query: str,
    query_rewrite_summary: str | None,
    hits: list[PolicyRetrievalHit],
    fallback_reason: str | None,
) -> RetrievalDiagnostics:
    candidate_ids = [f"{hit.doc_key}/{hit.chunk_id}@{hit.policy_version}" for hit in hits]
    explanations = [
        RankingExplanation(
            candidate_id=candidate_id,
            selected_channels=hit.selected_by,
            rewrite_contribution=1.0 if query_rewrite_summary and "rewrite_count=0" not in query_rewrite_summary else 0.0,
            rerank_contribution=min(float(hit.rrf_score or 0.0), 0.10),
            rank_before=None,
            rank_after=hit.rank,
            safe_score_components={
                "baseline_score": hit.score,
                "rrf_score": min(float(hit.rrf_score or 0.0), 0.10),
            },
            fallback_reason=fallback_reason,
        )
        for candidate_id, hit in zip(candidate_ids, hits, strict=True)
    ]
    return build_retrieval_diagnostics(
        original_query=query,
        query_rewrite_summary=query_rewrite_summary,
        ranking_explanations=explanations,
        selected_candidate_ids=candidate_ids,
        fallback_reason=fallback_reason,
    )


def _append_safe_channel_label(candidate: _FusedCandidate, label: str) -> None:
    if label not in candidate.channel_labels:
        candidate.channel_labels.append(label)


def _parse_effective_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _chunk_effective_date(chunk: object) -> date | None:
    value = getattr(chunk, "effective_date", None)
    if isinstance(value, date):
        return value
    return None


def _filter_effective_results(
    raw_results: list[tuple[object, float]],
    effective_date: date,
) -> list[tuple[object, float]]:
    return [
        (chunk, score)
        for chunk, score in raw_results
        if _chunk_effective_date(chunk) is None or _chunk_effective_date(chunk) <= effective_date
    ]


async def _call_optional_channel(
    repo: object,
    method_name: str,
    **kwargs,
) -> list[tuple[object, float]]:
    method = getattr(repo, method_name, None)
    if method is None:
        return []
    return await method(**kwargs)


def _candidate_key(chunk: object) -> tuple[str, str, str]:
    return (str(chunk.document.doc_key), str(chunk.chunk_id), _policy_version(chunk))


def _policy_version(chunk: object) -> str:
    return f"v{getattr(chunk.document, 'version', 1)}"


def _clamp_score(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)
