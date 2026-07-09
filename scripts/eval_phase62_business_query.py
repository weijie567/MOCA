"""Validate the Phase 62 business-query golden set.

Usage:
    uv run python scripts/eval_phase62_business_query.py
    uv run python scripts/eval_phase62_business_query.py --golden-set evaluation/golden/phase62_business_query_cases.jsonl

This script is deterministic. It validates fixture coverage and payload
expectations only; it does not call a live LLM or execute the agent graph.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_GOLDEN_SET = Path("evaluation/golden/phase62_business_query_cases.jsonl")
DEFAULT_OUTPUT = Path("evaluation/reports/phase62_business_query_eval.json")

ALLOWED_RESPONSE_KINDS = frozenset({"business_query_answer", "metric_answer", "clarification", "unsupported"})
ALLOWED_OPERATIONS = frozenset({"aggregate", "list", "detail", "breakdown", "compare"})
ALLOWED_TOOLS = frozenset({"business_query", "query_business_metric"})
REQUIRED_CATEGORIES = frozenset(
    {
        "aggregate_order_this_week",
        "aggregate_to_list_drilldown_order_no",
        "unauthorized_merchant_list_no_leak",
        "unauthorized_order_detail_no_leak",
        "breakdown_order_by_status",
        "compare_order_count_previous_period",
        "projection_bounds_no_raw_rows",
        "missing_business_query_time_range",
        "unsupported_business_query_boundary",
    }
)
REQUIRED_DRILLDOWN_SEQUENCE = ("本周多少订单？", "订单号是多少？")
NO_LEAK_TEXT = "当前权限范围内无法提供该业务数据"
NO_LEAK_CATEGORIES = frozenset({"unauthorized_merchant_list_no_leak", "unauthorized_order_detail_no_leak"})
RAW_PAYLOAD_KEYS = frozenset(
    {
        "raw",
        "raw_rows",
        "raw_args",
        "raw_payload",
        "raw_cursor",
        "raw_filters",
        "tenant_id",
        "merchant_scope",
        "prompt_payload",
        "tool_args",
        "routing_hints",
        "stack_trace",
        "sql",
    }
)


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

    drilldown_cases = [case for case in cases if case.get("category") == "aggregate_to_list_drilldown_order_no"]
    if not drilldown_cases:
        errors.append("missing aggregate_to_list_drilldown_order_no drilldown case")
    else:
        errors.extend(_validate_drilldown_case(drilldown_cases[0]))

    for category in sorted(NO_LEAK_CATEGORIES):
        if not any(case.get("category") == category for case in cases):
            errors.append(f"missing no-existence-leak category: {category}")

    for index, case in enumerate(cases, start=1):
        errors.extend(_validate_case(index, case))

    return errors


def _validate_case(index: int, case: dict[str, Any]) -> list[str]:
    prefix = f"{case.get('id') or index}:"
    errors: list[str] = []

    for field in ("id", "category", "role", "expected_response_kind", "expected_route"):
        if not case.get(field):
            errors.append(f"{prefix} missing {field}")
    if not case.get("prompt") and not case.get("turns"):
        errors.append(f"{prefix} missing prompt or turns")

    response_kind = case.get("expected_response_kind")
    if response_kind not in ALLOWED_RESPONSE_KINDS:
        errors.append(f"{prefix} invalid expected_response_kind {response_kind!r}")

    expected_response_kinds = _string_list(case.get("expected_response_kinds"))
    for kind in expected_response_kinds:
        if kind not in ALLOWED_RESPONSE_KINDS:
            errors.append(f"{prefix} invalid expected_response_kinds item {kind!r}")

    operations = _expected_operations(case)
    for operation in operations:
        if operation not in ALLOWED_OPERATIONS:
            errors.append(f"{prefix} invalid expected operation {operation!r}")

    tools = _expected_tools(case)
    for tool in tools:
        if tool not in ALLOWED_TOOLS:
            errors.append(f"{prefix} invalid expected tool {tool!r}")

    contains = _string_list(case.get("expected_response_contains"))
    if not contains:
        errors.append(f"{prefix} expected_response_contains must be non-empty")

    must_not_contain = _string_list(case.get("must_not_contain"))
    if not must_not_contain:
        errors.append(f"{prefix} must_not_contain must be non-empty")

    if response_kind == "business_query_answer":
        if not operations:
            errors.append(f"{prefix} business_query_answer must include expected operation")
        if not tools:
            errors.append(f"{prefix} business_query_answer must include expected tool")

    if case.get("category") in NO_LEAK_CATEGORIES:
        if case.get("expected_no_leak") is not True:
            errors.append(f"{prefix} no-existence-leak cases must set expected_no_leak=true")
        if NO_LEAK_TEXT not in contains:
            errors.append(f"{prefix} no-existence-leak case missing safe response text")
        if not _string_list(case.get("sensitive_terms")):
            errors.append(f"{prefix} no-existence-leak case must list sensitive_terms")

    raw_hits = _raw_payload_hits(case.get("expected_api_payload"))
    if raw_hits:
        errors.append(f"{prefix} raw payload expectation includes forbidden keys: {', '.join(sorted(raw_hits))}")

    return errors


def _validate_drilldown_case(case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    turns = _string_list(case.get("turns"))
    if tuple(turns) != REQUIRED_DRILLDOWN_SEQUENCE:
        errors.append("aggregate_to_list_drilldown_order_no must use required prompt sequence")
    if case.get("expected_operations") != ["aggregate", "list"]:
        errors.append("aggregate_to_list_drilldown_order_no must expect aggregate then list")
    if case.get("expected_tools") != ["query_business_metric", "business_query"]:
        errors.append("aggregate_to_list_drilldown_order_no must expect metric compatibility then business_query")
    if case.get("expected_drilldown_field") != "order_no":
        errors.append("aggregate_to_list_drilldown_order_no must expect order_no drilldown field")
    return errors


def _expected_operations(case: dict[str, Any]) -> list[str]:
    operations = _string_list(case.get("expected_operations"))
    operation = case.get("expected_operation")
    if isinstance(operation, str) and operation:
        operations.append(operation)
    return operations


def _expected_tools(case: dict[str, Any]) -> list[str]:
    tools = _string_list(case.get("expected_tools"))
    tool = case.get("expected_tool")
    if isinstance(tool, str) and tool:
        tools.append(tool)
    return tools


def _raw_payload_hits(value: Any) -> set[str]:
    hits: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if key_text in RAW_PAYLOAD_KEYS:
                hits.add(key_text)
            hits.update(_raw_payload_hits(nested))
    elif isinstance(value, list):
        for item in value:
            hits.update(_raw_payload_hits(item))
    return hits


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Phase 62 business-query golden coverage")
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
        "response_kinds": sorted({str(case.get("expected_response_kind") or "") for case in cases}),
        "errors": errors,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Phase 62 business-query golden validation passed: {len(cases)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
