from __future__ import annotations

import pytest

from src.agent.rag_context.risk_labels import (
    MANUAL_REVIEW_TRIGGER_RISK_LABELS,
    METRIC_LEVEL3_TRIGGER_LABELS,
    PROMPT_SAFE_RISK_LABELS,
    RAG_RISK_LABEL_REGISTRY,
    ROUTE_MANUAL_REVIEW_REASONS,
    ROUTE_STALE_OR_OCR_REASONS,
    ROUTING_RISK_LABELS,
    SAFE_EVIDENCE_RISK_LABELS,
    SEMANTIC_REVIEW_RISK_LABELS,
    filter_prompt_safe_risk_labels,
    filter_safe_evidence_risk_labels,
    is_prompt_safe_risk_label,
    metric_level3_trigger_labels,
    requires_semantic_review_for_risk_hints,
    routing_risk_labels,
)


EXPECTED_COMPATIBLE_RISK_LABELS = frozenset(
    {
        "authority_checked",
        "conflict",
        "freshness_risk",
        "high_risk",
        "latest_version_checked",
        "manual_review_sensitive",
        "ocr_low_confidence",
        "provenance_available",
        "source_locator_available",
        "stale_evidence",
    }
)


def test_registry_preserves_existing_label_strings() -> None:
    assert SAFE_EVIDENCE_RISK_LABELS == EXPECTED_COMPATIBLE_RISK_LABELS
    assert PROMPT_SAFE_RISK_LABELS == EXPECTED_COMPATIBLE_RISK_LABELS
    assert RAG_RISK_LABEL_REGISTRY.safe_evidence_risk_labels() == EXPECTED_COMPATIBLE_RISK_LABELS
    assert RAG_RISK_LABEL_REGISTRY.prompt_safe_risk_labels() == EXPECTED_COMPATIBLE_RISK_LABELS


def test_manual_review_sensitive_is_available_to_all_trigger_surfaces() -> None:
    assert "manual_review_sensitive" in PROMPT_SAFE_RISK_LABELS
    assert "manual_review_sensitive" in SEMANTIC_REVIEW_RISK_LABELS
    assert "manual_review_sensitive" in MANUAL_REVIEW_TRIGGER_RISK_LABELS
    assert "manual_review_sensitive" in ROUTING_RISK_LABELS
    assert "manual_review_sensitive" in METRIC_LEVEL3_TRIGGER_LABELS
    assert "manual_review_sensitive" in routing_risk_labels()
    assert "manual_review_sensitive" in metric_level3_trigger_labels()
    assert requires_semantic_review_for_risk_hints(["manual_review_sensitive"])


def test_filter_helpers_preserve_order_dedupe_and_drop_unknown_labels() -> None:
    labels = [
        "high_risk",
        "raw_debug_secret",
        "manual_review_sensitive",
        "high_risk",
        "",
        "stale_evidence",
    ]

    assert filter_safe_evidence_risk_labels(labels) == [
        "high_risk",
        "manual_review_sensitive",
        "stale_evidence",
    ]
    assert filter_prompt_safe_risk_labels(labels) == [
        "high_risk",
        "manual_review_sensitive",
        "stale_evidence",
    ]
    assert not is_prompt_safe_risk_label("raw_debug_secret")


def test_semantic_review_helper_uses_registry_owned_trigger_labels() -> None:
    assert requires_semantic_review_for_risk_hints(["conflict"])
    assert requires_semantic_review_for_risk_hints(["stale_evidence"])
    assert requires_semantic_review_for_risk_hints(["ocr_low_confidence"])
    assert requires_semantic_review_for_risk_hints(["manual_review_sensitive"])
    assert not requires_semantic_review_for_risk_hints(["authority_checked", "raw_debug_secret"])


def test_route_reason_codes_are_not_prompt_safe_risk_labels() -> None:
    assert "semantic_provider_timeout" in ROUTE_MANUAL_REVIEW_REASONS
    assert "semantic_provider_timeout" not in SAFE_EVIDENCE_RISK_LABELS
    assert "semantic_provider_timeout" not in PROMPT_SAFE_RISK_LABELS
    assert "semantic_timeout" in METRIC_LEVEL3_TRIGGER_LABELS
    assert "freshness_invalid" in ROUTE_STALE_OR_OCR_REASONS

    doc = RAG_RISK_LABEL_REGISTRY.__class__.__module__
    module_doc = __import__(doc, fromlist=["__doc__"]).__doc__ or ""
    assert "not risk labels" in module_doc


def test_public_groups_are_immutable() -> None:
    with pytest.raises(AttributeError):
        SAFE_EVIDENCE_RISK_LABELS.add("raw_debug_secret")  # type: ignore[attr-defined]
