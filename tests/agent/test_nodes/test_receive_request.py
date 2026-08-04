from __future__ import annotations

import pytest

import src.agent.nodes.receive_request as receive_request_module
from src.agent.nodes.receive_request import receive_request
from src.agent.schemas import RequiredSlotExpression
from src.agent.state import AgentState, business_query_context_binding


@pytest.mark.asyncio
async def test_receive_request_resets_ephemeral(base_state):
    state = {
        **base_state,
        "current_intent": "old_intent",
        "intent_confidence": 0.99,
        "risk_tier": "read_only",
        "classification_trace": {"old": "trace"},
        "slot_resolution_trace": {"schema": "slot_resolution_trace.phase54"},
        "missing_required_slots": [{"any_of": ["order_id", "refund_case_id"]}],
        "task_plan": {"steps": [{"step_id": "s1"}], "terminal_step_id": "s1"},
        "deferred_steps": [{"step_id": "s2", "intent": "ticket_reply_draft"}],
        "target_merchant_context": {"status": "resolved", "source": "spoofed"},
        "pre_route_decision": {"disposition": "approval_chat_not_trusted"},
        "safety_flags": {"requires_clarification": True},
        "active_flow_state": {"old": "flow"},
        "secondary_intents": ["policy_qa"],
        "required_slots": {"all_of": ["order_id"], "any_of": [], "optional": []},
        "candidate_slots": {"order_id": "ORD-OLD"},
        "routing_hints": {"pre_route_disposition": "old"},
        "clarification_request": {"reason": "old"},
        "last_business_context_refs": {"business_fact_refs": [{"resource_id": "ORD-OLD"}]},
        "business_context": {"old": "data"},
        "canonical_action": {"disposition": "manual_review"},
        "risk_signals": ["manual_review_required"],
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
    assert result["slot_resolution_trace"] is None
    assert result["missing_required_slots"] == []
    assert result["task_plan"] is None
    assert result["deferred_steps"] == []
    assert result["target_merchant_context"] is None
    assert result["pre_route_decision"] is None
    assert result["safety_flags"] == {}
    assert result["active_flow_state"] is None
    assert result["secondary_intents"] == []
    assert result["required_slots"] == {"all_of": [], "any_of": [], "optional": []}
    assert result["candidate_slots"] == {}
    assert result["routing_hints"] == {}
    assert result["clarification_request"] is None
    assert result["last_business_context_refs"] is None
    assert result["business_context"] is None
    assert result["canonical_action"] is None
    assert result["risk_signals"] == []
    assert result["action_draft"] is None
    assert result["draft_outcome"] is None
    assert result["execution_mode"] is None
    assert result["action_result"] is None
    assert [step["node"] for step in result["trace_steps"]] == ["receive_request"]
    assert result["current_run_id"] is not None


@pytest.mark.asyncio
async def test_receive_request_two_turn_reset_removes_checkpointed_safety_projection(base_state):
    first_turn_checkpoint = {
        **base_state,
        "canonical_action": {"executable_action_type": None, "disposition": "manual_review"},
        "risk_signals": ["manual_review_required"],
        "recommendation_draft": {"recommended_action": "launch rocket"},
        "risk_assessment": {"risk_disposition": "manual_review"},
    }

    second_turn = await receive_request(first_turn_checkpoint)

    assert second_turn["canonical_action"] is None
    assert second_turn["risk_signals"] == []
    assert second_turn["recommendation_draft"] is None
    assert second_turn["risk_assessment"] is None


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
async def test_receive_request_resets_rag_verifier_fields(base_state):
    state = {
        **base_state,
        "rag_context_bundle": {"schema_version": "rag_context_bundle_state_safe.v1"},
        "rag_verification": {"overall_outcome": "supported", "route": {"route": "allow"}},
        "verifier_status": "supported",
        "verification_route": "allow",
        "verifier_reason_codes": ["old_reason"],
        "verifier_safe_citation_refs": ["policy#old"],
        "verifier_metrics": {"claim_count": 1},
    }

    result = await receive_request(state)

    for field in (
        "rag_context_bundle",
        "rag_verification",
        "verifier_status",
        "verification_route",
        "verifier_reason_codes",
        "verifier_safe_citation_refs",
        "verifier_metrics",
    ):
        assert result[field] is None


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
        "reviewed_memory_context_retrieve_status": {"schema_version": "reviewed_memory_context_retrieve_status.v1"},
        "case_working_context": {"schema_version": "case_working_context_active_payload.v1"},
        "case_working_context_lifecycle_status": {"schema_version": "case_working_context_lifecycle_status.v1"},
        "memory_write_result": {"status": "written"},
        "memory_write_decision": {"schema_version": "memory_write_decision.v2"},
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
        "case_working_context",
        "case_working_context_lifecycle_status",
        "memory_write_result",
        "memory_write_decision",
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
        "case_working_context",
        "case_working_context_lifecycle_status",
        "memory_write_decision",
    ):
        assert field in annotations


def test_agent_state_declares_target_merchant_context_field():
    assert "target_merchant_context" in AgentState.__annotations__


def test_agent_state_declares_safety_pre_route_fields():
    annotations = AgentState.__annotations__

    assert "pre_route_decision" in annotations
    assert "safety_flags" in annotations


def test_agent_state_declares_task_plan_fields():
    annotations = AgentState.__annotations__

    assert "task_plan" in annotations
    assert "deferred_steps" in annotations


def test_agent_state_declares_rag_verifier_fields():
    annotations = AgentState.__annotations__

    for field in (
        "rag_context_bundle",
        "rag_verification",
        "verifier_status",
        "verification_route",
        "verifier_reason_codes",
        "verifier_safe_citation_refs",
        "verifier_metrics",
    ):
        assert field in annotations


def test_agent_state_declares_slot_resolution_fields():
    annotations = AgentState.__annotations__

    assert "slot_resolution_trace" in annotations
    assert "missing_required_slots" in annotations


def test_agent_state_declares_business_query_drilldown_fields():
    annotations = AgentState.__annotations__

    for field in (
        "last_query_spec",
        "last_answer_context",
        "result_cursor",
        "expected_slot_type",
        "expected_slot_context",
        "business_query_context_binding",
    ):
        assert field in annotations


@pytest.mark.asyncio
async def test_receive_request_preserves_safe_business_query_drilldown_context(base_state):
    binding = business_query_context_binding(base_state)
    drilldown_context = {
        "schema_version": "business_query_answer_context.v1",
        "query_spec": {
            "operation": "aggregate",
            "resource": "order",
            "metric_id": "order_count",
            "time_preset": "this_week",
        },
        "result_refs": ["order_count"],
        "allowed_drilldowns": ["list"],
        "fields_shown": ["order_count"],
        "scope": {"scope_label": "authorized_merchants"},
        "time_summary": "this_week",
        "filter_summary": None,
    }
    state = {
        **base_state,
        "last_query_spec": drilldown_context["query_spec"],
        "last_answer_context": drilldown_context,
        "result_cursor": None,
        "expected_slot_type": "field_request",
        "expected_slot_context": {
            "schema_version": "business_query_expected_slot_context.v1",
            "purpose": "business_query_drilldown",
            "context_binding": binding,
        },
        "business_query_context_binding": binding,
        "business_context": {"facts": {"business_query": {"raw_rows": ["SHOULD_RESET"]}}},
        "tool_results": [{"raw_args": "SHOULD_RESET"}],
    }

    result = await receive_request(state)

    assert result["last_query_spec"] == drilldown_context["query_spec"]
    assert result["last_answer_context"] == drilldown_context
    assert result["result_cursor"] is None
    assert result["expected_slot_type"] == "field_request"
    assert result["expected_slot_context"]["context_binding"] == binding
    assert result["business_context"] is None
    assert result["tool_results"] == []
    serialized = str(
        {
            "last_query_spec": result["last_query_spec"],
            "last_answer_context": result["last_answer_context"],
            "result_cursor": result["result_cursor"],
            "expected_slot_context": result["expected_slot_context"],
        }
    )
    for forbidden in ("raw_rows", "raw_args", "tenant_id", "merchant_scope"):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_receive_request_clears_business_query_drilldown_context_on_binding_mismatch(base_state):
    original_binding = business_query_context_binding(base_state)
    changed_user_state = {
        **base_state,
        "user_id": "different-user",
        "last_query_spec": {"operation": "list", "resource": "order", "fields": ["order_no"]},
        "last_answer_context": {
            "schema_version": "business_query_answer_context.v1",
            "query_spec": {"operation": "list", "resource": "order", "fields": ["order_no"]},
            "result_refs": ["ORD-OLD"],
            "allowed_drilldowns": ["detail"],
            "fields_shown": ["order_no"],
        },
        "result_cursor": {"has_more": True, "limit": 20},
        "expected_slot_type": "field_request",
        "expected_slot_context": {
            "schema_version": "business_query_expected_slot_context.v1",
            "purpose": "business_query_drilldown",
            "context_binding": original_binding,
        },
    }
    changed_user_state["business_query_context_binding"] = business_query_context_binding(changed_user_state)

    result = await receive_request(changed_user_state)

    assert result["last_query_spec"] is None
    assert result["last_answer_context"] is None
    assert result["result_cursor"] is None
    assert result["expected_slot_type"] is None
    assert result["expected_slot_context"] is None


@pytest.mark.asyncio
async def test_receive_request_resets_phase33_rag_claim_package_fields(base_state):
    state = {
        **base_state,
        "rag_context_status": "verified",
        "verified_evidence_package": {"schema_version": "verified_evidence_package.v1", "package_id": "pkg-old"},
        "citation_map": {"C1": ["policy#old"]},
        "evidence_map": {"policy#old": {"evidence_id": "policy#old"}},
        "material_claims": [{"claim_id": "claim-old"}],
        "claim_verification_bundle": {"schema_version": "claim_verification_bundle.v1"},
        "blocked_claims": ["claim-old"],
        "safe_support_refs": ["policy#old"],
    }

    result = await receive_request(state)

    assert result["rag_context_status"] is None
    assert result["verified_evidence_package"] is None
    assert result["citation_map"] == {}
    assert result["evidence_map"] == {}
    assert result["material_claims"] == []
    assert result["claim_verification_bundle"] is None
    assert result["blocked_claims"] == []
    assert result["safe_support_refs"] == []


def test_agent_state_declares_phase33_rag_claim_package_fields():
    annotations = AgentState.__annotations__

    for field in (
        "rag_context_status",
        "verified_evidence_package",
        "citation_map",
        "evidence_map",
        "material_claims",
        "claim_verification_bundle",
        "blocked_claims",
        "safe_support_refs",
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

    assert result["slot_resolution_trace"] is None
    assert result["missing_required_slots"] == []
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


@pytest.mark.asyncio
async def test_receive_request_projects_pending_flow_from_slot_policy_registry(monkeypatch, base_state):
    class FakeIntentRegistry:
        def is_known_intent(self, intent: str) -> bool:
            return intent == "registry_only_intent"

    class FakeSlotRegistry:
        def required_slots_for(self, intent: str) -> RequiredSlotExpression:
            assert intent == "registry_only_intent"
            return RequiredSlotExpression(all_of=["ticket_id"])

    monkeypatch.setattr(receive_request_module, "INTENT_POLICY_REGISTRY", FakeIntentRegistry(), raising=False)
    monkeypatch.setattr(receive_request_module, "SLOT_POLICY_REGISTRY", FakeSlotRegistry(), raising=False)
    state = {
        **base_state,
        "primary_intent": "registry_only_intent",
        "requested_operation": "read_status",
        "required_slots": {"all_of": [], "any_of": [], "optional": []},
        "candidate_slots": {"ticket_id": None},
        "clarification_request": {
            "reason": "missing_required_slots",
            "clarification_request_id": "clarify_run-002",
            "blocked_nodes": ["investigate"],
        },
    }

    result = await receive_request({**state, "user_query": "TKT-12345"})

    assert result["active_flow_state"] == {
        "kind": "pending_required_slot",
        "reason": "missing_required_slots",
        "last_effective_intent": "registry_only_intent",
        "last_requested_operation": "read_status",
        "required_slots": {"all_of": ["ticket_id"], "any_of": [], "optional": []},
        "candidate_slots": {"ticket_id": None},
        "clarification_request_id": "clarify_run-002",
        "blocked_nodes": ["investigate"],
    }
