from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.agent.conftest import FakeLLM

from src.agent.nodes import classify_intent as classify_intent_module
from src.agent.nodes.classify_intent import intent_result_to_state
from src.agent.intent_policy import PreRouteDecision, RiskDecision
from src.agent.schemas import IntentResultV3, RequiredSlotExpression


def _intent_v3(**overrides):
    payload = {
        "schema_version": "intent_result.v3",
        "primary_intent": "refund_troubleshooting",
        "requested_operation": "read_status",
        "confidence": 0.95,
        "calibrated_confidence": 0.92,
        "secondary_intents": [],
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "candidate_slots": {"order_id": "ORD-001"},
        "routing_hints": {},
        "classifier_version": "intent_classifier.v2",
        "calibration_version": "calibration.unverified",
        "reason_codes": ["test"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_classify_intent_success(monkeypatch, base_state, fake_llm_intent):
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: fake_llm_intent)

    result = await classify_intent_module.classify_intent(base_state)

    assert result["current_intent"] == "refund_troubleshooting"
    assert result["primary_intent"] == "refund_troubleshooting"
    assert result["requested_operation"] == "read_status"
    assert result["intent_confidence"] == 0.95
    assert result["risk_tier"] == "read_only"
    assert result["classification_trace"]["raw_llm_classification"]["primary_intent"] == "refund_troubleshooting"
    assert result["classification_trace"]["candidate_classification"]["primary_intent"] == "refund_troubleshooting"
    assert result["classification_trace"]["policy_owner"] == "IntentPolicyRegistry"
    assert result["classification_trace"]["effective_classification"]["primary_intent"] == "refund_troubleshooting"
    assert result["classification_trace"]["route_decision"] == "session_memory_load"
    assert result["classification_trace"]["semantic_intent"]["intent"] == "refund_troubleshooting"
    assert result["classification_trace"]["semantic_intent"]["operation"] == "read_status"
    assert result["classification_trace"]["risk_decision"]["tier"] == "read_only"
    assert result["classification_trace"]["clarification_decision"]["threshold_applied"] == 0.65
    assert result["required_slots"]["any_of"] == [["order_id", "refund_case_id"]]
    assert result["task_plan"] == result["classification_trace"]["task_plan"]
    assert result["task_plan"]["steps"][0]["step_id"] == "s1"
    assert result["task_plan"]["steps"][0]["intent"] == "refund_troubleshooting"
    assert result["classification_trace"]["executable_prefix"] == ["s1"]
    assert result["classification_trace"]["deferred_steps"] == []
    assert result["classification_trace"]["plan_normalization"] == []
    assert result["deferred_steps"] == []
    assert (
        result["llm_outputs"]["intent_classification"]["classification_trace"]
        == result["classification_trace"]
    )


@pytest.mark.asyncio
async def test_classify_intent_llm_failure_returns_unknown(monkeypatch, base_state):
    monkeypatch.setattr(
        classify_intent_module,
        "_get_llm",
        lambda: FakeLLM(
            {"primary_intent": "not_valid", "confidence": 0.95, "approval_result": {"decision": "approve"}}
        ),
    )

    result = await classify_intent_module.classify_intent(base_state)

    assert result["current_intent"] == "unsupported"
    assert result["risk_tier"] == "read_only"
    assert result["classification_trace"]["raw_llm_classification"] is None
    assert result["classification_trace"]["effective_classification"]["primary_intent"] == "unsupported"
    assert "approval_result" not in result
    assert result["node_errors"]


def test_intent_result_v3_rejects_approval_result_extra_field():
    with pytest.raises(ValidationError):
        IntentResultV3.model_validate(_intent_v3(approval_result={"decision": "approve"}))


def test_intent_result_to_state_uses_slot_policy_registry_for_required_slots(monkeypatch):
    class FakeSlotRegistry:
        def required_slots_for(self, intent: str) -> RequiredSlotExpression:
            return RequiredSlotExpression(all_of=["ticket_id"])

    monkeypatch.setattr(classify_intent_module, "SLOT_POLICY_REGISTRY", FakeSlotRegistry(), raising=False)
    result = IntentResultV3.model_validate(_intent_v3(required_slots={"all_of": [], "any_of": [], "optional": []}))

    update = intent_result_to_state(result, user_query="订单 ORD-1 怎么处理？")

    assert update["required_slots"] == {"all_of": ["ticket_id"], "any_of": [], "optional": []}
    assert update["classification_trace"]["raw_llm_classification"]["required_slots"] == {
        "all_of": [],
        "any_of": [],
        "optional": [],
    }
    assert update["classification_trace"]["effective_classification"]["required_slots"] == {
        "all_of": ["ticket_id"],
        "any_of": [],
        "optional": [],
    }


def test_intent_result_to_state_uses_intent_policy_registry_for_precedence_and_risk(monkeypatch):
    class FakeIntentRegistry:
        def resolve_precedence(
            self,
            primary_intent: str,
            secondary_intents: list[str],
            requested_operation: str,
            *,
            query: str = "",
            raw_confidence: float | None = None,
        ) -> tuple[str, str, list[str]]:
            del raw_confidence
            return "small_talk", "advise", ["fake_registry_precedence"]

        def resolve_risk_decision(
            self,
            primary_intent: str,
            requested_operation: str,
            role: str | None = None,
            channel: str | None = None,
            routing_hints: dict | None = None,
        ) -> RiskDecision:
            del primary_intent, requested_operation, role, channel, routing_hints
            return RiskDecision(
                tier="draft_only",
                evidence_required=True,
                approval_required=False,
                reason_codes=("fake_registry_risk",),
            )

    monkeypatch.setattr(classify_intent_module, "INTENT_POLICY_REGISTRY", FakeIntentRegistry(), raising=False)
    result = IntentResultV3.model_validate(_intent_v3(primary_intent="refund_troubleshooting"))

    update = intent_result_to_state(result, user_query="hi")

    assert update["primary_intent"] == "small_talk"
    assert update["risk_tier"] == "draft_only"
    assert update["classification_trace"]["policy_owner"] == "IntentPolicyRegistry"
    assert "fake_registry_precedence" in update["classification_trace"]["reason_codes"]


def test_intent_result_to_state_serializes_task_plan_trace_and_state():
    result = IntentResultV3.model_validate(
        _intent_v3(
            primary_intent="order_status_inquiry",
            requested_operation="read_status",
            secondary_intents=["policy_qa"],
            candidate_slots={"order_id": "ORD-001"},
        )
    )

    update = intent_result_to_state(result, user_query="查订单状态，同时看政策")
    trace = update["classification_trace"]

    assert update["primary_intent"] == "order_status_inquiry"
    assert update["requested_operation"] == "read_status"
    assert trace["task_plan"] == update["task_plan"]
    assert [step["step_id"] for step in update["task_plan"]["steps"]] == ["s1", "s2"]
    assert update["task_plan"]["steps"][0]["intent"] == "order_status_inquiry"
    assert update["task_plan"]["steps"][1]["intent"] == "policy_qa"
    assert trace["executable_prefix"] == ["s1"]
    assert trace["deferred_steps"] == [update["task_plan"]["steps"][1]]
    assert update["deferred_steps"] == trace["deferred_steps"]
    assert trace["plan_normalization"] == []
    assert update["llm_outputs"]["intent_classification"]["classification_trace"] == trace


def test_multi_target_request_is_neutralized_only_after_valid_task_plan():
    result = IntentResultV3.model_validate(
        _intent_v3(
            primary_intent="order_status_inquiry",
            requested_operation="read_status",
            secondary_intents=["policy_qa"],
            candidate_slots={"order_id": "ORD-001"},
        )
    )
    pre_route = PreRouteDecision(
        disposition="multi_target_request",
        reason_codes=["multi_target_request"],
        requires_clarification=True,
    )

    update = intent_result_to_state(result, pre_route=pre_route, user_query="查订单状态，同时看政策")
    trace = update["classification_trace"]

    assert update["primary_intent"] == "order_status_inquiry"
    assert trace["pre_route_decision"]["disposition"] == "multi_target_request"
    assert trace["pre_route_decision"]["requires_clarification"] is True
    assert update["routing_hints"]["pre_route_disposition"] == "multi_target_request"
    assert "requires_clarification" not in update["routing_hints"]
    assert "clarification_reason" not in update["routing_hints"]
    assert trace["clarification_decision"]["requires_clarification"] is False
    assert trace["route_decision"] == "session_memory_load"
    assert trace["executable_prefix"] == ["s1"]
    assert [step["intent"] for step in update["deferred_steps"]] == ["policy_qa"]


def test_high_risk_secondary_step_is_deferred_not_executed():
    result = IntentResultV3.model_validate(
        _intent_v3(
            primary_intent="order_status_inquiry",
            requested_operation="read_status",
            secondary_intents=["action_request"],
            candidate_slots={"order_id": "ORD-001", "action_type": "refund"},
        )
    )

    update = intent_result_to_state(result, user_query="查订单状态，再处理退款")
    trace = update["classification_trace"]

    assert update["primary_intent"] == "order_status_inquiry"
    assert update["requested_operation"] == "read_status"
    assert trace["executable_prefix"] == ["s1"]
    assert update["deferred_steps"][0]["intent"] == "action_request"
    assert update["deferred_steps"][0]["operation"] == "execute_action"
    for forbidden_key in ("proposed_action", "action_draft", "approval_result", "action_result"):
        assert forbidden_key not in update


def test_non_read_only_s1_remains_effective_without_action_state():
    result = IntentResultV3.model_validate(
        _intent_v3(
            primary_intent="compensation_suggestion",
            requested_operation="draft_action",
            secondary_intents=["policy_qa"],
            candidate_slots={"order_id": "ORD-001", "action_type": "coupon"},
        )
    )

    update = intent_result_to_state(result, user_query="给补偿券，同时看政策")
    trace = update["classification_trace"]

    assert update["primary_intent"] == "compensation_suggestion"
    assert update["requested_operation"] == "draft_action"
    assert update["risk_tier"] == "suggest_action"
    assert trace["executable_prefix"] == []
    assert trace["deferred_steps"][0]["intent"] == "policy_qa"
    assert trace["effective_classification"]["primary_intent"] == "compensation_suggestion"
    for forbidden_key in ("proposed_action", "action_draft", "approval_result", "action_result"):
        assert forbidden_key not in update


def test_two_read_step_plan_keeps_second_read_deferred():
    result = IntentResultV3.model_validate(
        _intent_v3(
            primary_intent="order_status_inquiry",
            requested_operation="read_status",
            secondary_intents=["policy_qa"],
            candidate_slots={"order_id": "ORD-001"},
        )
    )

    update = intent_result_to_state(result, user_query="查订单状态，也看退款政策")
    trace = update["classification_trace"]

    assert update["primary_intent"] == "order_status_inquiry"
    assert trace["executable_prefix"] == ["s1"]
    assert trace["task_plan"]["steps"][1]["intent"] == "policy_qa"
    assert trace["task_plan"]["steps"][1]["operation"] == "read_status"
    assert update["deferred_steps"] == [trace["task_plan"]["steps"][1]]


@pytest.mark.asyncio
async def test_approval_chat_pre_route_overrides_llm(monkeypatch, base_state):
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: FakeLLM(_intent_v3(primary_intent="policy_qa")))

    result = await classify_intent_module.classify_intent({**base_state, "user_query": "approve APR-1"})

    assert result["current_intent"] == "unsupported"
    assert result["requested_operation"] == "advise"
    assert result["risk_tier"] == "forbidden_in_chat"
    assert result["classification_trace"]["raw_llm_classification"]["primary_intent"] == "policy_qa"
    assert result["classification_trace"]["effective_classification"]["primary_intent"] == "unsupported"
    assert result["routing_hints"]["pre_route_disposition"] == "approval_chat_not_trusted"
    assert result["routing_hints"]["clarification_reason"] == "approval_chat_not_trusted"
    assert "approval_result" not in result
    assert "resume" not in result


@pytest.mark.asyncio
async def test_safety_sensitive_pre_route_still_applies_existing_risk(monkeypatch, base_state):
    monkeypatch.setattr(
        classify_intent_module,
        "_get_llm",
        lambda: FakeLLM(
            _intent_v3(
                primary_intent="order_status_inquiry",
                requested_operation="read_status",
                candidate_slots={"order_id": "ORD-001", "action_type": "refund"},
            )
        ),
    )

    result = await classify_intent_module.classify_intent({**base_state, "user_query": "直接退款 ORD-001"})

    assert result["primary_intent"] == "action_request"
    assert result["requested_operation"] == "execute_action"
    assert result["risk_tier"] == "approval_required"
    assert result["routing_hints"]["pre_route_disposition"] == "safety_sensitive"
    assert result["classification_trace"]["pre_route_decision"]["disposition"] == "safety_sensitive"
    assert result["classification_trace"]["executable_prefix"] == []
    assert result["deferred_steps"] == []
    for forbidden_key in ("proposed_action", "action_draft", "approval_result", "action_result"):
        assert forbidden_key not in result


@pytest.mark.asyncio
async def test_pending_required_slot_identifier_reply_uses_active_flow_state(monkeypatch, base_state):
    def fail_llm():
        raise AssertionError("LLM should not be called for a pending slot identifier reply")

    monkeypatch.setattr(classify_intent_module, "_get_llm", fail_llm)
    state = {
        **base_state,
        "user_query": "OD-12345",
        "active_flow_state": {
            "kind": "pending_required_slot",
            "last_effective_intent": "refund_troubleshooting",
            "last_requested_operation": "read_status",
            "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
            "candidate_slots": {},
            "clarification_request_id": "clarify_run-001",
        },
    }

    result = await classify_intent_module.classify_intent(state)

    assert result["primary_intent"] == "refund_troubleshooting"
    assert result["requested_operation"] == "read_status"
    assert result["intent_confidence"] == 1.0
    assert result["risk_tier"] == "read_only"
    assert result["routing_hints"]["workflow_state_resolution"] == "answered_pending_required_slot"
    assert result["classification_trace"]["raw_llm_classification"] is None
    assert result["classification_trace"]["route_decision"] == "session_memory_load"
    assert result["classification_trace"]["policy_overrides"][0]["source"] == "active_flow_state"


@pytest.mark.asyncio
async def test_pending_required_slot_ambiguous_reply_reasks_for_slot(monkeypatch, base_state):
    def fail_llm():
        raise AssertionError("LLM should not be called for an ambiguous pending slot reply")

    monkeypatch.setattr(classify_intent_module, "_get_llm", fail_llm)
    state = {
        **base_state,
        "user_query": "继续吧",
        "active_flow_state": {
            "kind": "pending_required_slot",
            "last_effective_intent": "refund_troubleshooting",
            "last_requested_operation": "read_status",
            "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
            "candidate_slots": {},
            "clarification_request_id": "clarify_run-001",
        },
    }

    result = await classify_intent_module.classify_intent(state)

    assert result["primary_intent"] == "refund_troubleshooting"
    assert result["intent_confidence"] == 0.0
    assert result["routing_hints"]["workflow_state_resolution"] == "pending_required_slot_not_answered"
    assert result["routing_hints"]["clarification_reason"] == "missing_required_slots"
    assert result["classification_trace"]["route_decision"] == "clarification_gate"


@pytest.mark.asyncio
async def test_short_approval_reply_without_flow_is_not_classified_by_llm(monkeypatch, base_state):
    def fail_llm():
        raise AssertionError("LLM should not be called for a standalone approval-like short reply")

    monkeypatch.setattr(classify_intent_module, "_get_llm", fail_llm)

    result = await classify_intent_module.classify_intent({**base_state, "user_query": "同意"})

    assert result["primary_intent"] == "unsupported"
    assert result["requested_operation"] == "advise"
    assert result["risk_tier"] == "forbidden_in_chat"
    assert result["routing_hints"]["clarification_reason"] == "approval_chat_not_trusted"
    assert result["classification_trace"]["route_decision"] == "clarification_gate"
