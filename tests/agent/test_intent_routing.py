from __future__ import annotations

import pytest

from tests.agent.conftest import FakeLLM

from src.agent.intent_policy import (
    DIRECT_RESPONSE_INTENTS,
    EVIDENCE_REQUIRED_INTENTS,
    HIGH_RISK_INTENTS,
    INTENT_DEFINITIONS,
    INTENT_ROUTE_POLICY,
    ORDINARY_INTENTS,
    PRECEDENCE_INTENTS,
    REQUESTED_OPERATIONS,
    REQUIRED_SLOT_POLICY,
    confidence_requires_clarification,
    detect_pre_route,
    resolve_intent_precedence,
)
from src.agent.nodes import classify_intent as classify_intent_module
from src.agent.nodes.classify_intent import intent_result_to_state
from src.agent.routing import INTENT_ROUTES, SLOT_ROUTES, route_after_intent, route_after_slots
from src.agent.schemas import IntentResultV3


def test_policy_taxonomy_has_no_generic_or_approval_decision_intents():
    assert "generic_qa" not in ORDINARY_INTENTS
    assert "support_qa" not in ORDINARY_INTENTS
    assert "approval_request" not in ORDINARY_INTENTS
    assert "approval_decision" not in REQUESTED_OPERATIONS


def test_intent_policy_views_are_derived_from_definitions():
    assert all(name == definition.name for name, definition in INTENT_DEFINITIONS.items())
    assert len({definition.precedence for definition in INTENT_DEFINITIONS.values()}) == len(INTENT_DEFINITIONS)
    assert all(
        not definition.direct_response or definition.initial_route == "final_response"
        for definition in INTENT_DEFINITIONS.values()
    )
    assert ORDINARY_INTENTS == tuple(INTENT_DEFINITIONS)
    assert REQUIRED_SLOT_POLICY == {
        name: definition.required_slots for name, definition in INTENT_DEFINITIONS.items()
    }
    assert INTENT_ROUTE_POLICY == {
        name: definition.initial_route for name, definition in INTENT_DEFINITIONS.items()
    }
    assert PRECEDENCE_INTENTS == tuple(
        name for name, _definition in sorted(INTENT_DEFINITIONS.items(), key=lambda item: item[1].precedence)
    )
    assert DIRECT_RESPONSE_INTENTS == {
        name for name, definition in INTENT_DEFINITIONS.items() if definition.direct_response
    }
    assert EVIDENCE_REQUIRED_INTENTS == {
        name for name, definition in INTENT_DEFINITIONS.items() if definition.evidence_required
    }
    assert HIGH_RISK_INTENTS == {
        name for name, definition in INTENT_DEFINITIONS.items() if definition.high_risk
    }


def test_detect_pre_route_approval_chat_and_hard_negatives():
    decision = detect_pre_route("approve APR-1")
    assert decision.disposition == "approval_chat_not_trusted"
    assert decision.requested_operation == "advise"
    assert "approval_chat_not_trusted" in decision.reason_codes

    assert detect_pre_route("通过订单号 ORD-1 查询退款状态").disposition == "none"
    assert detect_pre_route("通过规则判断是否要补偿").disposition == "none"
    assert detect_pre_route("accept language preference").disposition == "none"


@pytest.mark.parametrize(
    ("text", "expected_intent", "expected_operation"),
    [
        ("商家申诉解封，需要处理", "appeal_or_unban", "escalate"),
        ("客户投诉很严重，请升级", "complaint_escalation", "escalate"),
        ("这个订单要补偿券", "compensation_suggestion", "draft_action"),
    ],
)
def test_resolve_intent_precedence(text, expected_intent, expected_operation):
    primary, operation, reason_codes = resolve_intent_precedence("policy_qa", "read_status", text)
    assert primary == expected_intent
    assert operation == expected_operation
    assert "intent_precedence_applied" in reason_codes


def test_confidence_defaults_for_low_and_safety_sensitive_routes():
    assert confidence_requires_clarification("policy_qa", "advise", 0.6)
    assert confidence_requires_clarification("compensation_suggestion", "execute_action", 0.8)
    assert not confidence_requires_clarification("policy_qa", "advise", 0.8)


@pytest.mark.asyncio
async def test_classifier_pre_route_wiring_for_approval_chat(monkeypatch, base_state):
    payload = {
        "schema_version": "intent_result.v3",
        "primary_intent": "policy_qa",
        "requested_operation": "read_status",
        "confidence": 0.98,
        "calibrated_confidence": 0.97,
        "secondary_intents": [],
        "required_slots": {"all_of": [], "any_of": [], "optional": []},
        "candidate_slots": {},
        "routing_hints": {},
        "classifier_version": "intent_classifier.v2",
        "calibration_version": "calibration.unverified",
        "reason_codes": ["llm_read_only"],
    }
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: FakeLLM(payload))

    update = await classify_intent_module.classify_intent({**base_state, "user_query": "approve APR-1"})

    assert update["routing_hints"]["pre_route_disposition"] == "approval_chat_not_trusted"
    assert update["routing_hints"]["clarification_reason"] == "approval_chat_not_trusted"
    assert update["requested_operation"] == "advise"
    assert "approval_result" not in update
    assert route_after_intent(update) == "clarification_gate"


@pytest.mark.parametrize("llm_intent", ["policy_qa", "refund_troubleshooting"])
def test_safety_sensitive_pre_route_forces_action_request_policy(llm_intent):
    result = IntentResultV3.model_validate(
        {
            "schema_version": "intent_result.v3",
            "primary_intent": llm_intent,
            "requested_operation": "advise",
            "confidence": 0.97,
            "calibrated_confidence": 0.94,
            "secondary_intents": [],
            "required_slots": {"all_of": [], "any_of": [], "optional": []},
            "candidate_slots": {"order_id": "ORD-7001"},
            "routing_hints": {},
            "classifier_version": "intent_classifier.v2",
            "calibration_version": "calibration.unverified",
            "reason_codes": ["llm_misclassified_write"],
        }
    )
    pre_route = detect_pre_route("请对ORD-7001直接退款")

    update = intent_result_to_state(result, pre_route=pre_route, user_query="请对ORD-7001直接退款")

    assert update["primary_intent"] == "action_request"
    assert update["requested_operation"] == "execute_action"
    assert update["required_slots"]["all_of"] == ["action_type"]
    assert route_after_slots({**update, "extracted_slots": {"order_id": "ORD-7001"}}) == "clarification_gate"


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"primary_intent": "small_talk", "requested_operation": "advise", "intent_confidence": 0.9},
        {"primary_intent": "unsupported", "requested_operation": "advise", "intent_confidence": 0.9},
        {"primary_intent": "policy_qa", "requested_operation": "advise", "intent_confidence": 0.9},
        {"primary_intent": "refund_troubleshooting", "requested_operation": "read_status", "intent_confidence": 0.9},
        {"routing_hints": {"pre_route_disposition": "approval_chat_not_trusted"}},
    ],
)
def test_route_after_intent_totality(state):
    assert route_after_intent(state) in INTENT_ROUTES


def test_route_after_slots_totality_and_long_term_memory_route():
    assert route_after_slots({}) in SLOT_ROUTES
    assert (
        route_after_slots(
            {
                "primary_intent": "policy_qa",
                "required_slots": {"all_of": [], "any_of": [], "optional": []},
                "extracted_slots": {},
                "routing_hints": {"needs_long_term_memory": True},
            }
        )
        == "long_term_memory_retrieve"
    )
