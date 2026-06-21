from __future__ import annotations

import pytest

from src.agent.nodes.receive_request import receive_request


@pytest.mark.asyncio
async def test_receive_request_resets_ephemeral(base_state):
    state = {
        **base_state,
        "current_intent": "old_intent",
        "intent_confidence": 0.99,
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
async def test_receive_request_new_run_id_each_call(base_state):
    first = await receive_request(base_state)
    second = await receive_request(base_state)

    assert first["current_run_id"] != second["current_run_id"]


@pytest.mark.asyncio
async def test_receive_request_preserves_api_run_id_when_provided(base_state):
    result = await receive_request({**base_state, "current_run_id": "api-run-001"})

    assert result["current_run_id"] == "api-run-001"
