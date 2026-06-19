"""Deterministic Phase 22 hallucination-control eval scaffold.

Usage:
    uv run python scripts/eval_phase22_hallucination.py \
        --dataset evaluation/golden/phase22_hallucination_cases.jsonl \
        --fail-thresholds

The default path is local-only. It loads and validates JSONL cases, then uses a
future ``src.agent.rag_context.metrics.evaluate_hallucination_case`` adapter if
available. In Wave 0 the adapter is intentionally missing, so threshold mode
exits with status 1 after producing a parse-clean JSON report.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from src.agent.rag_context.metrics import DEFAULT_HALLUCINATION_THRESHOLDS
from src.agent.rag_context.metrics import threshold_failures as metric_threshold_failures


DEFAULT_DATASET = "evaluation/golden/phase22_hallucination_cases.jsonl"
DEFAULT_THRESHOLDS = dict(DEFAULT_HALLUCINATION_THRESHOLDS)
REQUIRED_FIELDS = {
    "id",
    "category",
    "query",
    "input",
    "expected_verifier_status",
    "expected_route",
    "expected_metrics_bucket",
    "must_not_contain",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 22 Hallucination-Control Evaluation")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Path to Phase 22 JSONL golden set")
    parser.add_argument("--output", help="Optional path to write the JSON report; stdout is always emitted")
    parser.add_argument(
        "--fail-thresholds",
        action="store_true",
        help="Exit 1 when implementation is missing or metrics do not meet blocking thresholds",
    )
    return parser


def _load_cases(path: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        case = json.loads(line)
        _validate_case(case, line_no=line_no)
        cases.append(case)
    if not cases:
        raise ValueError("dataset contains no cases")
    return cases


def _validate_case(case: dict[str, Any], *, line_no: int) -> None:
    missing = sorted(REQUIRED_FIELDS - set(case))
    if missing:
        raise ValueError(f"line {line_no}: missing required fields: {', '.join(missing)}")
    if not isinstance(case["id"], str) or not case["id"].strip():
        raise ValueError(f"line {line_no}: id must be a non-empty string")
    if not isinstance(case["input"], dict):
        raise ValueError(f"line {line_no}: input must be an object")
    if not isinstance(case["must_not_contain"], list) or not all(
        isinstance(item, str) for item in case["must_not_contain"]
    ):
        raise ValueError(f"line {line_no}: must_not_contain must be a list of strings")
    if not isinstance(case["expected_metrics_bucket"], str):
        raise ValueError(f"line {line_no}: expected_metrics_bucket must be a string")


def _missing_implementation_result(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "verifier_status": "implementation_missing",
        "route": "implementation_missing",
        "citation_supported": False,
        "unsafe_answer": False,
        "answer_text": "",
        "business_data_hallucinated": False,
        "level3_triggered": False,
        "timed_out": False,
        "fail_closed": False,
        "leakage_count": 0,
        "implementation_missing": True,
    }


def _load_evaluator() -> Callable[[dict[str, Any]], dict[str, Any]]:
    try:
        from src.agent.rag_context.metrics import evaluate_hallucination_case
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("src.agent.rag_context"):
            return _missing_implementation_result
        raise
    if not callable(evaluate_hallucination_case):
        return _missing_implementation_result
    return evaluate_hallucination_case


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    raise TypeError(f"evaluator returned unsupported result type: {type(value).__name__}")


def _leakage_count(case: dict[str, Any], actual: dict[str, Any]) -> int:
    answer_text = str(actual.get("answer_text") or "")
    explicit_count = int(actual.get("leakage_count") or 0)
    sentinel_count = sum(1 for sentinel in case["must_not_contain"] if sentinel and sentinel in answer_text)
    return explicit_count + sentinel_count


def _score_case(case: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    expected_route = case["expected_route"]
    expected_status = case["expected_verifier_status"]
    expected_citation = bool(case.get("expected_citation_support", False))
    route_correct = actual.get("route") == expected_route
    verifier_correct = actual.get("verifier_status") == expected_status
    citation_correct = bool(actual.get("citation_supported", False)) is expected_citation
    leakage_count = _leakage_count(case, actual)
    unsafe_answer = bool(actual.get("unsafe_answer", False)) or (
        expected_route != "allow" and actual.get("route") == "allow"
    )
    return {
        "id": case["id"],
        "category": case["category"],
        "expected_verifier_status": expected_status,
        "actual_verifier_status": actual.get("verifier_status"),
        "expected_route": expected_route,
        "actual_route": actual.get("route"),
        "claim_support_correct": verifier_correct,
        "citation_support_correct": citation_correct,
        "route_correct": route_correct,
        "unsafe_answer": unsafe_answer,
        "business_data_hallucinated": bool(actual.get("business_data_hallucinated", False)),
        "leakage_count": leakage_count,
        "level3_triggered": bool(actual.get("level3_triggered", False)),
        "expected_level3_trigger": bool(case.get("expected_level3_trigger", False)),
        "timed_out": bool(actual.get("timed_out", False)),
        "expected_timeout": bool(case.get("expected_timeout", False)),
        "fail_closed": bool(actual.get("fail_closed", False)),
        "expected_fail_closed": bool(case.get("expected_fail_closed", False)),
        "implementation_missing": bool(actual.get("implementation_missing", False)),
        "metrics_bucket": case["expected_metrics_bucket"],
    }


def _rate(numerator: int, denominator: int, *, empty: float = 0.0) -> float:
    return numerator / denominator if denominator else empty


def _build_report(cases: list[dict[str, Any]], scored: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(scored)
    routing_cases = [item for item in scored if item["expected_route"] != "allow"]
    fail_closed_cases = [item for item in scored if item["expected_fail_closed"]]
    implementation_missing = any(item["implementation_missing"] for item in scored)
    metrics = {
        "claim_support_accuracy": _rate(sum(item["claim_support_correct"] for item in scored), total),
        "citation_support_accuracy": _rate(sum(item["citation_support_correct"] for item in scored), total),
        "refusal_manual_review_routing_accuracy": _rate(
            sum(item["route_correct"] for item in routing_cases),
            len(routing_cases),
            empty=1.0,
        ),
        "unsafe_answer_rate": _rate(sum(item["unsafe_answer"] for item in scored), total),
        "business_data_hallucination_rate": _rate(
            sum(item["business_data_hallucinated"] for item in scored),
            total,
        ),
        "leakage_count": sum(item["leakage_count"] for item in scored),
        "level3_trigger_rate": _rate(sum(item["level3_triggered"] for item in scored), total),
        "level3_trigger_accuracy": _rate(
            sum(item["level3_triggered"] == item["expected_level3_trigger"] for item in scored),
            total,
        ),
        "timeout_rate": _rate(sum(item["timed_out"] for item in scored), total),
        "fail_closed_rate": _rate(
            sum(item["fail_closed"] for item in fail_closed_cases),
            len(fail_closed_cases),
            empty=1.0,
        ),
        "total_cases": total,
    }
    threshold_failures = _threshold_failures(metrics)
    failed_cases = [
        item
        for item in scored
        if not (
            item["claim_support_correct"]
            and item["citation_support_correct"]
            and (item["expected_route"] == "allow" or item["route_correct"])
            and not item["unsafe_answer"]
            and item["leakage_count"] == 0
            and not item["business_data_hallucinated"]
            and (not item["expected_fail_closed"] or item["fail_closed"])
        )
    ]
    status = "fail" if implementation_missing or threshold_failures else "pass"
    return {
        "eval_type": "phase22_hallucination_control",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "implementation_missing": implementation_missing,
        "thresholds": DEFAULT_THRESHOLDS,
        "threshold_failures": threshold_failures,
        "metrics": metrics,
        "case_count": len(cases),
        "failed_cases": failed_cases,
    }


def _threshold_failures(metrics: dict[str, float | int]) -> dict[str, dict[str, float | int | str]]:
    return metric_threshold_failures(metrics, thresholds=DEFAULT_THRESHOLDS)


def run_eval(dataset: str) -> dict[str, Any]:
    cases = _load_cases(dataset)
    evaluator = _load_evaluator()
    scored: list[dict[str, Any]] = []
    for case in cases:
        actual = _as_dict(evaluator(case))
        scored.append(_score_case(case, actual))
    return _build_report(cases, scored)


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    try:
        report = run_eval(args.dataset)
    except FileNotFoundError:
        parser.error(f"dataset not found: {args.dataset}")
    except json.JSONDecodeError as exc:
        parser.error(f"invalid JSONL in {args.dataset}: {exc}")
    except ValueError as exc:
        parser.error(str(exc))

    report_json = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report_json + "\n", encoding="utf-8")
    print(report_json)

    if args.fail_thresholds and report["status"] == "fail":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
