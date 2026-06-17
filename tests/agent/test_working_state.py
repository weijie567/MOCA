from __future__ import annotations

from typing import Any

from src.agent.working_state import project_working_state


def _safe_tool_summary(**overrides: Any) -> dict[str, Any]:
    summary = {
        "tool_call_id": "tool-call-001",
        "tool_result_id": "tool-result-001",
        "tool_name": "get_order",
        "status": "success",
        "summary": "Order ORD-1001 was loaded.",
        "prompt_summary": "Order ORD-1001 delivered; refund case still open.",
        "business_fact_refs": [{"resource_type": "order", "resource_id": "ORD-1001"}],
        "policy_evidence_refs": [{"evidence_id": "policy_refund_timeout/chunk_001@v3"}],
        "raw_result_ref": "tool-results/tool-result-001",
        "audit_ref": "audit/tool-result-001",
    }
    summary.update(overrides)
    return summary


def _base_state(**overrides: Any) -> dict[str, Any]:
    state = {
        "thread_id": "thread-001",
        "current_run_id": "run-001",
        "turn_id": "turn-001",
        "current_goal": "resolve_refund_or_policy_question",
        "current_intent": "refund_troubleshooting",
        "active_slots": {"order_id": "ORD-1001", "refund_case_id": "RF-1001"},
        "session_memory": {
            "unresolved_questions": ["需要确认商家是否已处理退款。"],
            "last_business_context_refs": {"business_fact_refs": [{"resource_id": "ORD-1001"}]},
        },
        "constraints": [
            "tool facts override session memory",
            "policy evidence is required before recommendation",
        ],
        "last_business_context_refs": {"business_fact_refs": [{"resource_id": "ORD-1001"}]},
        "evidence_refs": [{"evidence_id": "policy_refund_timeout/chunk_001@v3"}],
        "tool_results": [_safe_tool_summary()],
        "clarification_request": {
            "question": "请确认退款渠道。",
            "blocked_nodes": ["investigate", "action_draft"],
        },
        "action_draft": {
            "draft_id": "draft-001",
            "action_type": "coupon_grant",
            "status": "draft_created",
            "summary": "Created demo coupon draft.",
            "payload": {"amount": 50, "secret_marker": "ACTION_PAYLOAD_SHOULD_NOT_APPEAR"},
        },
    }
    state.update(overrides)
    return state


def test_working_state_v1_projects_allowlisted_current_run_fields() -> None:
    working_state = project_working_state(_base_state())
    dumped = working_state.model_dump(mode="json")

    assert dumped["schema_version"] == "working_state.v1"
    assert dumped["thread_id"] == "thread-001"
    assert dumped["run_id"] == "run-001"
    assert dumped["turn_id"] == "turn-001"
    assert dumped["current_goal"] == "resolve_refund_or_policy_question"
    assert dumped["current_intent"] == "refund_troubleshooting"
    assert dumped["active_slots"] == {"order_id": "ORD-1001", "refund_case_id": "RF-1001"}
    assert dumped["open_questions"] == ["需要确认商家是否已处理退款。"]
    assert dumped["constraints"] == [
        "tool facts override session memory",
        "policy evidence is required before recommendation",
    ]
    assert dumped["business_context_refs"] == [{"resource_id": "ORD-1001"}]
    assert dumped["retrieved_evidence_refs"] == [{"evidence_id": "policy_refund_timeout/chunk_001@v3"}]
    assert dumped["recent_tool_results"] == [_safe_tool_summary()]
    assert dumped["pending_confirmation"] == {"question": "请确认退款渠道。"}
    assert dumped["draft_artifact"] == {
        "draft_id": "draft-001",
        "action_type": "coupon_grant",
        "status": "draft_created",
        "summary": "Created demo coupon draft.",
    }


def test_working_state_v1_excludes_raw_tool_business_policy_trace_and_llm_fields() -> None:
    state = _base_state(
        business_context={
            "customer_phone": "13800000000",
            "business_context_body": "BUSINESS_CONTEXT_BODY_SHOULD_NOT_APPEAR",
        },
        retrieved_evidence={
            "full_text": "FULL_POLICY_TEXT_SHOULD_NOT_APPEAR",
            "evidence": [{"body": "RETRIEVED_EVIDENCE_BODY_SHOULD_NOT_APPEAR"}],
        },
        tool_results=[
            _safe_tool_summary(
                data={"raw_payload": {"secret_marker": "SHOULD_NOT_APPEAR"}},
                raw_payload={"secret_marker": "SHOULD_NOT_APPEAR"},
                summary="Safe summary survives.",
                prompt_summary="Safe prompt summary survives.",
            )
        ],
        approval_result={
            "schema_version": "approval_result.v1",
            "decision_type": "accept",
            "body": "APPROVAL_BODY_SHOULD_NOT_APPEAR",
        },
        proposed_action={
            "payload": {"amount": 50},
            "body": "PROPOSED_ACTION_BODY_SHOULD_NOT_APPEAR",
        },
        action_draft={
            "draft_id": "draft-raw",
            "action_type": "coupon_grant",
            "status": "draft_created",
            "summary": "Safe draft summary.",
            "payload": {"amount": 50, "secret_marker": "ACTION_DRAFT_PAYLOAD_SHOULD_NOT_APPEAR"},
        },
        draft_outcome={
            "status": "not_executed_demo",
            "body": "DRAFT_OUTCOME_BODY_SHOULD_NOT_APPEAR",
        },
        llm_outputs={"raw_completion": "LLM_OUTPUT_SHOULD_NOT_APPEAR"},
        trace_steps=[{"node": "investigate", "debug": "TRACE_STEP_SHOULD_NOT_APPEAR"}],
        node_errors=[{"traceback": "NODE_ERROR_SHOULD_NOT_APPEAR"}],
    )

    serialized = project_working_state(state).model_dump_json()

    assert "Safe prompt summary survives." in serialized
    for forbidden in (
        "SHOULD_NOT_APPEAR",
        "raw_payload",
        "BUSINESS_CONTEXT_BODY_SHOULD_NOT_APPEAR",
        "FULL_POLICY_TEXT_SHOULD_NOT_APPEAR",
        "RETRIEVED_EVIDENCE_BODY_SHOULD_NOT_APPEAR",
        "approval_result",
        "APPROVAL_BODY_SHOULD_NOT_APPEAR",
        "proposed_action",
        "PROPOSED_ACTION_BODY_SHOULD_NOT_APPEAR",
        "action_draft",
        "ACTION_DRAFT_PAYLOAD_SHOULD_NOT_APPEAR",
        "draft_outcome",
        "DRAFT_OUTCOME_BODY_SHOULD_NOT_APPEAR",
        "llm_outputs",
        "LLM_OUTPUT_SHOULD_NOT_APPEAR",
        "trace_steps",
        "TRACE_STEP_SHOULD_NOT_APPEAR",
        "node_errors",
        "NODE_ERROR_SHOULD_NOT_APPEAR",
    ):
        assert forbidden not in serialized


def test_working_state_v1_serialization_excludes_large_nested_tool_result() -> None:
    large_nested_tool_result = {
        "tool_call_id": "tool-call-large",
        "tool_result_id": "tool-result-large",
        "tool_name": "get_refund_case",
        "status": "success",
        "summary": "Refund case summary.",
        "prompt_summary": "Refund case RF-1001 is pending merchant confirmation.",
        "data": {
            "raw_payload": {
                "secret_marker": "SHOULD_NOT_APPEAR",
                "deep": [{"large_blob": "SHOULD_NOT_APPEAR" * 100}],
            }
        },
        "business_fact_refs": [{"resource_type": "refund_case", "resource_id": "RF-1001"}],
        "policy_evidence_refs": [],
        "raw_result_ref": "tool-results/tool-result-large",
        "audit_ref": "audit/tool-result-large",
    }

    serialized = project_working_state(_base_state(tool_results=[large_nested_tool_result])).model_dump_json()

    assert "Refund case RF-1001 is pending merchant confirmation." in serialized
    assert "large_nested_tool_result" not in serialized
    assert "SHOULD_NOT_APPEAR" not in serialized
    assert "raw_payload" not in serialized
    assert "large_blob" not in serialized
