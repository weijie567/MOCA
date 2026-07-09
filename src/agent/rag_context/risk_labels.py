"""Canonical RAG evidence risk label registry.

Risk labels are prompt-safe evidence/context labels such as
``manual_review_sensitive``. Route reason codes such as
``semantic_provider_timeout`` are not risk labels; they are grouped here only
when directly coupled to RAG verifier, routing, or metrics semantics.
"""

from __future__ import annotations

from typing import Any


SAFE_EVIDENCE_RISK_LABELS = frozenset(
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
PROMPT_SAFE_RISK_LABELS = SAFE_EVIDENCE_RISK_LABELS
SEMANTIC_REVIEW_RISK_LABELS = frozenset(
    {
        "conflict",
        "manual_review_sensitive",
        "ocr_low_confidence",
        "stale_evidence",
    }
)
MANUAL_REVIEW_TRIGGER_RISK_LABELS = SEMANTIC_REVIEW_RISK_LABELS
ROUTING_RISK_LABELS = frozenset(
    {
        "conflict",
        "manual_review_sensitive",
        "ocr_low_confidence",
        "stale_evidence",
    }
)
METRIC_LEVEL3_TRIGGER_LABELS = frozenset(
    {
        "high_risk",
        "manual_review_sensitive",
        "semantic_malformed_output",
        "semantic_provider_error",
        "semantic_timeout",
    }
)
ROUTE_MANUAL_REVIEW_REASONS = frozenset(
    {
        "conflict",
        "conflicting_evidence",
        "level2_partial_overlap_ambiguous",
        "manual_review_sensitive",
        "needs_semantic_review",
        "semantic_ambiguous",
        "semantic_budget_claim_count_exceeded",
        "semantic_budget_evidence_count_exceeded",
        "semantic_budget_input_chars_exceeded",
        "semantic_provider_error",
        "semantic_provider_malformed",
        "semantic_provider_timeout",
    }
)
ROUTE_STALE_OR_OCR_REASONS = frozenset(
    {
        "effective_date_invalid",
        "freshness_invalid",
        "ocr_low_confidence",
        "stale_evidence",
    }
)


class RagRiskLabelRegistry:
    """Read-only owner for RAG risk label and coupled route-trigger groups."""

    def safe_evidence_risk_labels(self) -> frozenset[str]:
        return SAFE_EVIDENCE_RISK_LABELS

    def prompt_safe_risk_labels(self) -> frozenset[str]:
        return PROMPT_SAFE_RISK_LABELS

    def semantic_review_risk_labels(self) -> frozenset[str]:
        return SEMANTIC_REVIEW_RISK_LABELS

    def manual_review_trigger_risk_labels(self) -> frozenset[str]:
        return MANUAL_REVIEW_TRIGGER_RISK_LABELS

    def routing_risk_labels(self) -> frozenset[str]:
        return ROUTING_RISK_LABELS

    def metric_level3_trigger_labels(self) -> frozenset[str]:
        return METRIC_LEVEL3_TRIGGER_LABELS

    def route_manual_review_reasons(self) -> frozenset[str]:
        return ROUTE_MANUAL_REVIEW_REASONS

    def route_stale_or_ocr_reasons(self) -> frozenset[str]:
        return ROUTE_STALE_OR_OCR_REASONS


RAG_RISK_LABEL_REGISTRY = RagRiskLabelRegistry()


def filter_safe_evidence_risk_labels(labels: Any) -> list[str]:
    return _filtered_unique_labels(labels, SAFE_EVIDENCE_RISK_LABELS)


def filter_prompt_safe_risk_labels(labels: Any) -> list[str]:
    return _filtered_unique_labels(labels, PROMPT_SAFE_RISK_LABELS)


def is_prompt_safe_risk_label(label: Any) -> bool:
    return str(label or "") in PROMPT_SAFE_RISK_LABELS


def requires_semantic_review_for_risk_hints(labels: Any) -> bool:
    return bool(set(_string_labels(labels)) & SEMANTIC_REVIEW_RISK_LABELS)


def routing_risk_labels() -> frozenset[str]:
    return ROUTING_RISK_LABELS


def metric_level3_trigger_labels() -> frozenset[str]:
    return METRIC_LEVEL3_TRIGGER_LABELS


def _filtered_unique_labels(labels: Any, allowed_labels: frozenset[str]) -> list[str]:
    result: list[str] = []
    for label in _string_labels(labels):
        if label in allowed_labels and label not in result:
            result.append(label)
    return result


def _string_labels(labels: Any) -> list[str]:
    if isinstance(labels, str | bytes):
        return [str(labels)] if str(labels) else []
    try:
        iterator = iter(labels)
    except TypeError:
        return []
    return [str(label) for label in iterator if str(label)]


__all__ = [
    "MANUAL_REVIEW_TRIGGER_RISK_LABELS",
    "METRIC_LEVEL3_TRIGGER_LABELS",
    "PROMPT_SAFE_RISK_LABELS",
    "RAG_RISK_LABEL_REGISTRY",
    "ROUTE_MANUAL_REVIEW_REASONS",
    "ROUTE_STALE_OR_OCR_REASONS",
    "ROUTING_RISK_LABELS",
    "SAFE_EVIDENCE_RISK_LABELS",
    "SEMANTIC_REVIEW_RISK_LABELS",
    "RagRiskLabelRegistry",
    "filter_prompt_safe_risk_labels",
    "filter_safe_evidence_risk_labels",
    "is_prompt_safe_risk_label",
    "metric_level3_trigger_labels",
    "requires_semantic_review_for_risk_hints",
    "routing_risk_labels",
]
