from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.agent.conftest import FakeLLM

from src.agent.intent_policy import PreRouteDecision, RiskDecision
from src.agent.nodes import contextual_intent_resolve as contextual_intent_module
from src.agent.routing import route_after_contextual_intent
from src.agent.schemas import IntentResultV3, RequiredSlotExpression
from src.agent.state import business_query_context_binding


FORBIDDEN_AUTHORITY_FIELDS = {
    "extracted_slots",
    "active_slots",
    "tool_results",
    "approval_result",
    "trusted_approval_result",
    "risk_signals",
    "proposed_action",
    "action_result",
    "final_response",
    "resume",
    "command",
}

FORBIDDEN_DOWNSTREAM_FIELDS = FORBIDDEN_AUTHORITY_FIELDS | {
    "business_context",
    "case_memory",
    "case_memory_context",
    "long_term_memory",
    "long_term_memory_context",
    "memory_context",
    "rag_context",
    "retrieved_evidence",
    "evidence_refs",
}


def test_intent_legacy_wrapper_and_direct_test_are_removed():
    assert not Path("src", "agent", "nodes", "classify_intent.py").exists()
    assert not Path("tests", "agent", "test_nodes", "test_classify_intent.py").exists()
    legacy_import_path = "src.agent.nodes." + "classify_intent"
    assert legacy_import_path not in Path("tests/agent/test_intent_adapter.py").read_text()


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
async def test_contextual_intent_resolve_success_owns_canonical_trace_and_llm_output(
    monkeypatch,
    base_state,
    fake_llm_intent,
):
    monkeypatch.setattr(contextual_intent_module, "_get_llm", lambda: fake_llm_intent)

    result = await contextual_intent_module.contextual_intent_resolve(base_state)

    assert result["current_intent"] == "refund_troubleshooting"
    assert result["primary_intent"] == "refund_troubleshooting"
    assert result["requested_operation"] == "read_status"
    assert result["intent_confidence"] == 0.95
    assert result["risk_tier"] == "read_only"
    assert result["required_slots"]["any_of"] == [["order_id", "refund_case_id"]]
    assert result["candidate_slots"] == {"order_id": "ORD-001"}
    assert result["task_plan"]["steps"][0]["intent"] == "refund_troubleshooting"

    trace = result["classification_trace"]
    assert trace["raw_llm_classification"]["primary_intent"] == "refund_troubleshooting"
    assert trace["candidate_classification"]["primary_intent"] == "refund_troubleshooting"
    assert trace["policy_owner"] == "IntentPolicyRegistry"
    assert trace["effective_classification"]["primary_intent"] == "refund_troubleshooting"
    assert trace["route_decision"] == "slot_resolution_gate"
    assert trace["semantic_intent"]["intent"] == "refund_troubleshooting"
    assert trace["semantic_intent"]["operation"] == "read_status"
    assert trace["risk_decision"]["tier"] == "read_only"
    assert trace["clarification_decision"]["threshold_applied"] == 0.65
    assert result["task_plan"] == trace["task_plan"]
    assert result["task_plan"]["steps"][0]["step_id"] == "s1"
    assert trace["executable_prefix"] == ["s1"]
    assert trace["deferred_steps"] == []
    assert trace["plan_normalization"] == []
    assert result["deferred_steps"] == []
    assert "pre_route_decision" not in trace
    assert result["trace_steps"][-1]["node"] == "contextual_intent_resolve"
    assert result["llm_outputs"]["contextual_intent_resolve"]["classification_trace"] == trace
    assert route_after_contextual_intent(result) == "slot_resolution_gate"


@pytest.mark.asyncio
async def test_contextual_intent_resolve_llm_output_is_candidate_only(monkeypatch, base_state, fake_llm_intent):
    monkeypatch.setattr(contextual_intent_module, "_get_llm", lambda: fake_llm_intent)

    result = await contextual_intent_module.contextual_intent_resolve(base_state)

    for forbidden in FORBIDDEN_AUTHORITY_FIELDS:
        assert forbidden not in result
    assert result["candidate_slots"] == {"order_id": "ORD-001"}
    assert "extracted_slots" not in result["llm_outputs"]["contextual_intent_resolve"]


@pytest.mark.asyncio
async def test_contextual_intent_resolve_pending_slot_identifier_uses_same_thread_state_only(
    monkeypatch,
    base_state,
):
    def fail_llm():
        raise AssertionError("LLM should not be called for a pending slot identifier reply")

    monkeypatch.setattr(contextual_intent_module, "_get_llm", fail_llm)
    state = {
        **base_state,
        "user_query": "OD-12345",
        "session_context": {
            "continuity_claimed": True,
            "active_slots": {"order_id": "ORD-OLD"},
            "slot_metadata": {"order_id": {"source": "trusted_session_memory"}},
        },
        "active_flow_state": {
            "kind": "pending_required_slot",
            "last_effective_intent": "refund_troubleshooting",
            "last_requested_operation": "read_status",
            "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
            "candidate_slots": {},
            "clarification_request_id": "clarify_run-001",
        },
    }

    result = await contextual_intent_module.contextual_intent_resolve(state)

    assert result["primary_intent"] == "refund_troubleshooting"
    assert result["requested_operation"] == "read_status"
    assert result["intent_confidence"] == 1.0
    assert result["routing_hints"]["workflow_state_resolution"] == "answered_pending_required_slot"
    assert result["classification_trace"]["raw_llm_classification"] is None
    assert result["classification_trace"]["route_decision"] == "slot_resolution_gate"
    assert "pre_route_decision" not in result["classification_trace"]
    assert result["llm_outputs"]["contextual_intent_resolve"]["classification_trace"] == result["classification_trace"]
    assert result["trace_steps"][-1]["node"] == "contextual_intent_resolve"
    assert route_after_contextual_intent(result) == "slot_resolution_gate"
    for forbidden in FORBIDDEN_DOWNSTREAM_FIELDS:
        assert forbidden not in result


@pytest.mark.asyncio
async def test_contextual_intent_resolve_pending_metric_time_answer_uses_same_thread_flow(
    monkeypatch,
    base_state,
):
    def fail_llm():
        raise AssertionError("LLM should not be called for a pending metric time answer")

    monkeypatch.setattr(contextual_intent_module, "_get_llm", fail_llm)
    state = {
        **base_state,
        "user_query": "本周",
        "active_flow_state": {
            "kind": "pending_required_slot",
            "last_effective_intent": "business_metric_query",
            "last_requested_operation": "read_status",
            "required_slots": {"all_of": ["metric_id"], "any_of": [], "optional": []},
            "candidate_slots": {"metric_id": "order_count"},
            "resolved_slots": {"metric_id": "order_count", "resource_type": "order"},
            "clarification_request_id": "clarify_metric_run",
        },
    }

    result = await contextual_intent_module.contextual_intent_resolve(state)

    assert result["primary_intent"] == "business_metric_query"
    assert result["requested_operation"] == "read_status"
    assert result["intent_confidence"] == 1.0
    assert result["candidate_slots"] == {
        "metric_id": "order_count",
        "resource_type": "order",
        "metric_time_preset": "this_week",
    }
    assert result["routing_hints"]["workflow_state_resolution"] == "answered_pending_metric_time_range"
    assert result["routing_hints"]["metric_slot_parser"] == "active_flow_state"
    assert result["classification_trace"]["raw_llm_classification"] is None
    assert result["classification_trace"]["route_decision"] == "slot_resolution_gate"
    assert "active_flow_pending_metric_time_answered" in result["classification_trace"]["reason_codes"]
    assert route_after_contextual_intent(result) == "slot_resolution_gate"
    for forbidden in FORBIDDEN_DOWNSTREAM_FIELDS:
        assert forbidden not in result


@pytest.mark.asyncio
async def test_contextual_intent_resolve_business_query_drilldown_field_request_uses_last_answer_context(
    monkeypatch,
    base_state,
):
    def fail_llm():
        raise AssertionError("LLM should not be called for a safe business query drilldown reply")

    binding = business_query_context_binding(
        {
            **base_state,
            "thread_id": "thread-drilldown",
            "tenant_id": "tenant-drilldown",
            "user_id": "user-drilldown",
            "role": "support",
        }
    )
    state = {
        **base_state,
        "user_query": "订单号是多少？",
        "thread_id": "thread-drilldown",
        "tenant_id": "tenant-drilldown",
        "user_id": "user-drilldown",
        "role": "support",
        "business_query_context_binding": binding,
        "last_query_spec": {
            "operation": "aggregate",
            "resource": "order",
            "metric_id": "order_count",
            "time_preset": "this_week",
            "filters": {"status_filter": []},
        },
        "last_answer_context": {
            "schema_version": "business_query_answer_context.v1",
            "query_spec": {
                "operation": "aggregate",
                "resource": "order",
                "metric_id": "order_count",
                "time_preset": "this_week",
                "filters": {"status_filter": []},
            },
            "result_refs": ["order_count"],
            "allowed_drilldowns": ["list"],
            "fields_shown": ["order_count"],
            "scope": {"scope_label": "authorized_merchants"},
            "time_summary": "this_week",
            "filter_summary": None,
        },
        "expected_slot_type": "field_request",
        "expected_slot_context": {
            "schema_version": "business_query_expected_slot_context.v1",
            "purpose": "business_query_drilldown",
            "context_binding": binding,
            "operation": "aggregate",
            "resource": "order",
            "allowed_drilldowns": ["list"],
            "fields_shown": ["order_count"],
        },
    }
    monkeypatch.setattr(contextual_intent_module, "_get_llm", fail_llm)

    result = await contextual_intent_module.contextual_intent_resolve(state)

    spec = result["candidate_slots"]["business_query_spec"]
    assert result["primary_intent"] == "business_metric_query"
    assert spec["operation"] == "list"
    assert spec["resource"] == "order"
    assert spec["time_preset"] == "this_week"
    assert spec["fields"] == ["order_no"]
    assert spec["filters"] == {"status_filter": []}
    assert spec["limit"] == 20
    assert result["routing_hints"]["workflow_state_resolution"] == "answered_business_query_drilldown"
    assert result["routing_hints"]["expected_slot_type"] == "field_request"
    assert result["classification_trace"]["raw_llm_classification"] is None
    assert result["classification_trace"]["route_decision"] == "slot_resolution_gate"
    assert "business_query_drilldown_field_request" in result["classification_trace"]["reason_codes"]
    assert route_after_contextual_intent(result) == "slot_resolution_gate"
    for forbidden in FORBIDDEN_DOWNSTREAM_FIELDS:
        assert forbidden not in result


@pytest.mark.asyncio
async def test_contextual_intent_resolve_business_query_field_request_without_context_fails_closed(
    monkeypatch,
    base_state,
):
    monkeypatch.setattr(
        contextual_intent_module,
        "_get_llm",
        lambda: FakeLLM(
            _intent_v3(
                primary_intent="unsupported",
                requested_operation="advise",
                confidence=0.2,
                calibrated_confidence=0.2,
                required_slots={"all_of": [], "any_of": [], "optional": []},
                candidate_slots={},
                reason_codes=["no_business_query_context"],
            )
        ),
    )
    state = {**base_state, "user_query": "订单号是多少？"}

    result = await contextual_intent_module.contextual_intent_resolve(state)

    assert result["current_intent"] == "unsupported"
    assert "business_query_spec" not in result["candidate_slots"]
    assert route_after_contextual_intent(result) == "clarification_gate"


@pytest.mark.asyncio
async def test_contextual_intent_resolve_invalid_structured_output_fails_closed(monkeypatch, base_state):
    monkeypatch.setattr(
        contextual_intent_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "primary_intent": "not_valid",
                "confidence": 0.95,
                "approval_result": {"decision": "approve"},
            }
        ),
    )

    result = await contextual_intent_module.contextual_intent_resolve(base_state)

    assert result["current_intent"] == "unsupported"
    assert result["requested_operation"] == "advise"
    assert result["classification_trace"]["raw_llm_classification"] is None
    assert result["classification_trace"]["effective_classification"]["primary_intent"] == "unsupported"
    assert result["classification_trace"]["route_decision"] == "clarification_gate"
    assert "pre_route_decision" not in result["classification_trace"]
    assert result["node_errors"][-1]["node"] == "contextual_intent_resolve"
    assert result["trace_steps"][-1]["node"] == "contextual_intent_resolve"

    llm_output = result["llm_outputs"]["contextual_intent_resolve"]
    assert llm_output["status"] == "fallback"
    assert llm_output["fallback_intent"] == "unsupported"
    assert "classifier_validation_failed" in llm_output["reason_codes"]
    assert llm_output["error_type"] == "structured_output_validation_failed"
    assert "raw" not in llm_output
    assert route_after_contextual_intent(result) == "clarification_gate"


def test_intent_result_v3_rejects_approval_result_extra_field():
    with pytest.raises(ValidationError):
        IntentResultV3.model_validate(_intent_v3(approval_result={"decision": "approve"}))


def test_intent_result_to_state_uses_slot_policy_registry_for_required_slots(monkeypatch):
    class FakeSlotRegistry:
        def required_slots_for(self, intent: str) -> RequiredSlotExpression:
            return RequiredSlotExpression(all_of=["ticket_id"])

    monkeypatch.setattr(contextual_intent_module, "SLOT_POLICY_REGISTRY", FakeSlotRegistry(), raising=False)
    result = IntentResultV3.model_validate(_intent_v3(required_slots={"all_of": [], "any_of": [], "optional": []}))

    update = contextual_intent_module.intent_result_to_state(result, user_query="订单 ORD-1 怎么处理？")

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
            del primary_intent, secondary_intents, requested_operation, query, raw_confidence
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

    monkeypatch.setattr(contextual_intent_module, "INTENT_POLICY_REGISTRY", FakeIntentRegistry(), raising=False)
    result = IntentResultV3.model_validate(_intent_v3(primary_intent="refund_troubleshooting"))

    update = contextual_intent_module.intent_result_to_state(result, user_query="hi")

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

    update = contextual_intent_module.intent_result_to_state(result, user_query="查订单状态，同时看政策")
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
    assert update["llm_outputs"]["contextual_intent_resolve"]["classification_trace"] == trace


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

    update = contextual_intent_module.intent_result_to_state(
        result, pre_route=pre_route, user_query="查订单状态，同时看政策"
    )
    trace = update["classification_trace"]

    assert update["primary_intent"] == "order_status_inquiry"
    assert update["routing_hints"]["pre_route_disposition"] == "multi_target_request"
    assert "requires_clarification" not in update["routing_hints"]
    assert "clarification_reason" not in update["routing_hints"]
    assert trace["clarification_decision"]["requires_clarification"] is False
    assert "pre_route_decision" not in trace
    assert trace["route_decision"] == "slot_resolution_gate"
    assert trace["executable_prefix"] == ["s1"]
    assert [step["intent"] for step in update["deferred_steps"]] == ["policy_qa"]


def test_lossy_same_intent_merge_keeps_multi_target_clarification():
    result = IntentResultV3.model_validate(
        _intent_v3(
            primary_intent="order_status_inquiry",
            requested_operation="read_status",
            secondary_intents=["order_status_inquiry"],
            candidate_slots={"order_id": "ORD-001"},
        )
    )
    pre_route = PreRouteDecision(
        disposition="multi_target_request",
        reason_codes=["multi_target_request"],
        requires_clarification=True,
    )

    update = contextual_intent_module.intent_result_to_state(
        result, pre_route=pre_route, user_query="查这两个订单"
    )
    trace = update["classification_trace"]

    assert trace["plan_normalization"] == ["same_intent_entity_merge_limited"]
    assert [step["step_id"] for step in trace["task_plan"]["steps"]] == ["s1"]
    assert trace["deferred_steps"] == []
    assert update["routing_hints"]["requires_clarification"] is True
    assert update["routing_hints"]["clarification_reason"] == "multi_target_request"
    assert trace["clarification_decision"]["requires_clarification"] is True
    assert trace["route_decision"] == "clarification_gate"


def test_high_risk_secondary_step_is_deferred_not_executed():
    result = IntentResultV3.model_validate(
        _intent_v3(
            primary_intent="order_status_inquiry",
            requested_operation="read_status",
            secondary_intents=["action_request"],
            candidate_slots={"order_id": "ORD-001", "action_type": "refund"},
        )
    )

    update = contextual_intent_module.intent_result_to_state(result, user_query="查订单状态，再处理退款")
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

    update = contextual_intent_module.intent_result_to_state(result, user_query="给补偿券，同时看政策")
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

    update = contextual_intent_module.intent_result_to_state(result, user_query="查订单状态，也看退款政策")
    trace = update["classification_trace"]

    assert update["primary_intent"] == "order_status_inquiry"
    assert trace["executable_prefix"] == ["s1"]
    assert trace["task_plan"]["steps"][1]["intent"] == "policy_qa"
    assert trace["task_plan"]["steps"][1]["operation"] == "read_status"
    assert update["deferred_steps"] == [trace["task_plan"]["steps"][1]]


@pytest.mark.asyncio
async def test_approval_chat_pre_route_overrides_llm(monkeypatch, base_state):
    monkeypatch.setattr(contextual_intent_module, "_get_llm", lambda: FakeLLM(_intent_v3(primary_intent="policy_qa")))

    result = await contextual_intent_module.contextual_intent_resolve({**base_state, "user_query": "approve APR-1"})

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
        contextual_intent_module,
        "_get_llm",
        lambda: FakeLLM(
            _intent_v3(
                primary_intent="order_status_inquiry",
                requested_operation="read_status",
                candidate_slots={"order_id": "ORD-001", "action_type": "refund"},
            )
        ),
    )

    result = await contextual_intent_module.contextual_intent_resolve(
        {**base_state, "user_query": "直接退款 ORD-001"}
    )

    assert result["primary_intent"] == "action_request"
    assert result["requested_operation"] == "execute_action"
    assert result["risk_tier"] == "approval_required"
    assert result["routing_hints"]["pre_route_disposition"] == "safety_sensitive"
    assert "pre_route_decision" not in result["classification_trace"]
    assert result["classification_trace"]["executable_prefix"] == []
    assert result["deferred_steps"] == []
    for forbidden_key in ("proposed_action", "action_draft", "approval_result", "action_result"):
        assert forbidden_key not in result


@pytest.mark.asyncio
async def test_pending_required_slot_ambiguous_reply_reasks_for_slot(monkeypatch, base_state):
    def fail_llm():
        raise AssertionError("LLM should not be called for an ambiguous pending slot reply")

    monkeypatch.setattr(contextual_intent_module, "_get_llm", fail_llm)
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

    result = await contextual_intent_module.contextual_intent_resolve(state)

    assert result["primary_intent"] == "refund_troubleshooting"
    assert result["intent_confidence"] == 0.0
    assert result["routing_hints"]["workflow_state_resolution"] == "pending_required_slot_not_answered"
    assert result["routing_hints"]["clarification_reason"] == "missing_required_slots"
    assert result["classification_trace"]["route_decision"] == "clarification_gate"


@pytest.mark.asyncio
async def test_short_approval_reply_without_flow_is_not_classified_by_llm(monkeypatch, base_state):
    def fail_llm():
        raise AssertionError("LLM should not be called for a standalone approval-like short reply")

    monkeypatch.setattr(contextual_intent_module, "_get_llm", fail_llm)

    result = await contextual_intent_module.contextual_intent_resolve({**base_state, "user_query": "同意"})

    assert result["primary_intent"] == "unsupported"
    assert result["requested_operation"] == "advise"
    assert result["risk_tier"] == "forbidden_in_chat"
    assert result["routing_hints"]["clarification_reason"] == "approval_chat_not_trusted"
    assert result["classification_trace"]["route_decision"] == "clarification_gate"


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["你好", "您好", "hi", "谢谢"])
async def test_standalone_small_talk_is_direct_without_llm(monkeypatch, base_state, query):
    def fail_llm():
        raise AssertionError("LLM should not be called for standalone small talk")

    monkeypatch.setattr(contextual_intent_module, "_get_llm", fail_llm)

    result = await contextual_intent_module.contextual_intent_resolve({**base_state, "user_query": query})

    assert result["primary_intent"] == "small_talk"
    assert result["requested_operation"] == "advise"
    assert result["classification_trace"]["route_decision"] == "final_response"
    assert "standalone_small_talk" in result["classification_trace"]["reason_codes"]
    assert result["llm_outputs"]["contextual_intent_resolve"]["classification_trace"] == result["classification_trace"]


@pytest.mark.asyncio
async def test_business_keyword_text_does_not_use_small_talk_guard(monkeypatch, base_state):
    monkeypatch.setattr(
        contextual_intent_module,
        "_get_llm",
        lambda: FakeLLM(
            _intent_v3(
                primary_intent="order_status_inquiry",
                requested_operation="read_status",
                candidate_slots={},
            )
        ),
    )

    result = await contextual_intent_module.contextual_intent_resolve({**base_state, "user_query": "你好，订单呢"})

    assert result["primary_intent"] == "order_status_inquiry"
    assert "standalone_small_talk" not in result["classification_trace"]["reason_codes"]


@pytest.mark.asyncio
async def test_aggregate_order_count_request_routes_to_metric_intent_without_llm(monkeypatch, base_state):
    def fail_llm():
        raise AssertionError("LLM should not be called for deterministic aggregate order counts")

    monkeypatch.setattr(contextual_intent_module, "_get_llm", fail_llm)

    result = await contextual_intent_module.contextual_intent_resolve({**base_state, "user_query": "当前有多少订单"})

    assert result["primary_intent"] == "business_metric_query"
    assert result["requested_operation"] == "read_status"
    assert result["candidate_slots"] == {"metric_id": "order_count"}
    assert result["classification_trace"]["route_decision"] == "slot_resolution_gate"
    assert "deterministic_business_metric_query" in result["classification_trace"]["reason_codes"]


@pytest.mark.asyncio
async def test_concrete_order_status_identifier_does_not_use_metric_guard(monkeypatch, base_state):
    monkeypatch.setattr(
        contextual_intent_module,
        "_get_llm",
        lambda: FakeLLM(
            _intent_v3(
                primary_intent="order_status_inquiry",
                requested_operation="read_status",
                candidate_slots={"order_id": "ORD-2024-001"},
            )
        ),
    )

    result = await contextual_intent_module.contextual_intent_resolve(
        {**base_state, "user_query": "订单 ORD-2024-001 状态如何"}
    )

    assert result["primary_intent"] == "order_status_inquiry"
    assert result["candidate_slots"] == {"order_id": "ORD-2024-001"}
    assert "deterministic_business_metric_query" not in result["classification_trace"]["reason_codes"]


def test_contextual_metric_parser_uses_business_query_registry_metadata() -> None:
    source = Path("src/agent/nodes/contextual_intent_resolve.py").read_text()
    prompt_source = Path("src/agent/prompts.py").read_text()

    assert "BUSINESS_QUERY_REGISTRY" in source
    assert "BUSINESS_QUERY_REGISTRY" in prompt_source
    for forbidden in (
        'metric_id = "order_count"',
        'metric_id = "refund_case_count"',
        'metric_id = "pending_ticket_count"',
        'metric_id = "coupon_record_count"',
        'metric_id = "merchant_refund_rate"',
        '"metric_time_preset"] = "current_snapshot"',
        "metric_id (one of: order_count",
        "metric_time_preset (one of: today",
    ):
        assert forbidden not in source
        assert forbidden not in prompt_source
