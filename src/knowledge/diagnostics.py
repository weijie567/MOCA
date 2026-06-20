from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from src.knowledge.config import (
    MAX_REWRITE_QUERY_CHARS,
    RERANK_CONFIG_VERSION,
    RETRIEVAL_CONFIG_VERSION,
    RETRIEVAL_DIAGNOSTICS_VERSION,
)


class RankingExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    candidate_id: str
    selected_channels: tuple[str, ...] = ()
    rewrite_contribution: float = 0.0
    rerank_contribution: float = 0.0
    rank_before: int | None = Field(default=None, validation_alias=AliasChoices("rank_before", "original_rank"))
    rank_after: int = Field(validation_alias=AliasChoices("rank_after", "final_rank"))
    rank_delta: int | None = None
    safe_score_components: dict[str, float] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("safe_score_components", "score_components"),
    )
    provider_config_version: str | None = None
    fallback_reason: str | None = None


class RewriteDiagnosticRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    safe_summary: str | None = None
    rewrite_expansion_count: int = 0
    trigger_terms: tuple[str, ...] = ()
    fallback_reason: str | None = None


class DiagnosticEvidenceExclusion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    reason_codes: list[str]


class RerankDiagnosticRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    config_version: str = RERANK_CONFIG_VERSION
    provider_config_version: str | None = None
    fallback_reason: str | None = None
    selected_candidate_ids: list[str] = Field(default_factory=list)
    score_components: dict[str, dict[str, float]] = Field(default_factory=dict)


class RetrievalDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    original_query: str
    query_rewrite_summary: str | None = None
    safe_query_rewrite_summary: str | None = None
    safe_summary: str | None = None
    rewrite_expansion_count: int = 0
    rewrite_diagnostic: RewriteDiagnosticRecord | None = None
    rerank_diagnostic: RerankDiagnosticRecord | None = None
    ranking_explanations: list[RankingExplanation] = Field(default_factory=list)
    selected_candidate_ids: list[str] = Field(default_factory=list)
    excluded_evidence: list[DiagnosticEvidenceExclusion] = Field(default_factory=list)
    retrieval_config_version: str = RETRIEVAL_CONFIG_VERSION
    rerank_config_version: str = RERANK_CONFIG_VERSION
    fallback_reason: str | None = None
    latency_ms: float | None = None
    diagnostics_version: str = RETRIEVAL_DIAGNOSTICS_VERSION


def build_retrieval_diagnostics(
    *,
    original_query: str,
    query_rewrite_summary: str | None = None,
    rewrite_expansion_count: int = 0,
    rerank_diagnostic: RerankDiagnosticRecord | None = None,
    ranking_explanations: list[RankingExplanation] | None = None,
    selected_candidate_ids: list[str] | None = None,
    excluded_evidence: list[DiagnosticEvidenceExclusion] | None = None,
    fallback_reason: str | None = None,
    latency_ms: float | None = None,
    raw_rewrite_payload: dict | None = None,
) -> RetrievalDiagnostics:
    del raw_rewrite_payload
    safe_summary = _bound_summary(query_rewrite_summary)
    exclusions = excluded_evidence or []
    excluded_ids = {item.evidence_id for item in exclusions}
    safe_candidate_ids = [candidate_id for candidate_id in selected_candidate_ids or [] if candidate_id not in excluded_ids]
    safe_explanations = [
        explanation
        for explanation in ranking_explanations or []
        if explanation.candidate_id not in excluded_ids
    ]
    return RetrievalDiagnostics(
        original_query=original_query,
        query_rewrite_summary=safe_summary,
        safe_query_rewrite_summary=safe_summary,
        safe_summary=safe_summary,
        rewrite_expansion_count=rewrite_expansion_count,
        rewrite_diagnostic=RewriteDiagnosticRecord(
            safe_summary=safe_summary,
            rewrite_expansion_count=rewrite_expansion_count,
            fallback_reason=fallback_reason,
        ),
        rerank_diagnostic=rerank_diagnostic,
        ranking_explanations=safe_explanations,
        selected_candidate_ids=safe_candidate_ids,
        excluded_evidence=exclusions,
        fallback_reason=fallback_reason,
        latency_ms=latency_ms,
    )


def _bound_summary(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:MAX_REWRITE_QUERY_CHARS]
