from __future__ import annotations

import inspect

import pytest

from tests.agent.conftest import FakeLLM

from src.agent import routing as routing_module
from src.agent.intent_policy import (
    DIRECT_RESPONSE_INTENTS,
    EVIDENCE_REQUIRED_INTENTS,
    HIGH_RISK_INTENTS,
    INTENT_DEFINITIONS,
    INTENT_ROUTE_POLICY,
    ORDINARY_INTENTS,
    PRECEDENCE_INTENTS,
    RISK_POLICY_TABLE,
    REQUESTED_OPERATIONS,
    REQUIRED_SLOT_POLICY,
    arbitrate_intent,
    confidence_requires_clarification,
    decide_clarification,
    derive_keyword_signals,
    detect_pre_route,
    resolve_intent_precedence,
    resolve_risk_decision,
    resolve_risk_tier,
)
from src.agent.nodes import contextual_intent_resolve as contextual_intent_module
from src.agent.nodes.contextual_intent_resolve import intent_result_to_state
from src.agent.routing import (
    CONTEXTUAL_INTENT_ROUTES,
    SLOT_ROUTES,
    resolve_slots_with_metadata,
    route_after_contextual_intent,
    route_after_slot_resolution,
)
from src.agent.schemas import IntentResultV3, RequiredSlotExpression


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
    assert REQUIRED_SLOT_POLICY == {name: definition.required_slots for name, definition in INTENT_DEFINITIONS.items()}
    assert INTENT_ROUTE_POLICY == {name: definition.initial_route for name, definition in INTENT_DEFINITIONS.items()}
    assert PRECEDENCE_INTENTS == tuple(
        name for name, _definition in sorted(INTENT_DEFINITIONS.items(), key=lambda item: item[1].precedence)
    )
    assert DIRECT_RESPONSE_INTENTS == {
        name for name, definition in INTENT_DEFINITIONS.items() if definition.direct_response
    }
    assert EVIDENCE_REQUIRED_INTENTS == {
        name for name, definition in INTENT_DEFINITIONS.items() if definition.evidence_required
    }
    assert HIGH_RISK_INTENTS == {name for name, definition in INTENT_DEFINITIONS.items() if definition.high_risk}


def test_detect_pre_route_approval_chat_and_hard_negatives():
    decision = detect_pre_route("approve APR-1")
    assert decision.disposition == "approval_chat_not_trusted"
    assert decision.requested_operation == "advise"
    assert "approval_chat_not_trusted" in decision.reason_codes

    assert detect_pre_route("通过订单号 ORD-1 查询退款状态").disposition == "none"
    assert detect_pre_route("通过规则判断是否要补偿").disposition == "none"
    assert detect_pre_route("accept language preference").disposition == "none"


def test_derive_keyword_signals_only_emits_candidates_without_selecting_winner():
    signals = derive_keyword_signals("这个订单投诉升级，补偿方案给多少？")

    assert signals == ("complaint_escalation", "compensation_suggestion")
    assert "policy_qa" not in signals


def test_arbitrate_intent_allows_keyword_when_llm_lists_same_intent():
    primary, operation, reason_codes = arbitrate_intent(
        "policy_qa",
        ["complaint_escalation"],
        ("complaint_escalation",),
        0.95,
        "advise",
    )

    assert primary == "complaint_escalation"
    assert operation == "escalate"
    assert "intent_precedence_applied" in reason_codes


def test_arbitrate_intent_does_not_let_keywords_override_high_confidence_llm_primary():
    text = "这个不算投诉吧，我就是问下退款进度"
    primary, operation, reason_codes = arbitrate_intent(
        "refund_troubleshooting",
        [],
        derive_keyword_signals(text),
        0.95,
        "read_status",
        query=text,
    )

    assert primary == "refund_troubleshooting"
    assert operation == "read_status"
    assert reason_codes == []


def test_arbitrate_intent_allows_keyword_override_when_confidence_is_low():
    primary, operation, reason_codes = arbitrate_intent(
        "refund_troubleshooting",
        [],
        ("complaint_escalation",),
        0.4,
        "read_status",
    )

    assert primary == "complaint_escalation"
    assert operation == "escalate"
    assert "intent_precedence_applied" in reason_codes


def test_resolve_intent_precedence_exempts_registered_high_confidence_not_complaint_case():
    primary, operation, reason_codes = resolve_intent_precedence(
        "refund_troubleshooting",
        "read_status",
        "这个不算投诉吧，我就是问下退款进度",
        raw_confidence=0.95,
    )

    assert primary == "refund_troubleshooting"
    assert operation == "read_status"
    assert reason_codes == []


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


@pytest.mark.parametrize("text", ["补偿券使用规则是什么？", "补偿券规则是什么", "通过规则判断是否要补偿"])
def test_compensation_terms_in_policy_questions_do_not_force_action_intent(text):
    primary, operation, reason_codes = resolve_intent_precedence("policy_qa", "advise", text)

    assert primary == "policy_qa"
    assert operation == "advise"
    assert reason_codes == []


def test_secondary_compensation_intent_does_not_override_without_action_cue():
    primary, operation, reason_codes = resolve_intent_precedence(
        "refund_troubleshooting",
        "read_status",
        "",
        ["compensation_suggestion"],
    )

    assert primary == "refund_troubleshooting"
    assert operation == "read_status"
    assert reason_codes == []


def test_secondary_intents_participate_in_precedence_resolution():
    primary, operation, reason_codes = resolve_intent_precedence(
        "policy_qa",
        "advise",
        "帮我看看这个问题",
        ["complaint_escalation"],
    )

    assert primary == "complaint_escalation"
    assert operation == "escalate"
    assert "intent_precedence_applied" in reason_codes


def test_next_step_advice_is_not_forced_into_action_type_clarification():
    result = IntentResultV3.model_validate(
        {
            "schema_version": "intent_result.v3",
            "primary_intent": "action_request",
            "requested_operation": "advise",
            "confidence": 0.82,
            "calibrated_confidence": 0.82,
            "secondary_intents": ["order_status_inquiry"],
            "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
            "candidate_slots": {},
            "routing_hints": {"clarification_reason": "missing_order_reference"},
            "classifier_version": "intent_classifier.v2",
            "calibration_version": "calibration.unverified",
            "reason_codes": ["action_handling_question", "missing_context_reference"],
        }
    )

    update = intent_result_to_state(result, user_query="那这个订单下一步应该怎么处理？")

    assert update["primary_intent"] == "refund_troubleshooting"
    assert update["requested_operation"] == "read_status"
    assert update["required_slots"] == {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []}
    eval_metadata = update["llm_outputs"]["contextual_intent_resolve"]["eval_metadata"]
    assert "next_step_advice_normalized" in eval_metadata["reason_codes"]
    assert route_after_contextual_intent(update) == "slot_resolution_gate"
    assert route_after_contextual_intent(update) == "slot_resolution_gate"


def test_confidence_defaults_for_low_and_safety_sensitive_routes():
    assert confidence_requires_clarification("policy_qa", "advise", 0.6)
    assert confidence_requires_clarification("compensation_suggestion", "execute_action", 0.8)
    assert not confidence_requires_clarification("policy_qa", "advise", 0.8)


@pytest.mark.parametrize(
    ("primary_intent", "requested_operation", "routing_hints", "expected"),
    [
        ("refund_troubleshooting", "read_status", {}, "read_only"),
        ("refund_troubleshooting", "draft_reply", {}, "draft_only"),
        ("compensation_suggestion", "draft_action", {}, "suggest_action"),
        ("complaint_escalation", "escalate", {}, "approval_required"),
        (
            "unsupported",
            "advise",
            {"pre_route_disposition": "approval_chat_not_trusted"},
            "forbidden_in_chat",
        ),
    ],
)
def test_resolve_risk_tier(primary_intent, requested_operation, routing_hints, expected):
    assert resolve_risk_tier(primary_intent, requested_operation, channel="ordinary_chat", routing_hints=routing_hints) == expected


def _legacy_resolve_risk_tier(
    primary_intent: str,
    requested_operation: str,
    channel: str | None,
    routing_hints: dict | None,
) -> str:
    hints = routing_hints or {}
    if (
        requested_operation == "approval_decision"
        or hints.get("pre_route_disposition") == "approval_chat_not_trusted"
        or hints.get("clarification_reason") == "approval_chat_not_trusted"
    ):
        return "forbidden_in_chat"
    if requested_operation == "read_status":
        return "read_only"
    if requested_operation == "draft_reply":
        return "draft_only"
    if requested_operation == "draft_action" or primary_intent == "compensation_suggestion":
        return "suggest_action"
    if requested_operation in {"execute_action", "escalate"}:
        return "approval_required"
    if primary_intent in HIGH_RISK_INTENTS or primary_intent == "action_request":
        return "approval_required"
    return "read_only"


@pytest.mark.parametrize("primary_intent", [*ORDINARY_INTENTS, "not_a_real_intent"])
@pytest.mark.parametrize("requested_operation", [*REQUESTED_OPERATIONS, "approval_decision", "not_a_real_operation"])
@pytest.mark.parametrize("channel", ["ordinary_chat", "external_workflow", None])
@pytest.mark.parametrize(
    "routing_hints",
    [
        {},
        {"pre_route_disposition": "approval_chat_not_trusted"},
        {"clarification_reason": "approval_chat_not_trusted"},
        {"channel": "agent_runs"},
    ],
)
def test_risk_policy_table_preserves_legacy_tier_for_all_intent_operation_channel_combinations(
    primary_intent,
    requested_operation,
    channel,
    routing_hints,
):
    assert resolve_risk_tier(primary_intent, requested_operation, channel=channel, routing_hints=routing_hints) == (
        _legacy_resolve_risk_tier(primary_intent, requested_operation, channel, routing_hints)
    )


RISK_POLICY_ROW_CASES = {
    ("approval_decision", "*", "*"): ("unsupported", "approval_decision", "ordinary_chat", {}),
    ("read_status", "*", "*"): ("complaint_escalation", "read_status", "ordinary_chat", {}),
    ("draft_reply", "*", "*"): ("policy_qa", "draft_reply", "ordinary_chat", {}),
    ("draft_action", "*", "*"): ("policy_qa", "draft_action", "ordinary_chat", {}),
    ("execute_action", "*", "ordinary_chat"): ("policy_qa", "execute_action", "ordinary_chat", {}),
    ("execute_action", "*", "non_chat"): ("policy_qa", "execute_action", "external_workflow", {}),
    ("escalate", "*", "ordinary_chat"): ("policy_qa", "escalate", "ordinary_chat", {}),
    ("escalate", "*", "non_chat"): ("policy_qa", "escalate", "external_workflow", {}),
    ("*", "compensation_suggestion", "*"): ("compensation_suggestion", "advise", "ordinary_chat", {}),
    ("*", "action_request", "*"): ("action_request", "advise", "ordinary_chat", {}),
    ("*", "high_risk", "*"): ("appeal_or_unban", "advise", "ordinary_chat", {}),
    ("*", "direct_response", "*"): ("small_talk", "advise", "ordinary_chat", {}),
    ("*", "*", "*"): ("policy_qa", "advise", "ordinary_chat", {}),
}


def test_risk_policy_table_rows_are_reachable_and_dead_branch_is_removed():
    assert set(RISK_POLICY_TABLE) == set(RISK_POLICY_ROW_CASES)

    for key, (primary_intent, requested_operation, channel, routing_hints) in RISK_POLICY_ROW_CASES.items():
        decision = resolve_risk_decision(
            primary_intent,
            requested_operation,
            channel=channel,
            routing_hints=routing_hints,
        )
        assert decision.tier == RISK_POLICY_TABLE[key].tier
        assert decision.reason_codes == RISK_POLICY_TABLE[key].reason_codes

    source = inspect.getsource(resolve_risk_decision) + inspect.getsource(resolve_risk_tier)
    assert 'if effective_channel in ORDINARY_CHAT_CHANNELS else "approval_required"' not in source
    assert resolve_risk_tier("policy_qa", "execute_action", channel="ordinary_chat") == "approval_required"
    assert resolve_risk_tier("policy_qa", "execute_action", channel="external_workflow") == "approval_required"


@pytest.mark.parametrize(
    ("primary_intent", "requested_operation", "confidence", "expected", "threshold"),
    [
        ("policy_qa", "advise", 0.64, True, 0.65),
        ("policy_qa", "advise", 0.65, False, 0.65),
        ("compensation_suggestion", "draft_action", 0.84, True, 0.85),
        ("compensation_suggestion", "draft_action", 0.85, False, 0.85),
    ],
)
def test_clarification_layer_preserves_threshold_boundaries(
    primary_intent,
    requested_operation,
    confidence,
    expected,
    threshold,
):
    decision = decide_clarification(
        primary_intent,
        requested_operation,
        confidence,
        calibrated_confidence=0.0,
    )

    assert decision.requires_clarification is expected
    assert decision.threshold_applied == threshold
    assert confidence_requires_clarification(primary_intent, requested_operation, confidence) is expected


def test_clarification_layer_exposes_pre_route_decision_without_threshold():
    pre_route = detect_pre_route("approve APR-1")
    decision = decide_clarification("policy_qa", "advise", 0.99, pre_route)

    assert decision.requires_clarification is True
    assert decision.reason == "approval_chat_not_trusted"
    assert decision.threshold_applied is None


def test_intent_layers_keep_risk_and_clarification_signatures_downstream_only():
    for func in (resolve_risk_decision, decide_clarification):
        params = set(inspect.signature(func).parameters)
        assert "query" not in params
        assert "keyword_signals" not in params


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
    monkeypatch.setattr(contextual_intent_module, "_get_llm", lambda: FakeLLM(payload))

    update = await contextual_intent_module.contextual_intent_resolve({**base_state, "user_query": "approve APR-1"})

    assert update["routing_hints"]["pre_route_disposition"] == "approval_chat_not_trusted"
    assert update["routing_hints"]["clarification_reason"] == "approval_chat_not_trusted"
    assert update["requested_operation"] == "advise"
    assert update["risk_tier"] == "forbidden_in_chat"
    assert update["classification_trace"]["raw_llm_classification"]["primary_intent"] == "policy_qa"
    assert update["classification_trace"]["effective_classification"]["primary_intent"] == "unsupported"
    assert update["classification_trace"]["route_decision"] == "clarification_gate"
    assert "approval_result" not in update
    assert route_after_contextual_intent(update) == "clarification_gate"


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
    assert update["risk_tier"] == "approval_required"
    assert update["classification_trace"]["effective_classification"]["primary_intent"] == "action_request"
    assert update["required_slots"]["all_of"] == ["action_type"]
    assert route_after_slot_resolution({**update, "extracted_slots": {"order_id": "ORD-7001"}}) == "clarification_gate"


def test_safety_sensitive_escalation_pre_route_forces_complaint_escalation_policy():
    result = IntentResultV3.model_validate(
        {
            "schema_version": "intent_result.v3",
            "primary_intent": "policy_qa",
            "requested_operation": "read_status",
            "confidence": 0.97,
            "calibrated_confidence": 0.94,
            "secondary_intents": [],
            "required_slots": {"all_of": [], "any_of": [], "optional": []},
            "candidate_slots": {"ticket_id": "TKT-6001"},
            "routing_hints": {},
            "classifier_version": "intent_classifier.v2",
            "calibration_version": "calibration.unverified",
            "reason_codes": ["llm_misclassified_escalation"],
        }
    )
    pre_route = detect_pre_route("TKT-6001要不要转主管")

    update = intent_result_to_state(result, pre_route=pre_route, user_query="TKT-6001要不要转主管")

    assert update["primary_intent"] == "complaint_escalation"
    assert update["requested_operation"] == "escalate"
    assert update["risk_tier"] == "approval_required"
    assert update["required_slots"]["any_of"] == [["ticket_id", "order_id", "merchant_id"]]
    assert route_after_contextual_intent(update) == "slot_resolution_gate"
    assert route_after_contextual_intent(update) == "slot_resolution_gate"


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
def test_route_after_contextual_intent_totality(state):
    assert route_after_contextual_intent(state) in CONTEXTUAL_INTENT_ROUTES


def test_route_after_contextual_intent_consumes_registry_route_policy(monkeypatch):
    class FakeIntentRegistry:
        def is_direct_response_intent(self, intent: str) -> bool:
            return False

        def route_for_intent(self, intent: str) -> str | None:
            return "investigate"

    class FakeSlotRegistry:
        def required_slots_for(self, intent: str) -> RequiredSlotExpression:
            return RequiredSlotExpression()

    monkeypatch.setattr(routing_module, "INTENT_POLICY_REGISTRY", FakeIntentRegistry(), raising=False)
    monkeypatch.setattr(routing_module, "SLOT_POLICY_REGISTRY", FakeSlotRegistry(), raising=False)

    assert (
        routing_module.route_after_contextual_intent(
            {"primary_intent": "refund_troubleshooting", "requested_operation": "read_status", "intent_confidence": 0.9}
        )
        == "investigate"
    )


@pytest.mark.parametrize("route_value", ["not_a_route", None])
def test_route_after_contextual_intent_fails_closed_for_invalid_registry_route(monkeypatch, route_value):
    class FakeIntentRegistry:
        def is_direct_response_intent(self, intent: str) -> bool:
            return False

        def route_for_intent(self, intent: str) -> str | None:
            return route_value

    class FakeSlotRegistry:
        def required_slots_for(self, intent: str) -> RequiredSlotExpression:
            return RequiredSlotExpression()

    monkeypatch.setattr(routing_module, "INTENT_POLICY_REGISTRY", FakeIntentRegistry(), raising=False)
    monkeypatch.setattr(routing_module, "SLOT_POLICY_REGISTRY", FakeSlotRegistry(), raising=False)

    assert (
        routing_module.route_after_contextual_intent(
            {"primary_intent": "refund_troubleshooting", "requested_operation": "read_status", "intent_confidence": 0.9}
        )
        == "clarification_gate"
    )


def test_route_after_contextual_intent_fails_closed_for_registry_exception(monkeypatch):
    class RaisingIntentRegistry:
        def is_direct_response_intent(self, intent: str) -> bool:
            raise RuntimeError("registry unavailable")

    monkeypatch.setattr(routing_module, "INTENT_POLICY_REGISTRY", RaisingIntentRegistry(), raising=False)

    assert (
        routing_module.route_after_contextual_intent(
            {"primary_intent": "refund_troubleshooting", "requested_operation": "read_status", "intent_confidence": 0.9}
        )
        == "clarification_gate"
    )


def test_intent_consumers_do_not_read_policy_constants_directly():
    routing_source = inspect.getsource(routing_module)
    contextual_intent_source = inspect.getsource(contextual_intent_module)

    forbidden = ("DIRECT_RESPONSE_INTENTS", "INTENT_ROUTE_POLICY", "REQUIRED_SLOT_POLICY")
    for token in forbidden:
        assert token not in routing_source
        assert token not in contextual_intent_source


def test_route_after_slot_resolution_totality_and_legacy_memory_hint_route():
    assert route_after_slot_resolution({}) in SLOT_ROUTES
    assert (
        route_after_slot_resolution(
            {
                "primary_intent": "policy_qa",
                "required_slots": {"all_of": [], "any_of": [], "optional": []},
                "extracted_slots": {},
                "routing_hints": {"needs_long_term_memory": True},
            }
        )
        == "memory_context_load"
    )


def test_route_after_slot_resolution_accepts_canonical_reviewed_memory_hint_and_preserves_slot_gate():
    assert (
        route_after_slot_resolution(
            {
                "primary_intent": "policy_qa",
                "required_slots": {"all_of": [], "any_of": [], "optional": []},
                "extracted_slots": {},
                "routing_hints": {"needs_reviewed_memory_context": True},
            }
        )
        == "memory_context_load"
    )
    assert (
        route_after_slot_resolution(
            {
                "primary_intent": "refund_troubleshooting",
                "extracted_slots": {},
                "routing_hints": {"needs_reviewed_memory_context": True},
            }
        )
        == "clarification_gate"
    )


def _trusted_slot_metadata() -> dict:
    return {
        "source": "trusted_session_memory",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "fresh": True,
        "intent_compatible": True,
    }


def test_resolve_slots_prefers_canonical_session_context_over_legacy_session_memory():
    resolved, metadata = resolve_slots_with_metadata(
        {
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": "thread-1",
            "primary_intent": "refund_troubleshooting",
            "extracted_slots": {},
            "session_context": {
                "schema_version": "session_context_memory.v1",
                "authority_class": "contextual_only",
                "continuity_claimed": True,
                "active_slots": {"order_id": "ORD-CANONICAL"},
                "slot_metadata": {"order_id": _trusted_slot_metadata()},
            },
            "session_memory": {
                "continuity_claimed": True,
                "active_slots": {"order_id": "ORD-LEGACY"},
                "slot_metadata": {"order_id": _trusted_slot_metadata()},
            },
        }
    )

    assert resolved["order_id"] == "ORD-CANONICAL"
    assert metadata["order_id"]["source"] == "trusted_session_memory"


def test_resolve_slots_keeps_legacy_session_memory_fallback_when_canonical_context_absent():
    resolved, _metadata = resolve_slots_with_metadata(
        {
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": "thread-1",
            "primary_intent": "refund_troubleshooting",
            "extracted_slots": {},
            "session_memory": {
                "continuity_claimed": True,
                "active_slots": {"order_id": "ORD-LEGACY"},
                "slot_metadata": {"order_id": _trusted_slot_metadata()},
            },
        }
    )

    assert resolved["order_id"] == "ORD-LEGACY"
