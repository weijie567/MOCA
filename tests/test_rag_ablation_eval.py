from __future__ import annotations

import json
from pathlib import Path


REQUIRED_PHASE23_GOLDEN_CATEGORIES = {
    "rewrite_win",
    "synonym_alias",
    "ambiguous_support_wording",
    "underspecified_question",
    "no_evidence_out_of_domain",
    "stale_unauthorized_evidence",
    "ranking_regression",
    "reranker_win",
}
REQUIRED_METRICS = {
    "hit_at_k",
    "mrr",
    "citation_support_compatibility",
    "no_evidence_precision",
    "unsafe_retrieval_rate",
    "fallback_rate",
    "latency_p50_ms",
    "latency_p95_ms",
}


def _load_ablation_api():
    from scripts.eval_rag_ablation import REQUIRED_ABLATION_VARIANTS, build_ablation_report, score_ablation_case

    return REQUIRED_ABLATION_VARIANTS, build_ablation_report, score_ablation_case


def _load_jsonl(path: str) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def test_phase23_golden_cases_cover_required_categories() -> None:
    _REQUIRED_ABLATION_VARIANTS, _build_ablation_report, _score_ablation_case = _load_ablation_api()
    cases = _load_jsonl("evaluation/golden/rag_cases.jsonl")
    categories = {case.get("category") for case in cases}

    assert REQUIRED_PHASE23_GOLDEN_CATEGORIES <= categories


def test_ablation_variants_include_required_modes() -> None:
    REQUIRED_ABLATION_VARIANTS, _build_ablation_report, _score_ablation_case = _load_ablation_api()

    assert {
        "dense_only",
        "sparse_only",
        "fuzzy_only",
        "rrf_baseline",
        "rewrite_enabled",
        "reranker_enabled",
        "rewrite_plus_reranker",
    } <= set(REQUIRED_ABLATION_VARIANTS)


def test_ablation_report_contains_rank_safety_fallback_and_latency_metrics() -> None:
    REQUIRED_ABLATION_VARIANTS, build_ablation_report, score_ablation_case = _load_ablation_api()
    case = {
        "id": "phase23-rewrite-win",
        "query": "商家发了货还能只退款吗？",
        "expected_doc_ids": ["refund_policy"],
        "expected_chunk_ids": ["refund_policy_001"],
        "should_fallback": False,
    }
    scored = score_ablation_case(
        case,
        {
            "variant": "rewrite_plus_reranker",
            "retrieval_status": "strong_evidence",
            "evidence": [
                {
                    "doc_key": "refund_policy",
                    "chunk_id": "refund_policy_001",
                    "rank": 1,
                    "score": 0.91,
                }
            ],
            "latency_ms": 87,
            "fallback_reason": None,
            "unsafe_retrieval": False,
            "citation_support_compatible": True,
        },
    )
    report = build_ablation_report(
        variant_results=[
            {
                "variant": variant,
                "case_scores": [scored],
                "latencies_ms": [87],
                "fallback_count": 0,
                "unsafe_retrieval_count": 0,
            }
            for variant in REQUIRED_ABLATION_VARIANTS
        ],
        generated_at="2026-06-20T00:00:00Z",
    )

    assert REQUIRED_METRICS <= set(report["metrics"])
    assert REQUIRED_METRICS <= set(report["per_variant"]["rewrite_plus_reranker"]["metrics"])
    assert report["metrics"]["hit_at_k"] >= 0
    assert report["metrics"]["mrr"] >= 0
    assert report["metrics"]["citation_support_compatibility"] >= 0
    assert report["metrics"]["no_evidence_precision"] == 0
    assert report["metrics"]["unsafe_retrieval_rate"] >= 0
    assert report["metrics"]["fallback_rate"] >= 0
    assert report["metrics"]["latency_p50_ms"] >= 0
    assert report["metrics"]["latency_p95_ms"] >= 0
    assert "fallback_reasons" in report
    assert "provider_config_version" in report
    assert "retrieval_config_version" in report
    assert "rerank_config_version" in report
    report_text = json.dumps(report, ensure_ascii=False, sort_keys=True)
    for forbidden_key in (
        "raw_prompt",
        "raw_provider",
        "private_reasoning",
        "source_block",
        "ocr_metadata",
        "raw_tool",
        "business_fact_payload",
        "provider_payload",
        "raw_rewrite_payload",
    ):
        assert forbidden_key not in report_text


def test_no_evidence_precision_counts_only_no_evidence_predictions() -> None:
    _REQUIRED_ABLATION_VARIANTS, build_ablation_report, score_ablation_case = _load_ablation_api()
    fallback_case = {
        "id": "phase23-no-evidence",
        "query": "用户问如何更换银行卡绑定手机号？",
        "expected_doc_ids": [],
        "expected_chunk_ids": [],
        "should_fallback": True,
    }
    normal_case = {
        "id": "phase23-hit",
        "query": "退款规则",
        "expected_doc_ids": ["refund_policy"],
        "expected_chunk_ids": ["refund_policy_001"],
        "should_fallback": False,
    }
    scores = [
        score_ablation_case(
            fallback_case,
            {"variant": "rrf_baseline", "retrieval_status": "no_evidence", "evidence": [], "latency_ms": 1},
        ),
        score_ablation_case(
            normal_case,
            {
                "variant": "rrf_baseline",
                "retrieval_status": "strong_evidence",
                "evidence": [{"doc_key": "refund_policy", "chunk_id": "refund_policy_001", "rank": 1}],
                "latency_ms": 1,
            },
        ),
    ]

    report = build_ablation_report(
        variant_results=[{"variant": "rrf_baseline", "case_scores": scores}],
        generated_at="2026-06-20T00:00:00Z",
    )

    assert report["metrics"]["no_evidence_precision"] == 1.0
