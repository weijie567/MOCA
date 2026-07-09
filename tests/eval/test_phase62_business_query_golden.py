from __future__ import annotations

from pathlib import Path

from scripts.eval_phase62_business_query import REQUIRED_CATEGORIES, load_cases, validate_cases


DATASET = Path("evaluation/golden/phase62_business_query_cases.jsonl")
REQUIRED_DRILLDOWN_SEQUENCE = ["本周多少订单？", "订单号是多少？"]
REAL_BEHAVIOR_TESTS = {
    "aggregate_to_list_drilldown_order_no": (
        Path("tests/agent/test_graph.py"),
        "test_business_query_drilldown_followup_reuses_same_thread_answer_context",
    ),
    "unauthorized_merchant_list_no_leak": (
        Path("tests/test_agent_runs_api.py"),
        "test_phase62_business_query_api_payload_supports_no_leak_breakdown_and_compare",
    ),
    "unauthorized_order_detail_no_leak": (
        Path("tests/test_agent_runs_api.py"),
        "test_phase62_business_query_api_payload_supports_no_leak_breakdown_and_compare",
    ),
    "breakdown_order_by_status": (
        Path("tests/test_agent_runs_api.py"),
        "test_phase62_business_query_api_payload_supports_no_leak_breakdown_and_compare",
    ),
    "compare_order_count_previous_period": (
        Path("tests/test_agent_runs_api.py"),
        "test_phase62_business_query_api_payload_supports_no_leak_breakdown_and_compare",
    ),
}


def test_phase62_business_query_golden_validates_required_categories() -> None:
    cases = load_cases(DATASET)
    errors = validate_cases(cases)

    assert errors == []
    categories = {case["category"] for case in cases}
    assert REQUIRED_CATEGORIES <= categories
    assert "business_query_answer" in {case["expected_response_kind"] for case in cases}
    assert "clarification" in {case["expected_response_kind"] for case in cases}
    assert "unsupported" in {case["expected_response_kind"] for case in cases}


def test_phase62_business_query_golden_locks_drilldown_sequence_and_no_leak_flags() -> None:
    cases = load_cases(DATASET)
    drilldown = next(case for case in cases if case["category"] == "aggregate_to_list_drilldown_order_no")

    assert drilldown["turns"] == REQUIRED_DRILLDOWN_SEQUENCE
    assert drilldown["expected_operations"] == ["aggregate", "list"]
    assert drilldown["expected_tools"] == ["query_business_metric", "business_query"]

    no_leak_categories = {"unauthorized_merchant_list_no_leak", "unauthorized_order_detail_no_leak"}
    no_leak_cases = [case for case in cases if case["category"] in no_leak_categories]
    assert {case["category"] for case in no_leak_cases} == no_leak_categories
    for case in no_leak_cases:
        assert case.get("expected_no_leak") is True
        assert case.get("sensitive_terms")
        assert "当前权限范围内无法提供该业务数据" in case["expected_response_contains"]


def test_phase62_business_query_validator_rejects_raw_payload_and_missing_no_leak_assertions() -> None:
    valid_cases = load_cases(DATASET)
    raw_cases = [dict(case) for case in valid_cases]
    raw_cases[0]["expected_api_payload"] = {"raw_rows": [{"tenant_id": "TENANT-SHOULD-NOT-LEAK"}]}
    assert any("raw payload expectation" in error for error in validate_cases(raw_cases))

    no_leak_cases = [dict(case) for case in valid_cases]
    for case in no_leak_cases:
        if case["category"] == "unauthorized_order_detail_no_leak":
            case.pop("expected_no_leak", None)
            break
    assert any("expected_no_leak=true" in error for error in validate_cases(no_leak_cases))


def test_phase62_business_query_golden_cases_have_real_graph_or_api_backstops() -> None:
    for category, (path, test_name) in REAL_BEHAVIOR_TESTS.items():
        assert category in REQUIRED_CATEGORIES
        assert test_name in path.read_text(encoding="utf-8")
