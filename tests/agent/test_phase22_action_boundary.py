from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from src.agent.graph import route_after_risk
from src.agent.nodes import assess_risk_and_approval as assess_risk_module
from src.agent.nodes.action_draft import action_draft
from src.approvals.snapshots import build_action_safety_snapshot
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1


ACTION_HASH = "sha256:" + "1" * 64
SNAPSHOT_HASH = "sha256:" + "2" * 64


def _evidence_ref(tenant_id: str) -> dict[str, Any]:
    ref = EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v2",
        text="Current refund policy requires verified business facts before compensation.",
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.91,
        rank=1,
    )
    return ref.model_dump(mode="json")


def _non_allow_verification(outcome: str, route: str = "manual_review") -> dict[str, Any]:
    return {
        "overall_outcome": outcome,
        "allows_recommendation": False,
        "allows_action_recommendation": False,
        "route": {
            "route": route,
            "selected_by": "backend",
            "model_selected": False,
            "decision_source": "phase22_verifier",
        },
        "reason_codes": [outcome],
    }


def _actionable_state(base_state: dict[str, Any], *, outcome: str, route: str = "manual_review") -> dict[str, Any]:
    return {
        **base_state,
        "current_intent": "compensation_suggestion",
        "current_run_id": str(uuid4()),
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Model proposes compensation.",
            "confidence": 0.93,
            "risk_level": "high",
            "missing_info": [],
            "evidence_refs": [_evidence_ref(base_state["tenant_id"])],
        },
        "business_context": {
            "order": {"id": "order-1", "order_no": "ORD-1001", "status": "delivered"},
            "refund_case": {"id": "refund-1", "refund_case_no": "RF-1001", "requested_amount": "100.00"},
        },
        "evidence_refs": [_evidence_ref(base_state["tenant_id"])],
        "rag_verification": _non_allow_verification(outcome, route=route),
    }


class ExplodingRiskLLM:
    def with_structured_output(self, schema: type[Any]) -> Any:
        raise AssertionError("non-allow verifier outcomes must block before risk LLM or action proposal")


class ExplodingActionToolManager:
    async def invoke(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("non-allow verifier outcomes must block action draft creation")


def _approved_result(tenant_id: str, run_id: str) -> dict[str, Any]:
    return {
        "schema_version": "approval_result.v1",
        "approval_id": str(uuid4()),
        "tenant_id": tenant_id,
        "run_id": run_id,
        "decision_type": "approve",
        "status": "approved",
        "revision": 1,
        "request_version": 2,
        "level_version": 2,
        "assignment_version": 2,
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
        "decided_by": str(uuid4()),
        "decided_at": "2026-06-19T00:00:00.000Z",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "route"),
    [
        ("unsupported", "insufficient_evidence"),
        ("conflicting", "manual_review"),
        ("stale", "manual_review"),
        ("unauthorized", "refuse"),
        ("hash_mismatch", "refuse"),
        ("latest_version_invalid", "refuse"),
        ("business_fact_missing", "insufficient_evidence"),
        ("semantic_ambiguous", "manual_review"),
    ],
)
async def test_non_allow_verifier_outcomes_block_proposed_actions_and_snapshot_evidence(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
    outcome: str,
    route: str,
) -> None:
    """RTE-04: non-allow status leaves proposed action, approval, and snapshot state absent."""
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: ExplodingRiskLLM())

    result = await assess_risk_module.assess_risk_and_approval(
        _actionable_state(base_state, outcome=outcome, route=route),
        {"configurable": {"session": object()}},
    )

    assert result["proposed_action"] is None
    assert result.get("action_payload_hash") is None
    assert result.get("safety_snapshot_ref") is None
    assert result.get("safety_snapshot_hash") is None
    assert result.get("safety_snapshot_verified") is not True
    assert result["risk_assessment"]["approval_required"] is False
    assert result["risk_assessment"]["risk_level"] in {"manual_review", "blocked", "low"}
    assert result["rag_verification"]["route"]["selected_by"] == "backend"
    assert result["rag_verification"]["route"]["model_selected"] is False


@pytest.mark.asyncio
async def test_non_allow_risk_assessment_clears_same_turn_stale_snapshot_bindings(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """RTE-04: non-allow verifier updates must clear any stale action binding in state merge."""
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: ExplodingRiskLLM())
    state = {
        **_actionable_state(base_state, outcome="latest_version_invalid", route="refuse"),
        "proposed_action": {"action_type": "issue_coupon"},
        "approval_result": _approved_result(base_state["tenant_id"], str(uuid4())),
        "action_draft": {"draft_id": "stale-draft"},
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:stale",
        "safety_snapshot_hash": SNAPSHOT_HASH,
        "safety_snapshot_verified": True,
    }

    result = await assess_risk_module.assess_risk_and_approval(
        state,
        {"configurable": {"session": object()}},
    )
    merged_state = {**state, **result}

    assert merged_state["proposed_action"] is None
    assert merged_state["approval_result"] is None
    assert merged_state["action_draft"] is None
    assert merged_state["action_payload_hash"] is None
    assert merged_state["safety_snapshot_ref"] is None
    assert merged_state["safety_snapshot_hash"] is None
    assert merged_state["safety_snapshot_verified"] is False
    assert route_after_risk(merged_state) == "final_response"


def test_route_after_risk_fails_closed_when_verification_route_is_non_allow() -> None:
    """RTE-04: graph routing cannot send non-allow verifier state to approval_gate."""
    state = {
        "rag_verification": _non_allow_verification("unsupported", route="insufficient_evidence"),
        "risk_assessment": {"approval_required": True, "risk_level": "high"},
        "proposed_action": {"action_type": "issue_coupon"},
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
        "safety_snapshot_verified": True,
    }

    assert route_after_risk(state) == "final_response"


@pytest.mark.asyncio
async def test_action_draft_node_refuses_even_trusted_approval_when_verifier_route_is_non_allow(
    base_state: dict[str, Any],
) -> None:
    """RTE-04: action draft creation is blocked by non-allow verification even after approval payloads."""
    run_id = str(uuid4())
    state = {
        **base_state,
        "current_run_id": run_id,
        "rag_verification": _non_allow_verification("latest_version_invalid", route="refuse"),
        "risk_assessment": {"approval_required": True, "risk_level": "high"},
        "proposed_action": {"action_type": "issue_coupon", "target_type": "refund_case", "target_id": "RF-1001"},
        "approval_result": _approved_result(base_state["tenant_id"], run_id),
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
    }

    result = await action_draft(
        state,
        {"configurable": {"session": object(), "action_tool_manager": ExplodingActionToolManager()}},
    )

    assert result.get("action_draft") is None
    assert result.get("draft_outcome") is None
    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "VERIFIER_NOT_ALLOW"


def test_action_safety_snapshot_rejects_phase23_ranking_diagnostics_as_authority(base_state: dict[str, Any]) -> None:
    for field_name in ("ranking_diagnostics", "provider_payload", "raw_rewrite_payload"):
        with pytest.raises(ValueError, match="unknown snapshot fields"):
            build_action_safety_snapshot(
                tenant_id=base_state["tenant_id"],
                run_id=str(uuid4()),
                snapshot_id="snap-phase23-boundary",
                snapshot_ref="snapshot:phase23-boundary",
                policy_config_version="approval-policy.v1",
                risk_config_version="risk-rules.v1",
                retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
                evidence=[_evidence_ref(base_state["tenant_id"])],
                action_payload_hash=ACTION_HASH,
                created_at="2026-06-20T00:00:00.000Z",
                **{field_name: "SHOULD_NOT_LEAK_RANKING_DIAGNOSTICS"},
            )
