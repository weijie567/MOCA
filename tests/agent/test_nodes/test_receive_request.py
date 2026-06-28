from __future__ import annotations

import pytest

from src.agent.nodes.receive_request import receive_request
from src.agent.state import AgentState


@pytest.mark.asyncio
async def test_receive_request_resets_ephemeral(base_state):
    state = {
        **base_state,
        "current_intent": "old_intent",
        "intent_confidence": 0.99,
        "risk_tier": "read_only",
        "classification_trace": {"old": "trace"},
        "active_flow_state": {"old": "flow"},
        "secondary_intents": ["policy_qa"],
        "required_slots": {"all_of": ["order_id"], "any_of": [], "optional": []},
        "candidate_slots": {"order_id": "ORD-OLD"},
        "routing_hints": {"pre_route_disposition": "old"},
        "clarification_request": {"reason": "old"},
        "last_business_context_refs": {"business_fact_refs": [{"resource_id": "ORD-OLD"}]},
        "business_context": {"old": "data"},
        "action_draft": {"draft_id": "old-draft"},
        "draft_outcome": {"status": "not_executed_demo"},
        "execution_mode": "demo",
        "action_result": {"status": "draft_created"},
        "trace_steps": [{"node": "old_node"}],
    }

    result = await receive_request(state)

    assert result["current_intent"] is None
    assert result["intent_confidence"] is None
    assert result["risk_tier"] is None
    assert result["classification_trace"] is None
    assert result["active_flow_state"] is None
    assert result["secondary_intents"] == []
    assert result["required_slots"] == {"all_of": [], "any_of": [], "optional": []}
    assert result["candidate_slots"] == {}
    assert result["routing_hints"] == {}
    assert result["clarification_request"] is None
    assert result["last_business_context_refs"] is None
    assert result["business_context"] is None
    assert result["action_draft"] is None
    assert result["draft_outcome"] is None
    assert result["execution_mode"] is None
    assert result["action_result"] is None
    assert [step["node"] for step in result["trace_steps"]] == ["receive_request"]
    assert result["current_run_id"] is not None


@pytest.mark.asyncio
async def test_receive_request_clears_phase14_action_bindings(base_state):
    state = {
        **base_state,
        "approval_revision_refs": [{"approval_id": "old-approval", "revision": 1}],
        "action_payload_hash": "sha256:old",
        "safety_snapshot_ref": "snapshot:old",
        "safety_snapshot_hash": "sha256:snapshot",
        "safety_snapshot_verified": True,
        "policy_config_version": "policy-old",
        "risk_config_version": "risk-old",
        "retrieval_config_version": "retrieval-old",
        "auto_allowed": True,
    }

    result = await receive_request(state)

    assert result["approval_revision_refs"] is None
    assert result["action_payload_hash"] is None
    assert result["safety_snapshot_ref"] is None
    assert result["safety_snapshot_hash"] is None
    assert result["safety_snapshot_verified"] is None
    assert result["policy_config_version"] is None
    assert result["risk_config_version"] is None
    assert result["retrieval_config_version"] is None
    assert result["auto_allowed"] is None


@pytest.mark.asyncio
async def test_receive_request_resets_session_context_target_fields(base_state):
    state = {
        **base_state,
        "session_memory": {"active_slots": {"order_id": "ORD-OLD"}},
        "session_memory_bundle": {"schema_version": "session_memory_bundle.v1"},
        "session_context": {"active_slots": {"order_id": "ORD-OLD"}},
        "session_context_bundle": {"schema_version": "session_context_bundle.v1"},
        "session_context_load_status": {"schema_version": "session_context_load_status.v1"},
        "long_term_memory": [{"content": "old long-term memory"}],
        "case_memory": [{"excerpt": "old case memory"}],
        "memory_context": {"long_term_items": [{"content": "old memory context"}]},
        "memory_context_bundle": {"schema_version": "reviewed_memory_context_bundle.v1"},
        "reviewed_memory_context_retrieve_status": {
            "schema_version": "reviewed_memory_context_retrieve_status.v1"
        },
        "memory_write_result": {"status": "written"},
    }

    result = await receive_request(state)

    for field in (
        "session_memory",
        "session_memory_bundle",
        "session_context",
        "session_context_bundle",
        "session_context_load_status",
        "long_term_memory",
        "case_memory",
        "memory_context",
        "memory_context_bundle",
        "reviewed_memory_context_retrieve_status",
        "memory_write_result",
    ):
        assert result[field] is None


def test_agent_state_declares_session_context_target_fields():
    annotations = AgentState.__annotations__

    for field in (
        "session_context",
        "session_context_bundle",
        "session_context_load_status",
        "memory_context",
        "memory_context_bundle",
        "reviewed_memory_context_retrieve_status",
    ):
        assert field in annotations


@pytest.mark.asyncio
async def test_receive_request_new_run_id_each_call(base_state):
    first = await receive_request(base_state)
    second = await receive_request(base_state)

    assert first["current_run_id"] != second["current_run_id"]


@pytest.mark.asyncio
async def test_receive_request_preserves_api_run_id_when_provided(base_state):
    result = await receive_request({**base_state, "current_run_id": "api-run-001"})

    assert result["current_run_id"] == "api-run-001"


@pytest.mark.asyncio
async def test_receive_request_projects_pending_required_slot_flow(base_state):
    state = {
        **base_state,
        "primary_intent": "refund_troubleshooting",
        "requested_operation": "read_status",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "candidate_slots": {"order_id": None},
        "clarification_request": {
            "reason": "missing_required_slots",
            "clarification_request_id": "clarify_run-001",
            "questions": ["请提供订单号或退款单号。"],
            "blocked_nodes": ["investigate", "action_draft"],
            "resume_policy": "same_thread_only",
        },
    }

    result = await receive_request({**state, "user_query": "ORD-12345"})

    assert result["active_flow_state"] == {
        "kind": "pending_required_slot",
        "reason": "missing_required_slots",
        "last_effective_intent": "refund_troubleshooting",
        "last_requested_operation": "read_status",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "candidate_slots": {"order_id": None},
        "clarification_request_id": "clarify_run-001",
        "blocked_nodes": ["investigate", "action_draft"],
    }
