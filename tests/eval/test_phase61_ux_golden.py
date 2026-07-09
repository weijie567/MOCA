from __future__ import annotations

from pathlib import Path

from scripts.eval_phase61_ux import REQUIRED_CATEGORIES, load_cases, validate_cases


DATASET = Path("evaluation/golden/phase61_ux_cases.jsonl")


def test_phase61_ux_golden_has_required_prompt_and_role_coverage() -> None:
    cases = load_cases(DATASET)
    errors = validate_cases(cases)

    assert errors == []
    categories = {case["category"] for case in cases}
    assert REQUIRED_CATEGORIES <= categories
    assert {"support", "manager", "admin"} <= {case["role"] for case in cases}
    prompts = {case["prompt"] for case in cases}
    assert "你好" in prompts
    assert "当前有多少订单" in prompts
    assert any("退款率" in prompt for prompt in prompts)


def test_phase61_ux_golden_locks_unauthorized_merchant_and_coupon_caveats() -> None:
    cases = load_cases(DATASET)
    unauthorized = [case for case in cases if case["category"] == "unauthorized_merchant_metric"]
    coupon = [case for case in cases if case["category"] == "weekly_coupon_count"]

    assert unauthorized, "must include an unauthorized merchant metric no-leak case"
    assert any(case.get("expected_no_leak") is True for case in unauthorized)
    for case in unauthorized:
        assert "当前权限范围内无法提供该商户指标" in case["expected_response_contains"]
        assert case.get("sensitive_terms")

    assert coupon, "must include coupon count cases"
    for case in coupon:
        caveat = case.get("expected_caveat_contains") or []
        assert "MOCA 演示系统" in caveat
        assert "不是外部优惠券实际发放成功数" in caveat
