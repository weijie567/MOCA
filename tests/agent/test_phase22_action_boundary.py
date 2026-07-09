from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from src.agent.graph import route_after_risk
from src.agent.nodes.action_draft import action_draft
from src.agent.nodes import risk_gate as risk_gate_module
from src.approvals.snapshots import build_action_safety_snapshot
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1


ACTION_HASH = "sha256:" + "1" * 64
SNAPSHOT_HASH = "sha256:" + "2" * 64


def test_phase58_action_boundary_patches_canonical_risk_gate_module() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    legacy_alias = "assess_" "risk_module"
    legacy_resume_route = "assess_" "risk_and_approval"

    assert legacy_alias not in source
    assert f'"resume_route": "{legacy_resume_route}"' not in source
    assert "from src.agent.nodes import risk_gate as risk_gate_module" in source


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


def _claim_result(*, allows_action_recommendation: bool, support_status: str = "unsupported") -> dict[str, Any]:
    return {
        "schema_version": "claim_verification_result.v1",
        "claim_id": "claim-action-1",
        "claim_type": "action_recommendation",
        "support_status": support_status,
        "supporting_evidence_refs": [],
        "business_fact_refs": [],
        "rule_checks": [],
        "semantic_review_status": "not_needed",
        "allows_user_visible_claim": allows_action_recommendation,
        "allows_action_recommendation": allows_action_recommendation,
    }


def _policy_claim_result() -> dict[str, Any]:
    return {
        "schema_version": "claim_verification_result.v1",
        "claim_id": "claim-policy-1",
        "claim_type": "policy",
        "support_status": "supported",
        "supporting_evidence_refs": [],
        "business_fact_refs": [],
        "rule_checks": [],
        "semantic_review_status": "not_needed",
        "allows_user_visible_claim": True,
        "allows_action_recommendation": False,
    }


def _claim_bundle(
    *,
    route: str = "continue",
    overall_status: str = "verified",
    blocked_claims: list[str] | None = None,
    claim_results: list[dict[str, Any]] | None = None,
    safe_support_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "claim_verification_bundle.v1",
        "overall_status": overall_status,
        "route": route,
        "claim_results": claim_results or [],
        "blocked_claims": blocked_claims or [],
        "safe_support_refs": safe_support_refs or [],
        "reason_codes": [],
        "verifier_policy_version": "claim-verifier.v1",
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


def _claim_verified_actionable_state(base_state: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
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
        },
        "business_context": {
            "order": {"id": "order-1", "order_no": "ORD-1001", "status": "delivered"},
            "refund_case": {"id": "refund-1", "refund_case_no": "RF-1001", "requested_amount": "100.00"},
        },
        "claim_verification_bundle": bundle,
        "blocked_claims": list(bundle.get("blocked_claims") or []),
        "safe_support_refs": list(bundle.get("safe_support_refs") or []),
        "verification_route": "allow",
    }


class ExplodingRiskLLM:
    def with_structured_output(self, schema: type[Any]) -> Any:
        raise AssertionError("non-allow verifier outcomes must block before risk LLM or action proposal")


class _AllowingRiskLLM:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def with_structured_output(self, schema: type[Any]) -> Any:
        response = self.response

        class _Wrapper:
            async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
                return schema.model_validate(response)

        return _Wrapper()


class ExplodingActionToolPlatform:
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
    monkeypatch.setattr(risk_gate_module, "_get_llm", lambda: ExplodingRiskLLM())

    result = await risk_gate_module.risk_gate(
        _actionable_state(base_state, outcome=outcome, route=route),
        {"configurable": {"session": object()}},
    )

    assert result["proposed_action"] is None
    assert result.get("action_payload_hash") is None
    assert result.get("safety_snapshot_ref") is None
    assert result.get("safety_snapshot_hash") is None
    assert result.get("safety_snapshot_verified") is not True
    assert result["risk_assessment"]["approval_required"] is False
    expected_dispositions = {
        "insufficient_evidence": "allow",
        "manual_review": "manual_review",
        "refuse": "blocked",
    }
    expected_severities = {
        "insufficient_evidence": "low",
        "manual_review": "medium",
        "refuse": "high",
    }
    assert result["risk_assessment"]["risk_level"] == expected_severities[route]
    assert result["risk_assessment"]["risk_severity"] == expected_severities[route]
    assert result["risk_assessment"]["risk_disposition"] == expected_dispositions[route]
    assert result["rag_verification"]["route"]["selected_by"] == "backend"
    assert result["rag_verification"]["route"]["model_selected"] is False


@pytest.mark.asyncio
async def test_non_allow_risk_assessment_clears_same_turn_stale_snapshot_bindings(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """RTE-04: non-allow verifier updates must clear any stale action binding in state merge."""
    monkeypatch.setattr(risk_gate_module, "_get_llm", lambda: ExplodingRiskLLM())
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

    result = await risk_gate_module.risk_gate(
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bundle",
    [
        _claim_bundle(route="manual_review", overall_status="manual_review"),
        _claim_bundle(route="final_response", overall_status="blocked", blocked_claims=["claim-action-1"]),
    ],
)
async def test_claim_bundle_blockers_clear_same_turn_action_capable_state(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
    bundle: dict[str, Any],
) -> None:
    """APF-14: claim bundle blockers are authoritative even when legacy route is allow."""
    monkeypatch.setattr(risk_gate_module, "_get_llm", lambda: ExplodingRiskLLM())
    state = {
        **_claim_verified_actionable_state(base_state, bundle),
        "proposed_action": {"action_type": "issue_coupon"},
        "approval_plan": {"plan_id": "stale-plan"},
        "approval_result": _approved_result(base_state["tenant_id"], str(uuid4())),
        "action_draft": {"draft_id": "stale-draft"},
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:stale",
        "safety_snapshot_hash": SNAPSHOT_HASH,
        "safety_snapshot_verified": True,
    }

    result = await risk_gate_module.risk_gate(
        state,
        {"configurable": {"session": object()}},
    )
    merged_state = {**state, **result}

    assert merged_state["proposed_action"] is None
    assert merged_state["approval_plan"] is None
    assert merged_state["approval_result"] is None
    assert merged_state["action_draft"] is None
    assert merged_state["action_payload_hash"] is None
    assert merged_state["safety_snapshot_ref"] is None
    assert merged_state["safety_snapshot_hash"] is None
    assert merged_state["safety_snapshot_verified"] is False
    assert route_after_risk(merged_state) == "final_response"


@pytest.mark.asyncio
async def test_action_claim_result_disallowing_action_blocks_risk_and_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """APF-14: action claim results with allows_action_recommendation=False fail closed."""
    monkeypatch.setattr(risk_gate_module, "_get_llm", lambda: ExplodingRiskLLM())
    bundle = _claim_bundle(
        claim_results=[_claim_result(allows_action_recommendation=False)],
        safe_support_refs=[_evidence_ref(base_state["tenant_id"])],
    )

    result = await risk_gate_module.risk_gate(
        _claim_verified_actionable_state(base_state, bundle),
        {"configurable": {"session": object()}},
    )

    assert result["proposed_action"] is None
    assert result.get("action_payload_hash") is None
    assert result.get("safety_snapshot_ref") is None
    assert result.get("safety_snapshot_hash") is None
    assert result.get("safety_snapshot_verified") is False


@pytest.mark.asyncio
async def test_missing_positive_action_claim_blocks_approval_edit_risk_reentry(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """APF-14: approval edit re-entry still requires a positive action claim allowance."""
    monkeypatch.setattr(risk_gate_module, "_get_llm", lambda: ExplodingRiskLLM())
    run_id = str(uuid4())
    edited_action = {
        "schema_version": "proposed_action.v1",
        "tenant_id": base_state["tenant_id"],
        "run_id": run_id,
        "action_id": f"act:{run_id}:issue_coupon:refund-1",
        "action_type": "issue_coupon",
        "target_type": "refund_case",
        "target_id": "refund-1",
        "amount": "88.00",
        "currency": "CNY",
        "args": {"risk_level": "high"},
        "reason": "Reviewer edited the coupon amount.",
        "evidence_refs": [_evidence_ref(base_state["tenant_id"])],
    }
    bundle = _claim_bundle(claim_results=[], safe_support_refs=[_evidence_ref(base_state["tenant_id"])])
    state = {
        **_claim_verified_actionable_state(base_state, bundle),
        "current_run_id": run_id,
        "proposed_action": {"action_type": "issue_coupon"},
        "approval_result": {
            **_approved_result(base_state["tenant_id"], run_id),
            "decision_type": "edit",
            "status": "superseded",
            "edited_action": edited_action,
            "new_action_payload_hash": "sha256:" + "3" * 64,
            "resume_route": "risk_gate",
        },
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
        "safety_snapshot_verified": True,
    }

    result = await risk_gate_module.risk_gate(
        state,
        {"configurable": {"session": object()}},
    )
    merged_state = {**state, **result}

    assert result["risk_assessment"]["rule_ref"] == "PHASE33-CLAIM-VERIFY"
    assert merged_state["proposed_action"] is None
    assert merged_state["approval_result"] is None
    assert merged_state["action_payload_hash"] is None
    assert merged_state["safety_snapshot_ref"] is None
    assert merged_state["safety_snapshot_hash"] is None
    assert merged_state["safety_snapshot_verified"] is False
    assert route_after_risk(merged_state) == "final_response"


@pytest.mark.asyncio
async def test_candidate_only_retrieved_evidence_refs_do_not_bind_action_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """APF-13/APF-14: candidate-only retrieved_evidence refs are not action snapshot evidence."""
    monkeypatch.setattr(
        risk_gate_module,
        "_get_llm",
        lambda: _AllowingRiskLLM(
            {
                "risk_level": "low",
                "risk_reason": "standard compensation",
                "approval_required": False,
                "rule_ref": "LR-01",
            }
        ),
    )
    candidate_ref = _evidence_ref(base_state["tenant_id"])
    bundle = _claim_bundle(claim_results=[_claim_result(allows_action_recommendation=True, support_status="supported")])
    state = {
        **_claim_verified_actionable_state(base_state, bundle),
        "current_run_id": None,
        "retrieved_evidence": {"evidence_refs": [candidate_ref]},
    }

    result = await risk_gate_module.risk_gate(state)

    proposed_refs = (result.get("proposed_action") or {}).get("evidence_refs") or []
    assert candidate_ref["evidence_id"] not in {ref.get("evidence_id") for ref in proposed_refs}
    assert candidate_ref["evidence_id"] not in {
        ref.get("evidence_id") for ref in result.get("evidence_refs") or [] if isinstance(ref, dict)
    }


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
        {"configurable": {"session": object(), "action_tool_platform": ExplodingActionToolPlatform()}},
    )

    assert result.get("action_draft") is None
    assert result.get("draft_outcome") is None
    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "VERIFIER_NOT_ALLOW"


@pytest.mark.asyncio
async def test_action_draft_node_refuses_when_claim_bundle_route_blocks_action(
    base_state: dict[str, Any],
) -> None:
    """APF-14: action_draft reads claim_verification_bundle blockers, not candidate refs."""
    run_id = str(uuid4())
    bundle = _claim_bundle(route="final_response", overall_status="blocked", blocked_claims=["claim-action-1"])
    state = {
        **base_state,
        "current_run_id": run_id,
        "claim_verification_bundle": bundle,
        "blocked_claims": ["claim-action-1"],
        "risk_assessment": {"approval_required": True, "risk_level": "high"},
        "proposed_action": {"action_type": "issue_coupon", "target_type": "refund_case", "target_id": "RF-1001"},
        "approval_result": _approved_result(base_state["tenant_id"], run_id),
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
    }

    result = await action_draft(
        state,
        {"configurable": {"session": object(), "action_tool_platform": ExplodingActionToolPlatform()}},
    )

    assert result.get("action_draft") is None
    assert result.get("draft_outcome") is None
    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "VERIFIER_NOT_ALLOW"


@pytest.mark.asyncio
@pytest.mark.parametrize("claim_results", [[], [_policy_claim_result()]])
async def test_action_draft_node_requires_positive_action_claim_before_tool_call(
    base_state: dict[str, Any],
    claim_results: list[dict[str, Any]],
) -> None:
    """APF-14: final action-draft writes require an allowed action_recommendation claim."""
    run_id = str(uuid4())
    bundle = _claim_bundle(claim_results=claim_results)
    state = {
        **base_state,
        "current_run_id": run_id,
        "claim_verification_bundle": bundle,
        "blocked_claims": [],
        "verification_route": "allow",
        "risk_assessment": {"approval_required": True, "risk_level": "high"},
        "proposed_action": {"action_type": "issue_coupon", "target_type": "refund_case", "target_id": "RF-1001"},
        "approval_result": _approved_result(base_state["tenant_id"], run_id),
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
    }

    result = await action_draft(
        state,
        {"configurable": {"session": object(), "action_tool_platform": ExplodingActionToolPlatform()}},
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
