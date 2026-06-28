from __future__ import annotations

from typing import Any

from src.agent.working_state import project_working_state
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1


WORKING_STATE_DEBUG_PROJECTION = "SHOULD_NOT_LEAK_WORKING_STATE_DEBUG_PROJECTION"
WORKING_STATE_VERIFIER_PROMPT = "SHOULD_NOT_LEAK_WORKING_STATE_VERIFIER_PROMPT"
WORKING_STATE_PRIVATE_REASONING = "SHOULD_NOT_LEAK_WORKING_STATE_PRIVATE_REASONING"
WORKING_STATE_CANDIDATE_ONLY = "SHOULD_NOT_LEAK_CANDIDATE_ONLY_REF"


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


def _evidence_ref(
    *,
    doc_key: str = "policy_refund_timeout",
    chunk_id: str = "chunk_001",
    text: str = "Refund timeout compensation requires verified policy evidence.",
    score: float = 0.91,
    rank: int = 1,
) -> dict[str, Any]:
    return EvidenceRefV1.build(
        tenant_id="11111111-1111-1111-1111-111111111111",
        doc_key=doc_key,
        chunk_id=chunk_id,
        policy_version="v3",
        text=text,
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=score,
        rank=rank,
    ).model_dump(mode="json")


def _verified_package(*refs: dict[str, Any], status: str = "verified") -> dict[str, Any]:
    evidence_refs = list(refs) or [_evidence_ref()]
    return {
        "schema_version": "verified_evidence_package.v1",
        "package_id": "pkg-working-state",
        "status": status,
        "evidence_items": [],
        "citation_map": {"C1": [evidence_refs[0]["evidence_id"]]},
        "evidence_map": {ref["evidence_id"]: ref for ref in evidence_refs},
        "prompt_projection": {
            "safe_refs": [evidence_refs[0]["evidence_id"]],
            "citations": [{"citation_id": "C1", "evidence_id": evidence_refs[0]["evidence_id"]}],
        },
        "verifier_projection": {"safe_refs": [evidence_refs[0]["evidence_id"]]},
        "replay_snapshot_refs": [ref["evidence_id"] for ref in evidence_refs],
        "debug_projection": {
            "debug_projection": WORKING_STATE_DEBUG_PROJECTION,
            "verifier_prompt": WORKING_STATE_VERIFIER_PROMPT,
            "private_reasoning": WORKING_STATE_PRIVATE_REASONING,
        },
        "stale_refs": [],
        "conflict_refs": [],
        "rejected_candidate_refs": [],
        "reason_codes": [],
        "policy_version": "v3",
        "retrieval_config_version": RETRIEVAL_CONFIG_VERSION,
    }


def _claim_bundle(*safe_support_refs: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "claim_verification_bundle.v1",
        "overall_status": "verified",
        "route": "continue",
        "claim_results": [],
        "blocked_claims": [],
        "safe_support_refs": list(safe_support_refs),
        "reason_codes": [],
        "verifier_policy_version": "claim-verifier.v1",
        "verifier_prompt": WORKING_STATE_VERIFIER_PROMPT,
        "private_reasoning": WORKING_STATE_PRIVATE_REASONING,
    }


def _base_state(**overrides: Any) -> dict[str, Any]:
    verified_ref = _evidence_ref()
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
        "verified_evidence_package": _verified_package(verified_ref),
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
    assert dumped["retrieved_evidence_refs"] == [_evidence_ref()]
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
            "evidence_refs": [{"evidence_id": WORKING_STATE_CANDIDATE_ONLY}],
        },
        verified_evidence_package=_verified_package(
            _evidence_ref(),
            {
                **_evidence_ref(
                    doc_key="policy_candidate_only",
                    chunk_id="chunk_candidate",
                    text="candidate-only refs are not claim support",
                    score=0.4,
                    rank=2,
                ),
                "evidence_id": WORKING_STATE_CANDIDATE_ONLY,
            },
        ),
        claim_verification_bundle=_claim_bundle(_evidence_ref()),
        safe_support_refs=[_evidence_ref()],
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
        "debug_projection",
        WORKING_STATE_DEBUG_PROJECTION,
        WORKING_STATE_VERIFIER_PROMPT,
        WORKING_STATE_PRIVATE_REASONING,
        WORKING_STATE_CANDIDATE_ONLY,
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


def test_working_state_v1_uses_claim_safe_support_refs_before_package_evidence_map() -> None:
    """APF-14: safe_support_refs are the prompt-safe support subset; candidate-only refs stay out."""
    safe_ref = _evidence_ref(doc_key="policy_safe_support", chunk_id="chunk_safe", rank=1)
    package_only_ref = {
        **_evidence_ref(
            doc_key="policy_candidate_only",
            chunk_id="chunk_candidate",
            text="candidate-only package refs are not safe claim support.",
            score=0.44,
            rank=2,
        ),
        "evidence_id": WORKING_STATE_CANDIDATE_ONLY,
    }

    working_state = project_working_state(
        _base_state(
            verified_evidence_package=_verified_package(safe_ref, package_only_ref),
            claim_verification_bundle=_claim_bundle(safe_ref),
            safe_support_refs=[safe_ref],
            policy_evidence=[package_only_ref],
            retrieved_evidence={"evidence_refs": [package_only_ref]},
        )
    )

    assert working_state.retrieved_evidence_refs == [safe_ref]
    serialized = working_state.model_dump_json()
    assert "policy_safe_support/chunk_safe@v3" in serialized
    assert WORKING_STATE_CANDIDATE_ONLY not in serialized


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
