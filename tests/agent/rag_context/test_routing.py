from __future__ import annotations

from typing import Any

import pytest


def _load_routing_api():
    from src.agent.rag_context.routing import VerificationRoute, determine_verification_route

    return VerificationRoute, determine_verification_route


def _value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


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
