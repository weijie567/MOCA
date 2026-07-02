"""Shared safety/write policy for memory surfaces."""

from __future__ import annotations

from typing import Literal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


MEMORY_POLICY_VERSION = "memory_write_policy.v1"
MEMORY_POLICY_AUTHORITY_CLASS = "contextual_only"

MemoryPolicyMemoryType = Literal["session", "long_term", "case", "case_working_context"]


class MemoryPolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["memory_policy_decision.v1"] = "memory_policy_decision.v1"
    memory_type: MemoryPolicyMemoryType
    decision: Literal["write", "needs_review", "skip"]
    review_status: str | None = None
    reason_code: str
    policy_version: str = MEMORY_POLICY_VERSION
    blocked_by: list[str] = Field(default_factory=list)
    authority_class: Literal["contextual_only"] = MEMORY_POLICY_AUTHORITY_CLASS


PROMPT_SAFE_PII_CLASSIFICATIONS = frozenset({"none", "low"})
BLOCKED_MEMORY_WRITE_PII_CLASSIFICATIONS = frozenset({"sensitive", "prohibited"})
AUTO_APPROVED_LONG_TERM_SOURCE_TYPES = frozenset(
    {
        "explicit_user_preference",
        "explicit_admin_preference",
        "human_reviewed",
        "deterministic_tool_result",
        "confirmed_business_outcome",
        "approved_approval_state",
    }
)
AUTO_APPROVED_DURABLE_LONG_TERM_SOURCE_TYPES = frozenset(
    {
        "deterministic_tool_result",
        "confirmed_business_outcome",
        "approved_approval_state",
    }
)
REVIEW_REQUIRED_LONG_TERM_SOURCE_TYPES = frozenset(
    {
        "llm_candidate",
        "semantic_episode_candidate",
        "summary_candidate",
        "cross_case_pattern_candidate",
        "behavior_inference",
    }
)
CURRENT_BUSINESS_OBJECT_TYPES = frozenset(
    {
        "order",
        "refund",
        "refund_case",
        "ticket",
        "logistics",
        "approval",
        "action",
        "coupon",
        "payment",
    }
)
AUTO_APPROVED_CASE_SOURCE_TYPES = frozenset(
    {
        "explicit_admin_preference",
        "human_reviewed",
    }
)
REVIEW_REQUIRED_CASE_SOURCE_TYPES = frozenset(
    {
        "deterministic_tool_result",
        "confirmed_business_outcome",
        "approved_approval_state",
        "llm_candidate",
        "semantic_episode_candidate",
        "summary_candidate",
        "cross_case_pattern_candidate",
        "behavior_inference",
    }
)


def is_prompt_safe_pii_classification(value: str | None) -> bool:
    return value in PROMPT_SAFE_PII_CLASSIFICATIONS


def is_blocked_memory_write_pii_classification(value: str | None) -> bool:
    return value in BLOCKED_MEMORY_WRITE_PII_CLASSIFICATIONS


def session_memory_policy_decision(pii_classification: str | None) -> MemoryPolicyDecision:
    if is_blocked_memory_write_pii_classification(pii_classification):
        return MemoryPolicyDecision(
            memory_type="session",
            decision="skip",
            review_status=None,
            reason_code="pii_blocked",
            blocked_by=["pii_classification"],
        )
    return MemoryPolicyDecision(
        memory_type="session",
        decision="write",
        review_status="auto_approved",
        reason_code="eligible",
    )


def long_term_memory_policy_decision(
    source_type: str,
    source_ref: Any | None = None,
    *,
    pii_classification: str | None = None,
) -> MemoryPolicyDecision:
    if is_blocked_memory_write_pii_classification(pii_classification):
        return MemoryPolicyDecision(
            memory_type="long_term",
            decision="skip",
            review_status=None,
            reason_code="pii_blocked",
            blocked_by=["pii_classification"],
        )

    if source_type in AUTO_APPROVED_DURABLE_LONG_TERM_SOURCE_TYPES:
        business_object_type = _source_ref_business_object_type(source_ref)
        if business_object_type is None:
            return _needs_review("long_term", blocked_by=["missing_business_object_metadata"])
        if business_object_type in CURRENT_BUSINESS_OBJECT_TYPES:
            return _needs_review("long_term", blocked_by=["current_business_object_state"])

    if source_type in AUTO_APPROVED_LONG_TERM_SOURCE_TYPES:
        return MemoryPolicyDecision(
            memory_type="long_term",
            decision="write",
            review_status="auto_approved",
            reason_code="auto_approved_source",
        )
    if source_type in REVIEW_REQUIRED_LONG_TERM_SOURCE_TYPES:
        return _needs_review("long_term", blocked_by=["source_requires_review"])
    return _needs_review("long_term", blocked_by=["unknown_source_type"])


def case_memory_policy_decision(
    source_type: str,
    source_ref: Any | None = None,
    *,
    pii_classification: str | None = None,
) -> MemoryPolicyDecision:
    del source_ref
    if is_blocked_memory_write_pii_classification(pii_classification):
        return MemoryPolicyDecision(
            memory_type="case",
            decision="skip",
            review_status=None,
            reason_code="pii_blocked",
            blocked_by=["pii_classification"],
        )
    if source_type in AUTO_APPROVED_CASE_SOURCE_TYPES:
        return MemoryPolicyDecision(
            memory_type="case",
            decision="write",
            review_status="auto_approved",
            reason_code="auto_approved_source",
        )
    if source_type in REVIEW_REQUIRED_CASE_SOURCE_TYPES:
        return _needs_review("case", blocked_by=["source_requires_review"])
    return _needs_review("case", blocked_by=["unknown_source_type"])


def long_term_review_status_for_source(source_type: str, source_ref: Any | None = None) -> str:
    return long_term_memory_policy_decision(source_type, source_ref).review_status or "needs_review"


def case_memory_review_status_for_source(source_type: str, source_ref: Any | None = None) -> str:
    return case_memory_policy_decision(source_type, source_ref).review_status or "needs_review"


def _needs_review(memory_type: MemoryPolicyMemoryType, *, blocked_by: list[str]) -> MemoryPolicyDecision:
    return MemoryPolicyDecision(
        memory_type=memory_type,
        decision="needs_review",
        review_status="needs_review",
        reason_code="requires_review",
        blocked_by=blocked_by,
    )


def _source_ref_business_object_type(source_ref: Any | None) -> str | None:
    if source_ref is None:
        return None
    if isinstance(source_ref, dict):
        value = source_ref.get("business_object_type")
    else:
        value = getattr(source_ref, "business_object_type", None)
    return str(value) if value else None
