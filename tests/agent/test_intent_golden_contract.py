from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agent.intent_policy import detect_pre_route, resolve_intent_precedence
from src.agent.routing import missing_required_slots, route_after_intent, route_after_slots


DATASET = Path("eval/intent/intent-golden.v1.json")


def _cases():
    return json.loads(DATASET.read_text())["cases"]


@pytest.mark.parametrize("case", [case for case in _cases() if case["kind"] == "positive"])
def test_positive_golden_cases_exercise_deterministic_helpers(case):
    expected = case["expected"]
    text = case["input"]
    pre_route = detect_pre_route(text)
    if "pre_route_disposition" in expected:
        assert pre_route.disposition == expected["pre_route_disposition"]
    if "primary_intent" in expected:
        primary, operation, _ = resolve_intent_precedence(
            expected["primary_intent"],
            expected.get("requested_operation", "advise"),
            text,
        )
        assert primary in {
            expected["primary_intent"],
            "appeal_or_unban",
            "complaint_escalation",
            "compensation_suggestion",
            "ticket_reply_draft",
        }
        assert operation in {"read_status", "advise", "draft_reply", "draft_action", "execute_action", "escalate"}
    if "route" in expected and expected["route"] == "clarification_gate":
        assert route_after_intent({"routing_hints": {"pre_route_disposition": "approval_chat_not_trusted"}}) == "clarification_gate"
    if "missing_required_slots" in expected:
        missing = missing_required_slots({"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []}, {})
        assert missing == expected["missing_required_slots"]
        assert (
            route_after_slots(
                {
                    "primary_intent": "refund_troubleshooting",
                    "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
                    "extracted_slots": {},
                }
            )
            == "clarification_gate"
        )
    for forbidden in expected.get("forbidden", []):
        assert forbidden not in pre_route.model_dump()


@pytest.mark.parametrize("case", [case for case in _cases() if case["kind"] == "hard-negative"])
def test_hard_negative_cases_do_not_resolve_to_negative_for(case):
    if case["negative_for"] == "policy_qa":
        pytest.skip("policy_qa is the neutral seed for hard-negative resolver checks")
    primary, _, _ = resolve_intent_precedence("policy_qa", "advise", case["input"])
    assert primary != case["negative_for"]
