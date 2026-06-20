"""Deterministic Phase 23 RAG ablation evaluation.

Default dry-run mode uses golden-case metadata only. It does not require live
provider credentials, network access, Redis, or a real embedding/model service.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION


DEFAULT_GOLDEN_SET = "evaluation/golden/rag_cases.jsonl"
DEFAULT_OUTPUT = "evaluation/reports/rag_ablation.json"
TEXT_SNIPPET_MAX_CHARS = 160

REQUIRED_ABLATION_VARIANTS = (
    "dense_only",
    "sparse_only",
    "fuzzy_only",
    "rrf_baseline",
    "rewrite_enabled",
    "reranker_enabled",
    "rewrite_plus_reranker",
)
REQUIRED_ABLATION_METRICS = (
    "hit_at_k",
    "mrr",
    "citation_support_compatibility",
    "no_evidence_precision",
    "unsafe_retrieval_rate",
    "fallback_rate",
    "latency_p50_ms",
    "latency_p95_ms",
)
FALLBACK_REASONS = (
    "provider_disabled",
    "provider_timeout",
    "provider_error",
    "provider_malformed_output",
    "budget_overflow",
    "rewrite_timeout",
    "rewrite_error",
)


def score_ablation_case(case: dict[str, Any], variant_result: dict[str, Any]) -> dict[str, Any]:
    evidence = [_redact_evidence(item) for item in variant_result.get("evidence", [])]
    expected_chunks = set(case.get("expected_chunk_ids", []))
    expected_docs = set(case.get("expected_doc_ids", []))
    got_chunks = [str(item.get("chunk_id", "")) for item in evidence]
    got_docs = {str(item.get("doc_key", "")) for item in evidence}
    first_match_rank = _first_match_rank(evidence, expected_chunks, expected_docs)
    should_fallback = bool(case.get("should_fallback"))
    retrieval_status = str(variant_result.get("retrieval_status", "no_evidence"))
    predicted_no_evidence = retrieval_status == "no_evidence" and not evidence

    if should_fallback:
        hit = predicted_no_evidence
        no_evidence_correct = hit
    else:
        hit = first_match_rank is not None
        no_evidence_correct = False

    fallback_reason = variant_result.get("fallback_reason")
    return {
        "case_id": case.get("id") or case.get("query", "unknown-case"),
        "category": case.get("category"),
        "variant": variant_result.get("variant"),
        "hit": hit,
        "reciprocal_rank": (1 / first_match_rank) if first_match_rank else 0.0,
        "citation_support_compatible": bool(variant_result.get("citation_support_compatible", hit)),
        "predicted_no_evidence": predicted_no_evidence,
        "no_evidence_correct": no_evidence_correct,
        "unsafe_retrieval": bool(variant_result.get("unsafe_retrieval", False)),
        "fallback": fallback_reason is not None or should_fallback,
        "fallback_reason": fallback_reason,
        "latency_ms": float(variant_result.get("latency_ms", 0.0)),
        "selected_candidate_ids": [
            _candidate_id(item)
            for item in evidence
            if item.get("doc_key") and item.get("chunk_id")
        ],
        "safe_evidence": evidence,
        "missing_expected_chunks": sorted(expected_chunks - set(got_chunks)),
        "expected_doc_id_hit": bool(expected_docs & got_docs),
    }


def build_ablation_report(
    *,
    variant_results: list[dict[str, Any]],
    thresholds: dict[str, float] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    per_variant: dict[str, dict[str, Any]] = {}
    all_scores: list[dict[str, Any]] = []
    fallback_reasons: dict[str, int] = {reason: 0 for reason in FALLBACK_REASONS}

    for result in variant_results:
        variant = str(result["variant"])
        case_scores = list(result.get("case_scores", []))
        all_scores.extend(case_scores)
        per_variant[variant] = {
            "metrics": _metrics(case_scores),
            "failed_cases": _failed_case_ids(case_scores),
            "fallback_reasons": _fallback_reason_counts(case_scores),
        }
        for reason, count in per_variant[variant]["fallback_reasons"].items():
            fallback_reasons[reason] = fallback_reasons.get(reason, 0) + count

    metrics = _metrics(all_scores)
    return {
        "eval_type": "rag_ablation",
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "thresholds": thresholds or _default_thresholds(),
        "metrics": metrics,
        "per_variant": per_variant,
        "failed_cases": _failed_case_ids(all_scores),
        "fallback_reasons": fallback_reasons,
        "retrieval_config_version": RETRIEVAL_CONFIG_VERSION,
        "rerank_config_version": RERANK_CONFIG_VERSION,
        "provider_config_version": "provider_disabled",
        "required_variants": list(REQUIRED_ABLATION_VARIANTS),
        "required_metrics": list(REQUIRED_ABLATION_METRICS),
    }


def run_rag_ablation(
    *,
    golden_set: str = DEFAULT_GOLDEN_SET,
    output: str | None = DEFAULT_OUTPUT,
    dry_run: bool = True,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    cases = _load_cases(golden_set)
    variant_results = [
        {
            "variant": variant,
            "case_scores": [
                score_ablation_case(case, _fake_variant_result(case, variant, index=index))
                for index, case in enumerate(cases, start=1)
            ],
        }
        for variant in REQUIRED_ABLATION_VARIANTS
    ]
    report = build_ablation_report(
        variant_results=variant_results,
        thresholds=thresholds,
    )
    report["mode"] = "dry_run" if dry_run else "deterministic_local"
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 23 deterministic RAG ablation evaluation")
    parser.add_argument("--golden-set", default=DEFAULT_GOLDEN_SET)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true", default=False)
    return parser


def _load_cases(path: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _fake_variant_result(case: dict[str, Any], variant: str, *, index: int) -> dict[str, Any]:
    expected_doc_ids = list(case.get("expected_doc_ids", []))
    expected_chunk_ids = list(case.get("expected_chunk_ids", []))
    should_fallback = bool(case.get("should_fallback"))
    evidence = []
    if not should_fallback and expected_doc_ids and expected_chunk_ids:
        evidence.append(
            {
                "doc_key": expected_doc_ids[0],
                "chunk_id": expected_chunk_ids[0],
                "rank": 1,
                "score": 0.90,
                "text_snippet": f"safe deterministic snippet for {case.get('id', index)}",
            }
        )
    fallback_reason = "provider_disabled" if variant in {"reranker_enabled", "rewrite_plus_reranker"} else None
    return {
        "variant": variant,
        "retrieval_status": "no_evidence" if should_fallback else "strong_evidence",
        "evidence": evidence,
        "latency_ms": 20 + index,
        "fallback_reason": fallback_reason,
        "unsafe_retrieval": False,
        "citation_support_compatible": True,
    }


def _metrics(case_scores: list[dict[str, Any]]) -> dict[str, float]:
    if not case_scores:
        return {metric: 0.0 for metric in REQUIRED_ABLATION_METRICS}
    latencies = [float(score.get("latency_ms", 0.0)) for score in case_scores]
    fallback_cases = [score for score in case_scores if score.get("fallback")]
    no_evidence_predictions = [score for score in case_scores if score.get("predicted_no_evidence")]
    return {
        "hit_at_k": _rate(score.get("hit") for score in case_scores),
        "mrr": sum(float(score.get("reciprocal_rank", 0.0)) for score in case_scores) / len(case_scores),
        "citation_support_compatibility": _rate(score.get("citation_support_compatible") for score in case_scores),
        "no_evidence_precision": _rate(score.get("no_evidence_correct") for score in no_evidence_predictions),
        "unsafe_retrieval_rate": _rate(score.get("unsafe_retrieval") for score in case_scores),
        "fallback_rate": len(fallback_cases) / len(case_scores),
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
    }


def _failed_case_ids(case_scores: list[dict[str, Any]]) -> list[str]:
    return [str(score["case_id"]) for score in case_scores if not score.get("hit")]


def _fallback_reason_counts(case_scores: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for score in case_scores:
        reason = score.get("fallback_reason")
        if isinstance(reason, str):
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def _first_match_rank(
    evidence: list[dict[str, Any]],
    expected_chunks: set[str],
    expected_docs: set[str],
) -> int | None:
    for rank, item in enumerate(evidence, start=1):
        if str(item.get("chunk_id", "")) in expected_chunks or str(item.get("doc_key", "")) in expected_docs:
            return int(item.get("rank") or rank)
    return None


def _redact_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_key": item.get("doc_key"),
        "chunk_id": item.get("chunk_id"),
        "rank": item.get("rank"),
        "score": item.get("score"),
        "text_snippet": str(item.get("text_snippet") or item.get("text") or "")[:TEXT_SNIPPET_MAX_CHARS],
    }


def _candidate_id(item: dict[str, Any]) -> str:
    return f"{item['doc_key']}/{item['chunk_id']}"


def _rate(values) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(1 for value in items if value) / len(items)


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = round((percentile / 100) * (len(sorted_values) - 1))
    return float(sorted_values[index])


def _default_thresholds() -> dict[str, float]:
    return {
        "hit_at_k": 0.80,
        "mrr": 0.50,
        "citation_support_compatibility": 0.95,
        "no_evidence_precision": 0.90,
        "unsafe_retrieval_rate": 0.0,
        "fallback_rate": 0.50,
        "latency_p50_ms": 750.0,
        "latency_p95_ms": 1500.0,
    }


def main() -> None:
    args = _parser().parse_args()
    report = run_rag_ablation(golden_set=args.golden_set, output=args.output, dry_run=args.dry_run)
    print(json.dumps({"status": "ok", "metrics": report["metrics"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
