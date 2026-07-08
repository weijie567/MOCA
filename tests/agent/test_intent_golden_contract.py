from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agent.nodes.contextual_intent_resolve import intent_result_to_state
from src.agent.intent_policy import detect_pre_route
from src.agent.routing import missing_required_slots, route_after_contextual_intent, route_after_slot_resolution
from src.agent.schemas import IntentResultV3


DATASET = Path("eval/intent/intent-golden.v1.json")


def _cases():
    return json.loads(DATASET.read_text())["cases"]


def _result(primary_intent: str, requested_operation: str = "advise") -> IntentResultV3:
    return IntentResultV3.model_validate(
        {
            "schema_version": "intent_result.v3",
            "primary_intent": primary_intent,
            "requested_operation": requested_operation,
            "confidence": 0.95,
            "calibrated_confidence": 0.93,
            "secondary_intents": [],
            "required_slots": {"all_of": [], "any_of": [], "optional": []},
            "candidate_slots": {},
            "routing_hints": {},
            "classifier_version": "intent_classifier.v2",
            "calibration_version": "calibration.unverified",
            "reason_codes": ["golden_contract"],
        }
    )


@pytest.mark.parametrize("case", [case for case in _cases() if case["kind"] == "positive"])
def test_positive_golden_cases_exercise_deterministic_helpers(case):
    expected = case["expected"]
    text = case["input"]
    pre_route = detect_pre_route(text)
    if "pre_route_disposition" in expected:
        assert pre_route.disposition == expected["pre_route_disposition"]
    if "primary_intent" in expected:
        update = intent_result_to_state(
            _result(expected["primary_intent"], expected.get("requested_operation", "advise")),
            pre_route=pre_route,
            user_query=text,
        )
        assert update["primary_intent"] == expected["primary_intent"]
        assert update["requested_operation"] == expected.get("requested_operation", update["requested_operation"])
        for key, value in expected.get("required_slots", {}).items():
            assert update["required_slots"][key] == value
        for forbidden in expected.get("forbidden", []):
            assert forbidden not in update
    if "route" in expected and expected["route"] == "clarification_gate":
        assert (
            route_after_contextual_intent(
                {
                    "primary_intent": expected.get("primary_intent", "unsupported"),
                    "requested_operation": expected.get("requested_operation", "advise"),
                    "intent_confidence": 0.95,
                    "routing_hints": {
                        "pre_route_disposition": expected.get("pre_route_disposition", "approval_chat_not_trusted")
                    },
                }
            )
            == "clarification_gate"
        )
    if "missing_required_slots" in expected:
        missing = missing_required_slots({"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []}, {})
        assert missing == expected["missing_required_slots"]
        assert (
            route_after_slot_resolution(
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
    expected = case["expected"]
    update = intent_result_to_state(
        _result(expected["classifier_primary_intent"], expected["requested_operation"]),
        pre_route=detect_pre_route(case["input"]),
        user_query=case["input"],
    )
    assert update["primary_intent"] != case["negative_for"]
    assert update["primary_intent"] != expected["not_primary_intent"]
