from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from src.agent.safety.taxonomy import (
    EXECUTABLE_ACTION_TYPES,
    NON_EXECUTABLE_DISPOSITIONS,
    RISK_DISPOSITIONS,
    RISK_SEVERITIES,
    SAFETY_TAXONOMY,
    ActionResolution,
    PreRouteActionMatch,
    RiskVocabulary,
    action_aliases_for,
    canonical_executable_action_type,
    detect_pre_route_action_request,
    is_actionable_recommendation,
    is_executable_action_type,
    matches_compensation_alias,
    matches_full_refund_alias,
    normalize_risk_vocabulary,
    pre_route_action_aliases,
    resolve_action_text,
    risk_assessment_with_disposition,
)


def test_public_collections_and_registry_views_are_immutable() -> None:
    assert EXECUTABLE_ACTION_TYPES == frozenset(
        {"issue_coupon", "approve_refund", "full_refund", "partial_refund"}
    )
    assert NON_EXECUTABLE_DISPOSITIONS == frozenset({"manual_review", "blocked"})
    assert RISK_SEVERITIES == frozenset({"low", "medium", "high"})
    assert {"allow", "approval_required", "manual_review", "blocked"}.issubset(RISK_DISPOSITIONS)

    with pytest.raises(AttributeError):
        EXECUTABLE_ACTION_TYPES.add("manual_review")  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        SAFETY_TAXONOMY.executable_actions()["issue_coupon"] = object()  # type: ignore[index]
    with pytest.raises(TypeError):
        pre_route_action_aliases()["direct_execution"] = frozenset()  # type: ignore[index]


def test_manual_review_and_blocked_are_dispositions_not_actions() -> None:
    for disposition in ("manual_review", "blocked"):
        assert disposition in NON_EXECUTABLE_DISPOSITIONS
        assert disposition not in EXECUTABLE_ACTION_TYPES
        assert is_executable_action_type(disposition) is False
        assert canonical_executable_action_type(disposition) is None
        assert is_actionable_recommendation(disposition) is False


@pytest.mark.parametrize(
    ("raw_action", "expected"),
    [
        ("issue_coupon", "issue_coupon"),
        ("approve_refund", "approve_refund"),
        ("full_refund", "full_refund"),
        ("全额退款", "full_refund"),
        ("全额退", "full_refund"),
        ("整单退款", "full_refund"),
        ("full refund", "full_refund"),
        ("partial_refund", "partial_refund"),
        ("部分退款", "partial_refund"),
        ("refund", "approve_refund"),
        ("退款", "approve_refund"),
    ],
)
def test_refund_and_coupon_aliases_preserve_current_input_acceptance(raw_action: str, expected: str) -> None:
    resolution = resolve_action_text(raw_action)

    assert resolution.executable_action_type == expected
    assert resolution.disposition is None
    assert canonical_executable_action_type(raw_action) == expected
    assert is_executable_action_type(expected) is True
    assert is_actionable_recommendation(raw_action) is True


@pytest.mark.parametrize("raw_action", ["compensation", "compensate", "coupon", "补偿", "券", "赔付"])
def test_compensation_aliases_resolve_to_issue_coupon_not_new_write_tool(raw_action: str) -> None:
    resolution = resolve_action_text(raw_action)

    assert "compensation" not in EXECUTABLE_ACTION_TYPES
    assert resolution.executable_action_type == "issue_coupon"
    assert resolution.disposition is None
    assert canonical_executable_action_type(raw_action) == "issue_coupon"
    assert matches_compensation_alias(raw_action) is True


@pytest.mark.parametrize("raw_action", ["reject", "拒绝", "不建议", "无法支持"])
def test_reject_and_no_support_text_resolve_to_manual_review_disposition(raw_action: str) -> None:
    resolution = resolve_action_text(raw_action)

    assert resolution.executable_action_type is None
    assert resolution.disposition == "manual_review"
    assert resolution.matched_alias is not None
    assert resolution.match_kind == "disposition"
    assert canonical_executable_action_type(raw_action) is None
    assert is_actionable_recommendation(raw_action) is False


@pytest.mark.parametrize(
    ("payload", "expected_disposition"),
    [
        ({"risk_level": "manual_review", "approval_required": False}, "manual_review"),
        ({"risk_level": "blocked", "approval_required": False}, "blocked"),
        ({"risk_level": "high", "approval_required": True}, "approval_required"),
        ({"risk_level": "low", "approval_required": False}, "allow"),
    ],
)
def test_legacy_risk_level_values_normalize_to_explicit_dispositions(
    payload: dict[str, object],
    expected_disposition: str,
) -> None:
    vocabulary = normalize_risk_vocabulary(payload)
    normalized_payload = risk_assessment_with_disposition(payload)

    assert isinstance(vocabulary, RiskVocabulary)
    assert vocabulary.risk_severity in RISK_SEVERITIES
    assert vocabulary.risk_disposition == expected_disposition
    assert normalized_payload["risk_level"] in RISK_SEVERITIES
    assert normalized_payload["risk_severity"] == vocabulary.risk_severity
    assert normalized_payload["risk_disposition"] == expected_disposition
    if payload["risk_level"] in {"manual_review", "blocked"}:
        assert normalized_payload["legacy_risk_level"] == payload["risk_level"]


@pytest.mark.parametrize(
    ("text", "expected_alias"),
    [
        ("please execute the approved refund now", "execute"),
        ("refund now for ORD-7001", "refund now"),
        ("override the current decision", "override"),
        ("请对ORD-7001直接退款", "直接退款"),
        ("请为这个订单发券", "发券"),
        ("创建补偿方案", "创建"),
    ],
)
def test_pre_route_action_matching_covers_existing_direct_action_terms(
    text: str,
    expected_alias: str,
) -> None:
    match = detect_pre_route_action_request(text)

    assert isinstance(match, PreRouteActionMatch)
    assert match.matched_alias == expected_alias
    assert match.requested_operation == "execute_action"
    assert match.reason_code == "critical_write"


@pytest.mark.parametrize("text", ["approve APR-1", "通过审批 APR-1", "reject approval request"])
def test_pre_route_action_matching_keeps_approval_chat_hard_negatives(text: str) -> None:
    assert detect_pre_route_action_request(text) is None


def test_read_only_alias_helpers_expose_registry_owned_aliases() -> None:
    full_refund_aliases = action_aliases_for("full_refund")
    coupon_aliases = action_aliases_for("issue_coupon")
    pre_route_aliases = pre_route_action_aliases()

    assert {"full_refund", "全额退款", "全额退", "整单退款", "full refund"}.issubset(full_refund_aliases)
    assert {"compensation", "compensate", "coupon", "补偿", "券", "赔付"}.issubset(coupon_aliases)
    assert {"direct_execution", "refund", "coupon"}.issubset(pre_route_aliases)
    assert matches_full_refund_alias("请全额退款") is True
    assert matches_compensation_alias("请给用户补偿券") is True

    with pytest.raises(AttributeError):
        full_refund_aliases.add("another")  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        pre_route_aliases["refund"] = frozenset()  # type: ignore[index]


def test_action_resolution_exposes_stable_branching_fields() -> None:
    assert [field.name for field in fields(ActionResolution)] == [
        "raw_value",
        "executable_action_type",
        "disposition",
        "matched_alias",
        "match_kind",
    ]

    full_refund = resolve_action_text("full refund")
    rejected = resolve_action_text("拒绝")

    assert isinstance(full_refund, ActionResolution)
    assert full_refund.raw_value == "full refund"
    assert full_refund.executable_action_type == "full_refund"
    assert full_refund.disposition is None
    assert full_refund.matched_alias == "full refund"
    assert full_refund.match_kind == "alias"

    assert rejected.raw_value == "拒绝"
    assert rejected.executable_action_type is None
    assert rejected.disposition == "manual_review"
    assert rejected.matched_alias == "拒绝"
    assert rejected.match_kind == "disposition"

    with pytest.raises(FrozenInstanceError):
        full_refund.executable_action_type = "issue_coupon"  # type: ignore[misc]
