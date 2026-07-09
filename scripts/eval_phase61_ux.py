"""Validate the Phase 61 UX and metric golden set.

Usage:
    uv run python scripts/eval_phase61_ux.py
    uv run python scripts/eval_phase61_ux.py --golden-set evaluation/golden/phase61_ux_cases.jsonl

This script is intentionally deterministic. It validates the regression-set
contract and writes a lightweight report; it does not call a live LLM.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_GOLDEN_SET = Path("evaluation/golden/phase61_ux_cases.jsonl")
DEFAULT_OUTPUT = Path("evaluation/reports/phase61_ux_eval.json")

ALLOWED_RESPONSE_KINDS = frozenset({"small_talk", "clarification", "unsupported", "metric_answer"})
ALLOWED_ROLES = frozenset({"support", "manager", "admin"})
REQUIRED_CATEGORIES = frozenset(
    {
        "small_talk_direct",
        "metric_missing_time_range",
        "missing_identifier_status",
        "today_refund_count",
        "weekly_coupon_count",
        "month_range_metric",
        "quarter_range_metric",
        "year_range_metric",
        "current_snapshot_pending_tickets",
        "merchant_refund_rate",
        "unauthorized_merchant_metric",
        "unsupported_metric",
    }
)
REQUIRED_PROMPTS = frozenset({"你好", "当前有多少订单"})
COUPON_CAVEAT_PARTS = ("MOCA 演示系统", "不是外部优惠券实际发放成功数")
NO_LEAK_TEXT = "当前权限范围内无法提供该商户指标"


def load_cases(path: str | Path = DEFAULT_GOLDEN_SET) -> list[dict[str, Any]]:
    dataset = Path(path)
    return [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_cases(cases: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not cases:
        return ["golden set is empty"]

    categories = {str(case.get("category") or "") for case in cases}
    missing_categories = sorted(REQUIRED_CATEGORIES - categories)
    if missing_categories:
        errors.append(f"missing categories: {', '.join(missing_categories)}")

    roles = {str(case.get("role") or "") for case in cases}
    missing_roles = sorted(ALLOWED_ROLES - roles)
    if missing_roles:
        errors.append(f"missing roles: {', '.join(missing_roles)}")

    prompts = {str(case.get("prompt") or "") for case in cases}
    missing_prompts = sorted(REQUIRED_PROMPTS - prompts)
    if missing_prompts:
        errors.append(f"missing prompts: {', '.join(missing_prompts)}")

    unauthorized_cases = [case for case in cases if case.get("category") == "unauthorized_merchant_metric"]
    if not unauthorized_cases:
        errors.append("missing unauthorized merchant metric case")

    coupon_cases = [case for case in cases if case.get("category") == "weekly_coupon_count"]
    if not coupon_cases:
        errors.append("missing weekly coupon count case")

    for index, case in enumerate(cases, start=1):
        errors.extend(_validate_case(index, case))

    return errors


def _validate_case(index: int, case: dict[str, Any]) -> list[str]:
    prefix = f"{case.get('id') or index}:"
    errors: list[str] = []

    for field in ("id", "category", "prompt", "role", "expected_response_kind", "expected_route"):
        if not case.get(field):
            errors.append(f"{prefix} missing {field}")

    if case.get("role") not in ALLOWED_ROLES:
        errors.append(f"{prefix} invalid role {case.get('role')!r}")

    response_kind = case.get("expected_response_kind")
    if response_kind not in ALLOWED_RESPONSE_KINDS:
        errors.append(f"{prefix} invalid expected_response_kind {response_kind!r}")

    contains = _string_list(case.get("expected_response_contains"))
    if not contains:
        errors.append(f"{prefix} expected_response_contains must be non-empty")

    must_not_contain = _string_list(case.get("must_not_contain"))
    if not must_not_contain:
        errors.append(f"{prefix} must_not_contain must be non-empty")

    if response_kind == "metric_answer":
        if case.get("expected_tool") != "query_business_metric":
            errors.append(f"{prefix} metric answers must expect query_business_metric")
        if not case.get("expected_metric_id"):
            errors.append(f"{prefix} metric answers must include expected_metric_id")

    if case.get("category") == "weekly_coupon_count":
        caveat = _string_list(case.get("expected_caveat_contains"))
        for part in COUPON_CAVEAT_PARTS:
            if part not in caveat:
                errors.append(f"{prefix} coupon case missing caveat part {part!r}")
        external_success_claims = ("外部优惠券实际发放成功", "已成功发券", "已发放到外部券系统")
        for phrase in external_success_claims:
            if phrase not in must_not_contain:
                errors.append(f"{prefix} coupon case must forbid {phrase!r}")

    if case.get("category") == "unauthorized_merchant_metric":
        if case.get("expected_no_leak") is not True:
            errors.append(f"{prefix} unauthorized metric must set expected_no_leak=true")
        if NO_LEAK_TEXT not in contains:
            errors.append(f"{prefix} unauthorized metric missing no-leak response text")
        if not _string_list(case.get("sensitive_terms")):
            errors.append(f"{prefix} unauthorized metric must list sensitive_terms")

    return errors


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Phase 61 UX golden coverage")
    parser.add_argument("--golden-set", default=str(DEFAULT_GOLDEN_SET), help="Path to JSONL golden set")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path to write JSON report")
    return parser


def main() -> int:
    args = _parser().parse_args()
    cases = load_cases(args.golden_set)
    errors = validate_cases(cases)
    report = {
        "success": not errors,
        "case_count": len(cases),
        "categories": sorted({str(case.get("category") or "") for case in cases}),
        "roles": sorted({str(case.get("role") or "") for case in cases}),
        "errors": errors,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Phase 61 UX golden validation passed: {len(cases)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
