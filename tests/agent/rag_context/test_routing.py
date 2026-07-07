from __future__ import annotations

from typing import Any

import pytest


def _load_routing_api():
    from src.agent.rag_context.routing import VerificationRoute, determine_verification_route

    return VerificationRoute, determine_verification_route


def _value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _continue_bundle(*, claim_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "overall_status": "verified",
        "route": "continue",
        "claim_results": claim_results or [],
        "blocked_claims": [],
        "safe_support_refs": [],
        "reason_codes": [],
    }


def _allowed_action_claim_result() -> dict[str, Any]:
    return {
        "claim_id": "claim-action-1",
        "claim_type": "action_recommendation",
        "support_status": "supported",
        "supporting_evidence_refs": [],
        "business_fact_refs": [],
        "rule_checks": [{"rule": "policy_support_required", "passed": True}],
        "semantic_review_status": "not_needed",
        "allows_user_visible_claim": True,
        "allows_action_recommendation": True,
    }


@pytest.mark.parametrize(
    ("state", "expected_route"),
    [
        (
            {
                "overall_outcome": "supported",
                "reason_codes": [],
                "risk_level": "low",
            },
            "allow",
        ),
        (
            {
                "overall_outcome": "unsupported",
                "reason_codes": ["unsupported"],
                "regenerate_route_enabled": False,
            },
            "insufficient_evidence",
        ),
        (
            {
                "overall_outcome": "unsupported",
                "reason_codes": ["cited_but_unsupported"],
                "regenerate_route_enabled": True,
            },
            "regenerate_route",
        ),
        (
            {
                "overall_outcome": "insufficient",
                "reason_codes": ["missing_citation"],
            },
            "insufficient_evidence",
        ),
        (
            {
                "overall_outcome": "conflict",
                "reason_codes": ["conflicting_evidence"],
                "risk_level": "high",
            },
            "manual_review",
        ),
        (
            {
                "overall_outcome": "stale",
                "reason_codes": ["stale_evidence"],
                "risk_level": "high",
            },
            "manual_review",
        ),
        (
            {
                "overall_outcome": "unauthorized",
                "reason_codes": ["unauthorized_evidence"],
            },
            "refuse",
        ),
        (
            {
                "overall_outcome": "scope_invalid",
                "reason_codes": ["scope_invalid"],
            },
            "refuse",
        ),
        (
            {
                "overall_outcome": "hash_mismatch",
                "reason_codes": ["text_hash_mismatch"],
            },
            "refuse",
        ),
        (
            {
                "overall_outcome": "latest_version_invalid",
                "reason_codes": ["latest_version_invalid"],
            },
            "refuse",
        ),
        (
            {
                "overall_outcome": "ocr_low_confidence",
                "reason_codes": ["ocr_low_confidence"],
                "risk_level": "high",
            },
            "manual_review",
        ),
        (
            {
                "overall_outcome": "business_fact_missing",
                "reason_codes": ["business_fact_missing"],
                "authority_class": "action_recommendation_claim",
            },
            "insufficient_evidence",
        ),
        (
            {
                "overall_outcome": "needs_manual_review",
                "reason_codes": ["semantic_ambiguous"],
            },
            "manual_review",
        ),
    ],
)
def test_verification_route_matrix_is_backend_owned(state: dict[str, Any], expected_route: str) -> None:
    """RTE-01/RTE-02: non-allow outcomes map through deterministic backend code."""
    VerificationRoute, determine_verification_route = _load_routing_api()

    result = determine_verification_route(state)

    assert _value(result.route) == getattr(VerificationRoute, expected_route.upper()).value
    assert _value(result.route) == expected_route
    assert result.selected_by == "backend"
    assert result.model_selected is False
    assert "model" not in result.decision_source


@pytest.mark.parametrize(
    "state",
    [
        {"overall_outcome": "unsupported", "reason_codes": ["unsupported"]},
        {"overall_outcome": "insufficient", "reason_codes": ["missing_citation"]},
        {"overall_outcome": "conflict", "reason_codes": ["conflicting_evidence"]},
        {"overall_outcome": "stale", "reason_codes": ["stale_evidence"]},
        {"overall_outcome": "unauthorized", "reason_codes": ["unauthorized_evidence"]},
        {"overall_outcome": "scope_invalid", "reason_codes": ["scope_invalid"]},
        {"overall_outcome": "hash_mismatch", "reason_codes": ["text_hash_mismatch"]},
        {"overall_outcome": "latest_version_invalid", "reason_codes": ["latest_version_invalid"]},
        {"overall_outcome": "ocr_low_confidence", "reason_codes": ["ocr_low_confidence"]},
        {"overall_outcome": "business_fact_missing", "reason_codes": ["business_fact_missing"]},
        {"overall_outcome": "needs_manual_review", "reason_codes": ["manual_review_sensitive"]},
    ],
)
def test_non_allow_routes_block_action_approval_and_snapshot_boundaries(state: dict[str, Any]) -> None:
    """RTE-02: every non-allow route blocks actions, approvals, drafts, and snapshots."""
    _VerificationRoute, determine_verification_route = _load_routing_api()

    result = determine_verification_route(state)

    assert _value(result.route) != "allow"
    assert result.allow_recommendation is False
    assert result.allow_proposed_action is False
    assert result.allow_approval_request is False
    assert result.allow_action_draft is False
    assert result.allow_action_safety_snapshot_evidence is False


def test_regenerate_route_is_route_value_only_not_automatic_retry_loop() -> None:
    """RTE-01: regenerate_route is an enum/action value, not an automatic retry loop."""
    VerificationRoute, determine_verification_route = _load_routing_api()

    result = determine_verification_route(
        {
            "overall_outcome": "unsupported",
            "reason_codes": ["cited_but_unsupported"],
            "regenerate_route_enabled": True,
        }
    )

    assert _value(result.route) == VerificationRoute.REGENERATE_ROUTE.value
    assert result.regeneration_attempt_started is False
    assert result.regeneration_attempt_count == 0
    assert result.next_backend_action == "regenerate_route"


def test_route_after_recommendation_sends_claims_and_actions_to_claim_verify() -> None:
    """APF-14: material claims and action recommendations must pass through claim_verify."""
    from src.agent.routing import route_after_recommendation

    assert route_after_recommendation({"material_claims": [{"claim_id": "claim-policy"}]}) == "claim_verify"
    assert (
        route_after_recommendation(
            {"recommendation_draft": {"policy_claims": [{"claim_text": "Policy allows review."}]}}
        )
        == "claim_verify"
    )
    assert (
        route_after_recommendation(
            {"recommendation_draft": {"business_claims": [{"claim_text": "Refund case is eligible."}]}}
        )
        == "claim_verify"
    )
    assert route_after_recommendation({"proposed_action": {"type": "create_compensation_review"}}) == "claim_verify"
    assert (
        route_after_recommendation(
            {
                "recommendation_draft": {
                    "user_visible_claims": [
                        {"claim_type": "business_fact", "claim_text": "Refund case is eligible."}
                    ]
                }
            }
        )
        == "claim_verify"
    )
    assert route_after_recommendation({"recommendation_draft": {"recommended_action": "answer_only"}}) == (
        "final_response"
    )


@pytest.mark.parametrize(
    ("state", "expected_route"),
    [
        (
            {
                "claim_verification_bundle": _continue_bundle(),
                "proposed_action": {"type": "create_compensation_review"},
            },
            "final_response",
        ),
        (
            {
                "claim_verification_bundle": _continue_bundle(
                    claim_results=[_allowed_action_claim_result()]
                ),
                "proposed_action": {"type": "create_compensation_review"},
            },
            "risk_gate",
        ),
        (
            {
                "claim_verification_bundle": _continue_bundle(),
                "proposed_action": {"type": "create_compensation_review"},
                "risk_signals": ["approval_required"],
            },
            "final_response",
        ),
        (
            {"claim_verification_bundle": _continue_bundle()},
            "final_response",
        ),
        (
            {
                "recommendation_draft": {"recommended_action": "issue_coupon", "risk_level": "low"},
                "claim_verification_bundle": _continue_bundle(claim_results=[_allowed_action_claim_result()]),
            },
            "risk_gate",
        ),
        (
            {
                "claim_verification_bundle": _continue_bundle(
                    claim_results=[_allowed_action_claim_result()]
                ),
                "risk_signals": ["manual_review_required"],
            },
            "risk_gate",
        ),
        (
            {
                "claim_verification_bundle": {"overall_status": "manual_review", "route": "manual_review"},
                "proposed_action": {"type": "create_compensation_review"},
            },
            "final_response",
        ),
        (
            {
                "claim_verification_bundle": {"overall_status": "error", "route": "final_response"},
                "proposed_action": {"type": "create_compensation_review"},
            },
            "final_response",
        ),
        (
            {
                "claim_verification_bundle": {"overall_status": "verified", "route": "continue"},
                "blocked_claims": ["claim-business"],
                "proposed_action": {"type": "create_compensation_review"},
            },
            "final_response",
        ),
        (
            {
                "claim_verification_bundle": {
                    "overall_status": "blocked",
                    "route": "final_response",
                    "reason_codes": ["business_fact_ref_required"],
                },
                "proposed_action": {"type": "create_compensation_review"},
            },
            "final_response",
        ),
        ({}, "final_response"),
        ({"claim_verification_bundle": _continue_bundle()}, "final_response"),
    ],
)
def test_route_after_claim_verify_maps_bundle_routes_to_registered_graph_keys(
    state: dict[str, Any],
    expected_route: str,
) -> None:
    from src.agent.routing import route_after_claim_verify

    route = route_after_claim_verify(state)

    assert route == expected_route
    assert route in {"risk_gate", "final_response"}
    assert route != "continue"


def test_route_after_claim_verify_blocks_business_fact_and_unsupported_action_claims() -> None:
    """APF-14: blocked business fact claims and unsupported action_recommendation claims cannot reach risk."""
    from src.agent.routing import route_after_claim_verify

    assert (
        route_after_claim_verify(
            {
                "claim_verification_bundle": {
                    "overall_status": "blocked",
                    "route": "final_response",
                    "reason_codes": ["business_fact_ref_required"],
                },
                "blocked_claims": ["claim-business"],
                "proposed_action": {"type": "create_compensation_review"},
            }
        )
        == "final_response"
    )
    assert (
        route_after_claim_verify(
            {
                "claim_verification_bundle": {
                    "overall_status": "blocked",
                    "route": "final_response",
                    "reason_codes": ["unsupported_action_recommendation"],
                },
                "blocked_claims": ["claim-action"],
                "proposed_action": {"type": "create_compensation_review"},
            }
        )
        == "final_response"
    )


def test_route_after_claim_verify_sends_verified_action_recommendation_to_current_risk_node() -> None:
    """APF-14: verified actionable drafts must still bind action authority through risk/snapshot."""
    from src.agent.routing import route_after_claim_verify

    route = route_after_claim_verify(
        {
            "recommendation_draft": {
                "recommended_action": "issue_coupon",
                "risk_level": "low",
                "evidence_refs": [{"doc_key": "policy_refund_timeout", "chunk_id": "chunk_001"}],
            },
            "proposed_action": {"type": "create_compensation_review"},
            "claim_verification_bundle": _continue_bundle(claim_results=[_allowed_action_claim_result()]),
        }
    )

    assert route == "risk_gate"


@pytest.mark.parametrize(
    "state",
    [
        {"verification_route": "allow"},
        {"verification_route": "allow", "verifier_status": "verified", "verifier_reason_codes": []},
        {
            "verification_route": "allow",
            "claim_verification_bundle": {
                "overall_status": "blocked",
                "route": "final_response",
                "blocked_claims": ["claim-action-1"],
            },
        },
        {
            "verification_route": "allow",
            "claim_verification_bundle": {
                "overall_status": "verified",
                "route": "final_response",
                "blocked_claims": [],
            },
        },
    ],
)
def test_legacy_verifier_fields_cannot_override_canonical_claim_bundle_gate(
    state: dict[str, Any],
) -> None:
    from src.agent.routing import route_after_claim_verify

    state = {"proposed_action": {"type": "create_compensation_review"}, **state}

    assert route_after_claim_verify(state) == "final_response"
