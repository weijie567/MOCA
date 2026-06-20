from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.knowledge.config import MAX_REWRITE_QUERY_CHARS, RERANK_CONFIG_VERSION


class RankingExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    selected_channels: tuple[str, ...] = ()
    rewrite_contribution: str | None = None
    rerank_contribution: str | None = None
    original_rank: int | None = None
    final_rank: int | None = None
    rank_delta: int | None = None
    score_components: dict[str, float] = Field(default_factory=dict)
    provider_config_version: str
    fallback_reason: str | None = None


class RetrievalDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    original_query: str
    safe_query_rewrite_summary: str | None = None
    safe_summary: str | None = None
    rewrite_expansion_count: int = 0
    ranking_explanations: list[RankingExplanation] = Field(default_factory=list)
    selected_candidate_ids: list[str] = Field(default_factory=list)
    diagnostics_version: str = "retrieval_diagnostics.v1"


class RerankDiagnosticRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    config_version: str = RERANK_CONFIG_VERSION
    provider_config_version: str | None = None
    fallback_reason: str | None = None
    selected_candidate_ids: list[str] = Field(default_factory=list)
    score_components: dict[str, dict[str, float]] = Field(default_factory=dict)


def build_retrieval_diagnostics(
    *,
    original_query: str,
    query_rewrite_summary: str | None = None,
    rewrite_expansion_count: int = 0,
    raw_rewrite_payload: dict | None = None,
) -> RetrievalDiagnostics:
    del raw_rewrite_payload
    safe_summary = _bound_summary(query_rewrite_summary)
    return RetrievalDiagnostics(
        original_query=original_query,
        safe_query_rewrite_summary=safe_summary,
        safe_summary=safe_summary,
        rewrite_expansion_count=rewrite_expansion_count,
    )


def _bound_summary(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:MAX_REWRITE_QUERY_CHARS]
