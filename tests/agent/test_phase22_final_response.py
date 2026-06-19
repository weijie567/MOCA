from __future__ import annotations

from typing import Any

import pytest

from src.agent.nodes.final_response import final_response


VERIFIER_TRACE = "SHOULD_NOT_LEAK_VERIFIER_TRACE"
RAW_PROVENANCE = "SHOULD_NOT_LEAK_RAW_PROVENANCE"
SOURCE_BLOCK_ID = "refund-policy:policy_pdf:text:source-block-private"
PRIVATE_REASONING = "SHOULD_NOT_LEAK_PRIVATE_REASONING"
INTERNAL_REASON_CODES = {
    "unsupported",
    "missing_citation",
    "conflicting_evidence",
    "stale_evidence",
    "unauthorized_evidence",
    "text_hash_mismatch",
    "latest_version_invalid",
    "ocr_low_confidence",
    "business_fact_missing",
    "semantic_ambiguous",
    "regenerate_route",
}


def _verification_state(
    *,
    outcome: str,
    route: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "overall_outcome": outcome,
        "allows_recommendation": False,
        "route": {
            "route": route,
            "selected_by": "backend",
            "model_selected": False,
            "decision_source": "phase22_verifier",
        },
        "reason_codes": reason_codes,
        "debug_trace": {
            "verifier_prompt": VERIFIER_TRACE,
            "raw_provenance": RAW_PROVENANCE,
            "source_block_id": SOURCE_BLOCK_ID,
            "private_reasoning": PRIVATE_REASONING,
        },
    }


def _state(base_state: dict[str, Any], *, outcome: str, route: str, reason_codes: list[str]) -> dict[str, Any]:
    return {
        **base_state,
        "rag_verification": _verification_state(outcome=outcome, route=route, reason_codes=reason_codes),
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Model proposed compensation, but verifier did not allow it.",
            "evidence_refs": [
                {
                    "doc_key": "policy_refund_timeout",
                    "chunk_id": "chunk_001",
                    "title": "Refund policy",
                    "section": "Compensation",
                }
            ],
            "confidence": 0.91,
            "risk_level": "high",
            "missing_info": [],
        },
        "business_context": {
            "order": {"order_no": "ORD-1001", "status": "delivered", "item_name": "测试商品"},
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "route", "reason_codes", "expected_status", "expected_phrase"),
    [
        ("unsupported", "regenerate_route", ["unsupported", "missing_citation"], "insufficient_evidence", "重新生成"),
        ("insufficient", "insufficient_evidence", ["missing_citation"], "insufficient_evidence", "没有找到足够证据"),
        ("conflicting", "manual_review", ["conflicting_evidence"], "manual_review", "人工复核"),
        ("stale", "manual_review", ["stale_evidence"], "manual_review", "人工复核"),
        ("unauthorized", "refuse", ["unauthorized_evidence"], "refused", "无法基于当前政策证据"),
        ("hash_mismatch", "refuse", ["text_hash_mismatch"], "refused", "无法基于当前政策证据"),
        ("latest_version_invalid", "refuse", ["latest_version_invalid"], "refused", "无法基于当前政策证据"),
        ("ocr_low_confidence", "manual_review", ["ocr_low_confidence"], "manual_review", "人工复核"),
        ("business_fact_missing", "insufficient_evidence", ["business_fact_missing"], "insufficient_evidence", "业务事实不足"),
        ("semantic_ambiguous", "manual_review", ["semantic_ambiguous"], "manual_review", "人工复核"),
    ],
)
async def test_final_response_renders_safe_non_allow_verifier_outcomes_without_internal_codes(
    base_state: dict[str, Any],
    outcome: str,
    route: str,
    reason_codes: list[str],
    expected_status: str,
    expected_phrase: str,
) -> None:
    """RTE-05: non-allow verifier routes get safe user wording and no debug leakage."""
    result = await final_response(
        _state(base_state, outcome=outcome, route=route, reason_codes=reason_codes)
    )

    response_text = result["final_response"]

    assert expected_phrase in response_text
    assert result["llm_outputs"]["final_response"]["final_status"] == expected_status
    assert result["llm_outputs"]["final_response"]["verification_route"] == route
    assert result["llm_outputs"]["final_response"]["route_selected_by"] == "backend"
    assert result["llm_outputs"]["final_response"]["model_selected_route"] is False
    for internal_code in INTERNAL_REASON_CODES:
        assert internal_code not in response_text
    for unsafe in (VERIFIER_TRACE, RAW_PROVENANCE, SOURCE_BLOCK_ID, PRIVATE_REASONING):
        assert unsafe not in response_text


@pytest.mark.asyncio
async def test_final_response_does_not_turn_manual_review_verification_into_action_success(
    base_state: dict[str, Any],
) -> None:
    """RTE-05: manual-review verifier state cannot be worded as approval, draft, or action success."""
    state = _state(
        base_state,
        outcome="conflicting",
        route="manual_review",
        reason_codes=["conflicting_evidence", "semantic_ambiguous"],
    )
    state.update(
        {
            "risk_assessment": {"approval_required": True, "risk_reason": "high risk"},
            "approval_result": {"decision": "approve"},
            "action_draft": {"draft_id": "draft-should-not-appear", "status": "draft_created"},
            "draft_outcome": {"status": "not_executed_demo", "draft_id": "draft-should-not-appear"},
        }
    )

    result = await final_response(state)

    assert "人工复核" in result["final_response"]
    assert "draft-should-not-appear" not in result["final_response"]
    assert "审批结果" not in result["final_response"]
    assert "草稿已创建" not in result["final_response"]
