from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"


class MemorySourceRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    run_id: str | None = None
    event_id: str | None = None
    conversation_message_id: str | None = None
    tool_result_id: str | None = None
    agent_run_id: str | None = None
    business_object_type: str | None = None
    business_object_id: str | None = None
    policy_version: str | None = None
    outcome_id: str | None = None


class MemoryIdentityV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    memory_type: str
    scope_type: str
    scope_id: str
    content_hash: str = Field(pattern=_SHA256_PATTERN)
    source_identity_hash: str | None = Field(default=None, pattern=_SHA256_PATTERN)


class MemoryCandidateIdentityV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    memory_type: str
    scope_type: str
    scope_id: str
    content_hash: str = Field(pattern=_SHA256_PATTERN)
    source_identity_hash: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    candidate_hash: str = Field(pattern=_SHA256_PATTERN)


class SessionSlotV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    source: Literal["explicit_user", "system_derived"]
    source_run_id: str
    updated_at: datetime
    expires_at: datetime
    compatible_intents: list[str]
    confirmed_at: datetime | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    business_object_type: str | None = None
    business_object_id: str | None = None
    display_label: str | None = None


class SessionSlotsEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["session_slots.v1"] = "session_slots.v1"
    slots: dict[str, SessionSlotV1] = Field(default_factory=dict)


class SessionMemoryView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    continuity_claimed: bool
    active_slots: dict[str, str] = Field(default_factory=dict)
    slot_metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)
    session_summary: str | None = None
    unresolved_questions: list[Any] = Field(default_factory=list)
    last_intent: str | None = None
    last_business_context_refs: dict[str, Any] = Field(default_factory=dict)
    version: int | None = None
    fallback_reason: str | None = None


SlotContinuityMemoryView = SessionMemoryView


class SessionRollingSummaryView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary_id: str
    summary_text: str
    source_message_ids: list[str] = Field(default_factory=list)
    source_tool_result_ids: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class SessionRecentMessageView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    run_id: str
    message_index: int
    role: Literal["user", "assistant", "tool"]
    content: str
    created_at: datetime | None = None


class SessionToolSummaryView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_result_record_id: str
    tool_result_id: str | None = None
    run_id: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    status: str
    prompt_summary: str
    business_fact_refs: list[dict[str, Any]] = Field(default_factory=list)
    policy_evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    audit_ref: str | None = None
    created_at: datetime | None = None


class SessionMemoryBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["session_memory_bundle.v1"] = "session_memory_bundle.v1"
    source: Literal["session_memory_bundle"] = "session_memory_bundle"
    tenant_id: str
    user_id: str
    thread_id: str
    run_id: str
    rolling_summary: SessionRollingSummaryView | None = None
    recent_messages: list[SessionRecentMessageView] = Field(default_factory=list)
    tool_summaries: list[SessionToolSummaryView] = Field(default_factory=list)
    slot_continuity: SlotContinuityMemoryView
    policy_topic_hints: list[str] = Field(default_factory=list)
    prior_policy_mention_refs: list[dict[str, Any]] = Field(default_factory=list)
    fallback_reasons: dict[str, str] = Field(default_factory=dict)


class SessionContextMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["session_context_memory.v1"] = "session_context_memory.v1"
    authority_class: Literal["contextual_only"] = "contextual_only"
    tenant_id: str
    user_id: str
    thread_id: str
    run_id: str
    rolling_summary: SessionRollingSummaryView | None = None
    recent_messages: list[SessionRecentMessageView] = Field(default_factory=list)
    tool_summaries: list[SessionToolSummaryView] = Field(default_factory=list)
    slot_continuity: SlotContinuityMemoryView
    policy_topic_hints: list[str] = Field(default_factory=list)
    prior_policy_mention_refs: list[dict[str, Any]] = Field(default_factory=list)
    fallback_reasons: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _from_session_memory_bundle(cls, value: Any) -> Any:
        if isinstance(value, SessionMemoryBundle):
            value = value.model_dump(mode="json")
        if isinstance(value, dict) and value.get("schema_version") == "session_memory_bundle.v1":
            value = dict(value)
            value["schema_version"] = "session_context_memory.v1"
            value.pop("source", None)
        return value


class SessionContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["session_context_bundle.v1"] = "session_context_bundle.v1"
    authority_class: Literal["contextual_only"] = "contextual_only"
    session_context: SessionContextMemory


class SessionMemoryWriteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    thread_id: str
    run_id: uuid.UUID
    explicit_slots: dict[str, SessionSlotV1] = Field(default_factory=dict)
    unresolved_questions: list[Any] = Field(default_factory=list)
    last_intent: str | None = None
    session_summary: str | None = None
    last_business_context_refs: dict[str, Any] = Field(default_factory=dict)
    expected_version: int | None = None
    pii_classification: Literal["none", "low", "sensitive", "prohibited"] = "none"
    decision: Literal["write", "skip"] = "write"
    reason_code: str = "eligible"


class SessionMemoryWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["written", "merged_after_conflict", "conflict", "skipped", "disabled", "fallback", "error"]
    memory_id: uuid.UUID | None = None
    version: int | None = None
    decision: Literal["write", "skip"] = "write"
    reason_code: str
    policy_version: str = "memory_write_policy.v1"
    blocked_by: list[str] = Field(default_factory=list)
    pii_classification: Literal["none", "low", "sensitive", "prohibited"] = "none"
    candidate_hash: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    event_id: uuid.UUID | None = None
    conflict_reason: str | None = None
    fallback_reason: str | None = None


LongTermScopeType = Literal["tenant", "merchant", "user", "thread", "case"]
LongTermMemoryKind = Literal["fact", "preference", "constraint", "pattern"]
LongTermSemanticKind = Literal[
    "durable_profile_fact",
    "merchant_preference",
    "operational_constraint",
    "merchant_pattern",
]
LongTermPiiClassification = Literal["none", "low", "sensitive", "prohibited"]
LongTermReviewStatus = Literal[
    "auto_approved",
    "needs_review",
    "approved",
    "rejected",
    "superseded",
    "tombstoned",
    "deleted",
]
LongTermWriteDecision = Literal["write", "skip", "needs_review", "delete", "supersede", "tombstone", "write_blocked"]
LongTermSourceType = Literal[
    "explicit_user_preference",
    "explicit_admin_preference",
    "human_reviewed",
    "deterministic_tool_result",
    "confirmed_business_outcome",
    "approved_approval_state",
    "llm_candidate",
    "semantic_episode_candidate",
    "summary_candidate",
    "cross_case_pattern_candidate",
    "behavior_inference",
]
CaseMemoryScopeType = Literal["tenant", "merchant", "user", "thread", "case"]
CaseMemoryPiiClassification = Literal["none", "low", "sensitive", "prohibited"]
CaseMemoryReviewStatus = Literal[
    "auto_approved",
    "needs_review",
    "approved",
    "rejected",
    "superseded",
    "tombstoned",
    "deleted",
]
CaseMemoryWriteDecision = Literal["write", "skip", "needs_review", "delete", "supersede", "tombstone", "write_blocked"]
CaseMemorySourceType = Literal[
    "explicit_admin_preference",
    "human_reviewed",
    "deterministic_tool_result",
    "confirmed_business_outcome",
    "approved_approval_state",
    "llm_candidate",
    "semantic_episode_candidate",
    "summary_candidate",
    "cross_case_pattern_candidate",
    "behavior_inference",
]


class LongTermMemoryWriteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID
    run_id: uuid.UUID
    scope_type: LongTermScopeType
    scope_id: str = Field(min_length=1, max_length=128)
    memory_kind: LongTermMemoryKind = "fact"
    content: str = Field(min_length=1, max_length=4000)
    source_type: LongTermSourceType
    source_ref: MemorySourceRefV1 | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    pii_classification: LongTermPiiClassification = "none"
    expires_at: datetime | None = None


class LongTermMemoryWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["written", "needs_review", "skipped", "error"]
    memory_id: uuid.UUID | None = None
    review_status: LongTermReviewStatus | None = None
    decision: LongTermWriteDecision
    reason_code: str
    pii_classification: LongTermPiiClassification = "none"
    candidate_hash: str = Field(pattern=_SHA256_PATTERN)
    content_hash: str = Field(pattern=_SHA256_PATTERN)
    source_identity_hash: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    event_id: uuid.UUID | None = None


class LongTermMemoryView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    tenant_id: str
    scope_type: LongTermScopeType
    scope_id: str
    memory_kind: LongTermMemoryKind
    semantic_kind: LongTermSemanticKind
    content: str
    source_type: str
    source_ref: dict[str, Any] = Field(default_factory=dict)
    review_status: Literal["auto_approved", "approved"]
    version: int
    valid_from: datetime | None = None
    expires_at: datetime | None = None


class CaseMemoryWriteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID
    run_id: uuid.UUID
    scope_type: CaseMemoryScopeType
    scope_id: str = Field(min_length=1, max_length=128)
    case_type: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=4000)
    excerpt: str = Field(min_length=1, max_length=1500)
    applicability: str | None = Field(default=None, max_length=1500)
    outcome: str | None = Field(default=None, max_length=1500)
    caveats: str | None = Field(default=None, max_length=1500)
    source_type: CaseMemorySourceType
    source_ref: MemorySourceRefV1 | None = None
    policy_family: str | None = Field(default=None, max_length=80)
    policy_version: str | None = Field(default=None, max_length=80)
    policy_refs: list[dict[str, Any]] = Field(default_factory=list)
    embedding: list[float] | None = None
    pii_classification: CaseMemoryPiiClassification = "none"
    expires_at: datetime | None = None


class CaseMemoryReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID
    run_id: uuid.UUID
    case_memory_id: uuid.UUID
    reviewer_user_id: uuid.UUID | None = None
    reason_code: str = Field(min_length=1, max_length=64)
    review_reason: str | None = Field(default=None, max_length=1500)


class CaseMemoryWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["written", "needs_review", "skipped", "error"]
    memory_id: uuid.UUID | None = None
    review_status: CaseMemoryReviewStatus | None = None
    decision: CaseMemoryWriteDecision
    reason_code: str
    pii_classification: CaseMemoryPiiClassification = "none"
    candidate_hash: str = Field(pattern=_SHA256_PATTERN)
    content_hash: str = Field(pattern=_SHA256_PATTERN)
    source_identity_hash: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    event_id: uuid.UUID | None = None


class CaseMemorySearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID
    scope_type: CaseMemoryScopeType | None = None
    scope_id: str | None = Field(default=None, max_length=128)
    scopes: list[tuple[CaseMemoryScopeType, str]] | None = None
    case_type: str | None = Field(default=None, max_length=64)
    policy_family: str | None = Field(default=None, max_length=80)
    policy_version: str | None = Field(default=None, max_length=80)
    query: str | None = Field(default=None, min_length=1, max_length=500)
    query_embedding: list[float] | None = None
    now: datetime | None = None
    limit: int = Field(default=5, ge=1, le=50)


class CaseMemorySearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_memory_id: str
    excerpt: str
    applicability: str | None = None
    outcome: str | None = None
    caveats: str | None = None
    score: float
    policy_refs: list[dict[str, Any]] = Field(default_factory=list)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


class CaseMemorySearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "empty"]
    items: list[CaseMemorySearchItem] = Field(default_factory=list)


class SessionPrecedentSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    thread_id: str
    version: int
    score: float = Field(ge=0.0)
    active_slots: dict[str, str] = Field(default_factory=dict)
    session_summary: str | None = None
    unresolved_questions: list[Any] = Field(default_factory=list)
    last_intent: str | None = None
    last_business_context_refs: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None


class SessionPrecedentSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "unavailable"]
    items: list[SessionPrecedentSearchItem] = Field(default_factory=list)
    summary: str
    error_code: str | None = None
