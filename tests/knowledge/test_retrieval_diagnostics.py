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
        RankingExplanation,
        RetrievalDiagnostics,
        build_retrieval_diagnostics,
    )

    return RetrievalDiagnostics, RankingExplanation, build_retrieval_diagnostics


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
    RetrievalDiagnostics, _RankingExplanation, build_retrieval_diagnostics = _load_diagnostics_api()
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
    RetrievalDiagnostics, RankingExplanation, _build_retrieval_diagnostics = _load_diagnostics_api()
    explanation = RankingExplanation(
        candidate_id="refund_policy/refund_policy_001@v1",
        selected_channels=("dense", "sparse"),
        rewrite_contribution="matched rewrite expansion: 已发货 仅退款",
        rerank_contribution="lexical and section overlap promoted the candidate",
        original_rank=4,
        final_rank=1,
        rank_delta=-3,
        score_components={"lexical_overlap": 0.38, "channel_coverage": 0.66},
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
        "retrieved_at",
        "retrieval_config_version",
        "score",
        "rank",
    }
    diagnostics_text = _json_text(diagnostics)
    assert "refund_policy/refund_policy_001@v1" in diagnostics_text
    assert "ranking_explanations" in diagnostics_text
    assert "EvidenceRefV1" not in diagnostics_text


def test_ranking_explanation_contains_safe_components() -> None:
    _RetrievalDiagnostics, RankingExplanation, _build_retrieval_diagnostics = _load_diagnostics_api()

    explanation = RankingExplanation(
        candidate_id="refund_policy/refund_policy_001@v1",
        selected_channels=("dense", "sparse", "fuzzy"),
        rewrite_contribution="rewrite_expansion: 已发货 仅退款 商家举证",
        rerank_contribution="title_section_overlap + channel_coverage",
        original_rank=5,
        final_rank=1,
        rank_delta=-4,
        score_components={
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
    assert dumped["rewrite_contribution"]
    assert dumped["rerank_contribution"]
    assert dumped["rank_delta"] == -4
    assert set(dumped["score_components"]) == {
        "lexical_overlap",
        "title_section_overlap",
        "channel_coverage",
        "rrf_score",
    }
    assert dumped["provider_config_version"] == "rerank.v3"
    assert dumped["fallback_reason"] == "provider_disabled"
