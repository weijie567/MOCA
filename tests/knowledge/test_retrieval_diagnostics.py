from __future__ import annotations

import json

from src.knowledge.schemas import EvidenceRefV1
from src.knowledge.schemas import KnowledgeContext

RAW_REWRITE_PROMPT = "SHOULD_NOT_LEAK_RAW_REWRITE_PROMPT"
RAW_PROVIDER_PAYLOAD = "SHOULD_NOT_LEAK_RAW_PROVIDER_PAYLOAD"
PRIVATE_REASONING = "SHOULD_NOT_LEAK_PRIVATE_REASONING"
RAW_SOURCE_BLOCK = "SHOULD_NOT_LEAK_RAW_SOURCE_BLOCK"
RAW_TOOL_PAYLOAD = "SHOULD_NOT_LEAK_RAW_TOOL_PAYLOAD"
UNBOUNDED_POLICY_TEXT = "SHOULD_NOT_LEAK_UNBOUNDED_POLICY_TEXT " * 80


def _load_diagnostics_api():
    from src.knowledge.diagnostics import (
        DiagnosticEvidenceExclusion,
        RankingExplanation,
        RetrievalDiagnostics,
        build_retrieval_diagnostics,
    )

    return RetrievalDiagnostics, RankingExplanation, DiagnosticEvidenceExclusion, build_retrieval_diagnostics


def _json_text(value: object) -> str:
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def _context() -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id="tenant-001",
        user_id="user-001",
        role="support_agent",
        merchant_scope=["merchant-001"],
        run_id="run-001",
        trace_id="trace-001",
        locale="zh-CN",
        effective_at="2026-06-14T00:00:00+00:00",
    )


def test_query_rewrite_summary_excludes_raw_payloads() -> None:
    RetrievalDiagnostics, _RankingExplanation, _DiagnosticEvidenceExclusion, build_retrieval_diagnostics = (
        _load_diagnostics_api()
    )
    from src.knowledge.rewrite import build_query_rewrite_plan, safe_rewrite_summary

    rewrite_plan = build_query_rewrite_plan("商家已发货还能仅退款吗？", _context())
    safe_summary = safe_rewrite_summary(rewrite_plan)

    diagnostics = build_retrieval_diagnostics(
        original_query="商家已发货还能仅退款吗？",
        query_rewrite_summary=safe_summary,
        rewrite_expansion_count=len(rewrite_plan.rewritten_queries),
        raw_rewrite_payload={
            "raw_prompt": RAW_REWRITE_PROMPT,
            "raw_provider": RAW_PROVIDER_PAYLOAD,
            "private_reasoning": PRIVATE_REASONING,
            "source_block": RAW_SOURCE_BLOCK,
            "tool_payload": RAW_TOOL_PAYLOAD,
            "text": UNBOUNDED_POLICY_TEXT,
        },
    )

    assert isinstance(diagnostics, RetrievalDiagnostics)
    diagnostics_text = _json_text(diagnostics)
    assert "safe_summary" in diagnostics_text
    assert "rewrite_count=2" in diagnostics_text
    assert "triggers=仅退款,已发货" in diagnostics_text
    for sentinel in (
        RAW_REWRITE_PROMPT,
        RAW_PROVIDER_PAYLOAD,
        PRIVATE_REASONING,
        RAW_SOURCE_BLOCK,
        RAW_TOOL_PAYLOAD,
        UNBOUNDED_POLICY_TEXT,
    ):
        assert sentinel not in diagnostics_text


def test_rerank_diagnostics_do_not_extend_evidence_ref() -> None:
    RetrievalDiagnostics, RankingExplanation, _DiagnosticEvidenceExclusion, _build_retrieval_diagnostics = (
        _load_diagnostics_api()
    )
    explanation = RankingExplanation(
        candidate_id="refund_policy/refund_policy_001@v1",
        selected_channels=("dense", "sparse"),
        rewrite_contribution=1.0,
        rerank_contribution=0.42,
        rank_before=4,
        rank_after=1,
        rank_delta=-3,
        safe_score_components={"lexical_overlap": 0.38, "channel_coverage": 0.66},
        provider_config_version="rerank.v3",
        fallback_reason=None,
    )
    diagnostics = RetrievalDiagnostics(
        original_query="商家已发货还能仅退款吗？",
        safe_query_rewrite_summary="扩展为已发货仅退款和商家举证。",
        ranking_explanations=[explanation],
        selected_candidate_ids=["refund_policy/refund_policy_001@v1"],
        diagnostics_version="retrieval_diagnostics.v1",
    )

    fields = set(EvidenceRefV1.model_fields)
    assert fields == {
        "schema_version",
        "tenant_id",
        "evidence_id",
        "doc_key",
        "chunk_id",
        "policy_version",
        "text_hash",
        "scope_type",
        "scope_id",
        "document_version_id",
        "chunk_version_id",
        "document_version",
        "chunk_version",
        "retrieved_at",
        "retrieval_config_version",
        "score",
        "rank",
    }
    assert {
        "ranking_explanations",
        "rank_before",
        "rank_after",
        "rank_delta",
        "rerank_contribution",
        "provider_config_version",
    }.isdisjoint(fields)
    diagnostics_text = _json_text(diagnostics)
    assert "refund_policy/refund_policy_001@v1" in diagnostics_text
    assert "ranking_explanations" in diagnostics_text
    assert "EvidenceRefV1" not in diagnostics_text


def test_ranking_explanation_contains_safe_components() -> None:
    _RetrievalDiagnostics, RankingExplanation, _DiagnosticEvidenceExclusion, _build_retrieval_diagnostics = (
        _load_diagnostics_api()
    )

    explanation = RankingExplanation(
        candidate_id="refund_policy/refund_policy_001@v1",
        selected_channels=("dense", "sparse", "fuzzy"),
        rewrite_contribution=1.0,
        rerank_contribution=0.62,
        rank_before=5,
        rank_after=1,
        rank_delta=-4,
        safe_score_components={
            "lexical_overlap": 0.41,
            "title_section_overlap": 0.33,
            "channel_coverage": 1.0,
            "rrf_score": 0.032,
        },
        provider_config_version="rerank.v3",
        fallback_reason="provider_disabled",
    )

    dumped = explanation.model_dump(mode="json")
    assert dumped["candidate_id"] == "refund_policy/refund_policy_001@v1"
    assert dumped["selected_channels"] == ["dense", "sparse", "fuzzy"]
    assert dumped["rewrite_contribution"] == 1.0
    assert dumped["rerank_contribution"] == 0.62
    assert dumped["rank_before"] == 5
    assert dumped["rank_after"] == 1
    assert dumped["rank_delta"] == -4
    assert set(dumped["safe_score_components"]) == {
        "lexical_overlap",
        "title_section_overlap",
        "channel_coverage",
        "rrf_score",
    }
    assert dumped["provider_config_version"] == "rerank.v3"
    assert dumped["fallback_reason"] == "provider_disabled"


def test_phase22_evidence_validation_reason_codes_exclude_unsafe_diagnostic_candidates() -> None:
    """Mirrors test_phase22_evidence_validation reason-code patterns for EXP-03 diagnostics."""
    RetrievalDiagnostics, RankingExplanation, DiagnosticEvidenceExclusion, build_retrieval_diagnostics = (
        _load_diagnostics_api()
    )
    excluded_ids = {
        "candidate_scope_invalid": ["scope_invalid"],
        "candidate_freshness_invalid": ["freshness_invalid"],
        "candidate_effective_date_invalid": ["effective_date_invalid"],
        "candidate_latest_version_invalid": ["latest_version_invalid"],
        "candidate_text_hash_mismatch": ["text_hash_mismatch"],
    }
    diagnostics = build_retrieval_diagnostics(
        original_query="商家已发货还能仅退款吗？",
        selected_candidate_ids=["candidate_valid", *excluded_ids],
        ranking_explanations=[
            RankingExplanation(
                candidate_id=candidate_id,
                selected_channels=("dense",),
                rewrite_contribution=0.0,
                rerank_contribution=0.0,
                rank_before=rank,
                rank_after=rank,
                safe_score_components={"baseline_score": 0.8},
            )
            for rank, candidate_id in enumerate(["candidate_valid", *excluded_ids], start=1)
        ],
        excluded_evidence=[
            DiagnosticEvidenceExclusion(evidence_id=evidence_id, reason_codes=reason_codes)
            for evidence_id, reason_codes in excluded_ids.items()
        ],
    )

    assert isinstance(diagnostics, RetrievalDiagnostics)
    assert diagnostics.selected_candidate_ids == ["candidate_valid"]
    assert [explanation.candidate_id for explanation in diagnostics.ranking_explanations] == ["candidate_valid"]
    reason_codes = {reason for item in diagnostics.excluded_evidence for reason in item.reason_codes}
    assert {
        "scope_invalid",
        "freshness_invalid",
        "effective_date_invalid",
        "latest_version_invalid",
        "text_hash_mismatch",
    } <= reason_codes
