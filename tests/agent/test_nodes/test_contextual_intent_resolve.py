from __future__ import annotations

from pathlib import Path

import pytest

from tests.agent.conftest import FakeLLM

from src.agent.nodes import contextual_intent_resolve as contextual_intent_module
from src.agent.routing import route_after_contextual_intent


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
    assert not Path("src/agent/nodes/classify_intent.py").exists()
    assert not Path("tests/agent/test_nodes/test_classify_intent.py").exists()
    assert "src.agent.nodes.classify_intent" not in Path("tests/agent/test_intent_adapter.py").read_text()


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
