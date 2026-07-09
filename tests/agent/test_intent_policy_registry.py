from __future__ import annotations

import pytest

from src.agent.intent_policy import (
    DIRECT_RESPONSE_INTENTS,
    EVIDENCE_REQUIRED_INTENTS,
    HIGH_RISK_INTENTS,
    INTENT_DEFINITIONS,
    INTENT_POLICY_REGISTRY,
    INTENT_ROUTE_POLICY,
    PRECEDENCE_INTENTS,
    REQUIRED_SLOT_POLICY,
    SLOT_POLICY_REGISTRY,
    IntentPolicyRegistry,
    SlotPolicyRegistry,
    resolve_intent_precedence,
    resolve_risk_tier,
)
from src.agent.prompts import CLASSIFY_INTENT_SYSTEM
from src.agent.schemas import RequiredSlotExpression


_FORBIDDEN_PER_METRIC_INTENTS = {
    "order_count_query",
    "refund_count_query",
    "refund_case_count_query",
    "pending_ticket_count_query",
    "coupon_record_count_query",
    "merchant_refund_rate_query",
}


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


def test_module_level_policy_registries_expose_effective_policy_api() -> None:
    assert isinstance(INTENT_POLICY_REGISTRY, IntentPolicyRegistry)
    assert isinstance(SLOT_POLICY_REGISTRY, SlotPolicyRegistry)

    assert INTENT_POLICY_REGISTRY.route_for_intent("policy_qa") == "investigate"
    assert INTENT_POLICY_REGISTRY.route_for_intent("small_talk") == "final_response"
    assert INTENT_POLICY_REGISTRY.route_for_intent("unknown_intent") is None
    assert INTENT_POLICY_REGISTRY.is_known_intent("refund_troubleshooting") is True
    assert INTENT_POLICY_REGISTRY.is_known_intent("unknown_intent") is False
    assert INTENT_POLICY_REGISTRY.is_direct_response_intent("small_talk") is True
    assert INTENT_POLICY_REGISTRY.is_direct_response_intent("refund_troubleshooting") is False
    assert INTENT_POLICY_REGISTRY.requires_evidence("policy_qa") is True
    assert INTENT_POLICY_REGISTRY.requires_evidence("small_talk") is False
    assert INTENT_POLICY_REGISTRY.is_high_risk_intent("action_request") is True
    assert INTENT_POLICY_REGISTRY.is_high_risk_intent("policy_qa") is False
    assert INTENT_POLICY_REGISTRY.is_critical_route_intent("appeal_or_unban") is True
    assert INTENT_POLICY_REGISTRY.is_critical_route_intent("critical_write") is True
    assert INTENT_POLICY_REGISTRY.is_critical_route_intent("policy_qa") is False


def test_business_metric_query_is_single_read_only_slot_resolution_intent() -> None:
    definition = INTENT_DEFINITIONS["business_metric_query"]

    assert definition.initial_route == "slot_resolution_gate"
    assert definition.evidence_required is False
    assert definition.high_risk is False
    assert definition.direct_response is False
    assert definition.required_slots.all_of == ["metric_id"]
    assert "business_metric_query" in INTENT_POLICY_REGISTRY.intent_names()
    assert "business_metric_query" not in DIRECT_RESPONSE_INTENTS
    assert "business_metric_query" not in EVIDENCE_REQUIRED_INTENTS
    assert "business_metric_query" not in HIGH_RISK_INTENTS
    assert resolve_risk_tier("business_metric_query", "read_status", channel="ordinary_chat") == "read_only"


def test_no_per_metric_intents_are_admitted() -> None:
    admitted = set(INTENT_POLICY_REGISTRY.intent_names())

    assert admitted.isdisjoint(_FORBIDDEN_PER_METRIC_INTENTS)


def test_classification_prompt_documents_generic_metric_examples() -> None:
    assert "- business_metric_query:" in CLASSIFY_INTENT_SYSTEM
    assert "\"primary_intent\":\"business_metric_query\"" in CLASSIFY_INTENT_SYSTEM
    for phrase in ("当前有多少订单", "今天有多少退款单", "待处理工单有多少", "本周补偿券发了多少", "某商家的退款率是多少"):
        assert phrase in CLASSIFY_INTENT_SYSTEM


def test_intent_policy_registry_resolves_precedence_and_risk_through_effective_api() -> None:
    registry = IntentPolicyRegistry()

    assert registry.resolve_precedence(
        "policy_qa",
        ["complaint_escalation"],
        "advise",
        query="需要投诉升级",
    ) == ("complaint_escalation", "escalate", ["intent_precedence_applied"])
    assert registry.resolve_precedence(
        "not_a_real_intent",
        [],
        "not_a_real_operation",
        query="unknown",
    ) == ("unsupported", "advise", ["unsupported_intent"])
    assert (
        registry.resolve_risk_tier("compensation_suggestion", "draft_action", channel="ordinary_chat")
        == "suggest_action"
    )
    assert registry.resolve_risk_tier("not_a_real_intent", "not_a_real_operation") == "read_only"


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
