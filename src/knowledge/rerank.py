from __future__ import annotations

import asyncio
import math
import re
from collections.abc import Sequence
from typing import Any, Literal, Protocol

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from src.knowledge.config import (
    RERANK_CONFIG_VERSION,
    RERANK_MAX_CANDIDATES,
    RERANK_PROVIDER_ENABLED,
    RERANK_PROVIDER_MAX_RETRIES,
    RERANK_SCORE_CONFIG_VERSION,
    RERANK_STAGE_TIMEOUT_SECONDS,
    RERANK_TEXT_MAX_CHARS,
)


ScoreComponentName = Literal[
    "baseline_score",
    "lexical_overlap",
    "title_section_overlap",
    "channel_coverage",
    "rrf_score",
    "final_score",
]
FallbackReason = Literal[
    "provider_disabled",
    "provider_timeout",
    "provider_error",
    "provider_malformed_output",
    "budget_overflow",
]

_ALNUM_PATTERN = re.compile(r"[a-z0-9]+")
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
_CHANNEL_SUFFIXES = ("dense", "sparse", "fuzzy")
_UNSAFE_PROVIDER_TEXT_MARKERS = (
    "SHOULD_NOT_LEAK_RAW_PROVIDER_PAYLOAD",
    "SHOULD_NOT_LEAK_PRIVATE_REASONING",
    "SHOULD_NOT_LEAK_SOURCE_BLOCK",
    "SHOULD_NOT_LEAK_RAW_SOURCE_BLOCK",
    "SHOULD_NOT_LEAK_RAW_TOOL_PAYLOAD",
    "SHOULD_NOT_LEAK_UNBOUNDED_POLICY_TEXT",
    "raw_provider",
    "private_reasoning",
    "source_block",
    "raw_tool",
    "raw_prompt",
    "parser",
    "ocr",
    "business_fact",
)


class RerankCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    doc_key: str
    chunk_id: str
    policy_version: str
    title: str
    section: str
    text_snippet: str
    baseline_score: float
    baseline_rank: int
    selected_by: tuple[str, ...] = ()
    rrf_score: float | None = None


class RerankConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    config_version: str = RERANK_CONFIG_VERSION
    provider_enabled: bool = RERANK_PROVIDER_ENABLED
    max_candidates: int = RERANK_MAX_CANDIDATES
    text_max_chars: int = Field(
        default=RERANK_TEXT_MAX_CHARS,
        validation_alias=AliasChoices("text_max_chars", "max_candidate_text_chars"),
    )
    timeout_seconds: float = Field(
        default=RERANK_STAGE_TIMEOUT_SECONDS,
        validation_alias=AliasChoices("timeout_seconds", "provider_timeout_seconds"),
    )
    provider_max_retries: int = Field(
        default=RERANK_PROVIDER_MAX_RETRIES,
        validation_alias=AliasChoices("provider_max_retries", "max_provider_retries"),
    )

    @property
    def max_candidate_text_chars(self) -> int:
        return self.text_max_chars

    @property
    def max_provider_retries(self) -> int:
        return self.provider_max_retries

    @property
    def provider_timeout_seconds(self) -> float:
        return self.timeout_seconds


class ProviderRerankScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    score: float


class RerankScoreComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: ScoreComponentName
    value: float


class RerankedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    doc_key: str
    chunk_id: str
    policy_version: str
    title: str
    section: str
    text_snippet: str
    baseline_score: float
    baseline_rank: int
    selected_by: tuple[str, ...] = ()
    rrf_score: float | None = None
    rank: int
    final_score: float
    score_components: dict[ScoreComponentName, float] = Field(default_factory=dict)
    score_config_version: str = RERANK_SCORE_CONFIG_VERSION
    fallback_reason: FallbackReason | None = None

    @property
    def score(self) -> float:
        return self.baseline_score

    @property
    def text(self) -> str:
        return self.text_snippet


class RerankOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ranked_candidates: tuple[RerankedCandidate, ...]
    fallback_reason: FallbackReason | None = None
    config_version: str = RERANK_CONFIG_VERSION
    provider_config_version: str = RERANK_SCORE_CONFIG_VERSION

    @property
    def selected_candidate_ids(self) -> tuple[str, ...]:
        return tuple(candidate.candidate_id for candidate in self.ranked_candidates)

    def __iter__(self):
        return iter(self.ranked_candidates)

    def __len__(self) -> int:
        return len(self.ranked_candidates)

    def __getitem__(self, index: int) -> RerankedCandidate:
        return self.ranked_candidates[index]


class RerankerProviderAdapter(Protocol):
    async def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        config: RerankConfig,
    ) -> Sequence[ProviderRerankScore]: ...


class DefaultLocalReranker:
    def __init__(self, config: RerankConfig | None = None) -> None:
        self.config = config or RerankConfig()

    async def rerank(
        self,
        *,
        query: str,
        candidates: Sequence[RerankCandidate],
        config: RerankConfig | None = None,
        fallback_reason: FallbackReason | None = None,
    ) -> RerankOutput:
        effective_config = config or self.config
        ranked = _rank_locally(query=query, candidates=candidates, fallback_reason=fallback_reason)
        return RerankOutput(
            ranked_candidates=ranked,
            fallback_reason=fallback_reason,
            config_version=effective_config.config_version,
        )


async def rerank_candidates_for_query(
    *,
    query: str,
    candidates: Sequence[RerankCandidate],
    config: RerankConfig | None = None,
    provider: RerankerProviderAdapter | None = None,
) -> RerankOutput:
    effective_config = config or RerankConfig()
    local_reranker = DefaultLocalReranker(effective_config)

    if len(candidates) > effective_config.max_candidates:
        return await local_reranker.rerank(
            query=query,
            candidates=candidates,
            fallback_reason="budget_overflow",
        )
    if not effective_config.provider_enabled or provider is None:
        return await local_reranker.rerank(
            query=query,
            candidates=candidates,
            fallback_reason="provider_disabled",
        )

    provider_candidates = tuple(
        _sanitize_candidate_for_provider(candidate, effective_config) for candidate in candidates
    )
    try:
        provider_scores = await _call_provider_with_retries(
            provider=provider,
            query=query,
            candidates=provider_candidates,
            config=effective_config,
        )
    except TimeoutError:
        return await local_reranker.rerank(query=query, candidates=candidates, fallback_reason="provider_timeout")
    except Exception:
        return await local_reranker.rerank(query=query, candidates=candidates, fallback_reason="provider_error")

    normalized_scores = _normalize_provider_scores(provider_scores)
    if normalized_scores is None:
        return await local_reranker.rerank(
            query=query,
            candidates=candidates,
            fallback_reason="provider_malformed_output",
        )
    provider_order = _provider_order(
        query=query,
        candidates=candidates,
        provider_scores=normalized_scores,
    )
    if provider_order is None:
        return await local_reranker.rerank(
            query=query,
            candidates=candidates,
            fallback_reason="provider_malformed_output",
        )
    return RerankOutput(
        ranked_candidates=provider_order,
        fallback_reason=None,
        config_version=effective_config.config_version,
    )


async def _call_provider_with_retries(
    *,
    provider: RerankerProviderAdapter,
    query: str,
    candidates: Sequence[RerankCandidate],
    config: RerankConfig,
) -> Sequence[ProviderRerankScore]:
    last_error: Exception | None = None
    for _attempt in range(config.provider_max_retries + 1):
        try:
            return await asyncio.wait_for(
                provider.rerank(query=query, candidates=candidates, config=config),
                timeout=config.timeout_seconds,
            )
        except (asyncio.TimeoutError, TimeoutError) as exc:
            raise TimeoutError("provider timeout") from exc
        except Exception as exc:
            last_error = exc
    raise RuntimeError("provider error") from last_error


def _rank_locally(
    *,
    query: str,
    candidates: Sequence[RerankCandidate],
    fallback_reason: FallbackReason | None,
) -> tuple[RerankedCandidate, ...]:
    query_terms_value = _query_terms(query)
    scored = [
        _to_reranked_candidate(
            candidate,
            rank=0,
            final_score=_local_final_score(candidate, query_terms_value),
            score_components=_score_components(candidate, query_terms_value),
            fallback_reason=fallback_reason,
        )
        for candidate in candidates
    ]
    scored.sort(key=lambda item: (-item.final_score, item.baseline_rank, item.doc_key, item.chunk_id))
    return tuple(candidate.model_copy(update={"rank": rank}) for rank, candidate in enumerate(scored, start=1))


def _provider_order(
    *,
    query: str,
    candidates: Sequence[RerankCandidate],
    provider_scores: dict[str, float],
) -> tuple[RerankedCandidate, ...] | None:
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    if set(provider_scores) != set(candidate_by_id):
        return None
    query_terms_value = _query_terms(query)
    ranked = [
        _to_reranked_candidate(
            candidate_by_id[candidate_id],
            rank=0,
            final_score=score,
            score_components={
                **_score_components(candidate_by_id[candidate_id], query_terms_value),
                "final_score": score,
            },
            fallback_reason=None,
        )
        for candidate_id, score in provider_scores.items()
    ]
    ranked.sort(key=lambda item: (-item.final_score, item.baseline_rank, item.doc_key, item.chunk_id))
    return tuple(candidate.model_copy(update={"rank": rank}) for rank, candidate in enumerate(ranked, start=1))


def _to_reranked_candidate(
    candidate: RerankCandidate,
    *,
    rank: int,
    final_score: float,
    score_components: dict[ScoreComponentName, float],
    fallback_reason: FallbackReason | None,
) -> RerankedCandidate:
    return RerankedCandidate(
        candidate_id=candidate.candidate_id,
        doc_key=candidate.doc_key,
        chunk_id=candidate.chunk_id,
        policy_version=candidate.policy_version,
        title=candidate.title,
        section=candidate.section,
        text_snippet=candidate.text_snippet,
        baseline_score=_clamp_score(candidate.baseline_score),
        baseline_rank=candidate.baseline_rank,
        selected_by=candidate.selected_by,
        rrf_score=candidate.rrf_score,
        rank=rank,
        final_score=_clamp_score(final_score),
        score_components=score_components,
        fallback_reason=fallback_reason,
    )


def _score_components(
    candidate: RerankCandidate,
    query_terms_value: set[str],
) -> dict[ScoreComponentName, float]:
    lexical_overlap = _overlap_ratio(query_terms_value, candidate.text_snippet)
    title_section_overlap = _overlap_ratio(query_terms_value, f"{candidate.title} {candidate.section}")
    channel_coverage = _channel_coverage(candidate.selected_by)
    rrf_score = min(float(candidate.rrf_score or 0.0), 0.10)
    final_score = _clamp_score(
        candidate.baseline_score
        + 0.10 * lexical_overlap
        + 0.05 * title_section_overlap
        + 0.03 * channel_coverage
        + rrf_score
    )
    return {
        "baseline_score": _clamp_score(candidate.baseline_score),
        "lexical_overlap": lexical_overlap,
        "title_section_overlap": title_section_overlap,
        "channel_coverage": channel_coverage,
        "rrf_score": rrf_score,
        "final_score": final_score,
    }


def _local_final_score(candidate: RerankCandidate, query_terms_value: set[str]) -> float:
    return _score_components(candidate, query_terms_value)["final_score"]


def _channel_coverage(selected_by: tuple[str, ...]) -> float:
    channels = set()
    for label in selected_by:
        for suffix in _CHANNEL_SUFFIXES:
            if label == suffix or label.endswith(f"_{suffix}"):
                channels.add(suffix)
    return len(channels) / len(_CHANNEL_SUFFIXES)


def _sanitize_candidate_for_provider(candidate: RerankCandidate, config: RerankConfig) -> RerankCandidate:
    return candidate.model_copy(
        update={"text_snippet": _safe_provider_text(candidate.text_snippet, config.text_max_chars)}
    )


def _safe_provider_text(text: str, max_chars: int) -> str:
    safe_text = text
    for marker in _UNSAFE_PROVIDER_TEXT_MARKERS:
        safe_text = safe_text.replace(marker, "")
    return safe_text[:max_chars]


def _normalize_provider_scores(
    values: Sequence[ProviderRerankScore] | Sequence[dict[str, Any]],
) -> dict[str, float] | None:
    scores: dict[str, float] = {}
    for value in values:
        if isinstance(value, ProviderRerankScore):
            candidate_id = value.candidate_id
            raw_score = value.score
        elif isinstance(value, dict):
            candidate_id = value.get("candidate_id")
            raw_score = value.get("score")
        else:
            return None
        if not isinstance(candidate_id, str) or candidate_id in scores:
            return None
        if isinstance(raw_score, bool) or not isinstance(raw_score, int | float):
            return None
        score = float(raw_score)
        if not math.isfinite(score) or score < 0 or score > 1:
            return None
        scores[candidate_id] = score
    return scores


def _query_terms(text: str) -> set[str]:
    normalized = text.lower()
    terms = set(_ALNUM_PATTERN.findall(normalized))
    for segment in _CJK_PATTERN.findall(normalized):
        terms.update(segment)
        for size in (2, 3, 4):
            if len(segment) >= size:
                terms.update(segment[index : index + size] for index in range(len(segment) - size + 1))
    return {term for term in terms if term.strip()}


def _overlap_ratio(query_terms_value: set[str], text: str) -> float:
    if not query_terms_value or not text:
        return 0.0
    text_terms = _query_terms(text)
    if not text_terms:
        return 0.0
    return len(query_terms_value & text_terms) / min(len(query_terms_value), len(text_terms))


def _clamp_score(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)
