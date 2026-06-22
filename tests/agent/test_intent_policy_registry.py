from __future__ import annotations

import pytest

from src.agent.intent_policy import (
    DIRECT_RESPONSE_INTENTS,
    EVIDENCE_REQUIRED_INTENTS,
    HIGH_RISK_INTENTS,
    INTENT_DEFINITIONS,
    INTENT_ROUTE_POLICY,
    PRECEDENCE_INTENTS,
    REQUIRED_SLOT_POLICY,
    IntentPolicyRegistry,
    SlotPolicyRegistry,
    resolve_intent_precedence,
    resolve_risk_tier,
)
from src.agent.schemas import RequiredSlotExpression


def test_intent_policy_registry_mirrors_existing_constants() -> None:
    registry = IntentPolicyRegistry()

    assert registry.definitions() == INTENT_DEFINITIONS
    assert registry.intent_names() == tuple(INTENT_DEFINITIONS)
    assert registry.precedence_order() == PRECEDENCE_INTENTS
    assert registry.route_policy() == INTENT_ROUTE_POLICY
    assert registry.direct_response_intents() == frozenset(DIRECT_RESPONSE_INTENTS)
    assert registry.evidence_required_intents() == frozenset(EVIDENCE_REQUIRED_INTENTS)
    assert registry.high_risk_intents() == frozenset(HIGH_RISK_INTENTS)
    assert registry.definition_for("refund_troubleshooting") == INTENT_DEFINITIONS["refund_troubleshooting"]
    assert resolve_intent_precedence("policy_qa", "advise", "规则怎么说") == ("policy_qa", "advise", [])
    assert resolve_risk_tier("compensation_suggestion", "draft_action", channel="ordinary_chat") == "suggest_action"


def test_slot_policy_registry_mirrors_required_slot_policy() -> None:
    registry = SlotPolicyRegistry()

    assert registry.required_slot_policy() == REQUIRED_SLOT_POLICY
    assert registry.required_slots_for("refund_troubleshooting") == REQUIRED_SLOT_POLICY["refund_troubleshooting"]
    assert registry.required_slots_for("small_talk") == RequiredSlotExpression()


def test_registries_are_read_only() -> None:
    intent_registry = IntentPolicyRegistry()
    slot_registry = SlotPolicyRegistry()

    with pytest.raises(TypeError):
        intent_registry.definitions()["policy_qa"] = INTENT_DEFINITIONS["unsupported"]
    with pytest.raises(TypeError):
        intent_registry.route_policy()["policy_qa"] = "final_response"
    with pytest.raises(TypeError):
        slot_registry.required_slot_policy()["policy_qa"] = RequiredSlotExpression(all_of=["merchant_id"])

    assert INTENT_DEFINITIONS["policy_qa"].initial_route == "investigate"
    assert REQUIRED_SLOT_POLICY["policy_qa"] == RequiredSlotExpression()
