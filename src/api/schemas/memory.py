from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


MemoryReviewType = Literal["long_term", "case"]


class MemoryReviewActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    expected_lifecycle_version: int | None = Field(default=None, gt=0)
    reason_code: str | None = Field(default=None, min_length=1, max_length=64)
    review_reason: str | None = Field(default=None, max_length=1500)


class MemorySourceAuthorityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["business_fact", "policy_evidence"]
    source_status: Literal["success"]
    source_authority_class: Literal["business_fact", "policy_evidence"]
    source_ref: dict[str, str]
    business_fact_refs: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)


class MemoryScopeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: str
    scope_id: str


class CaseMemoryLineageLinkItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    survivor_case_memory_id: str
    related_case_memory_id: str
    relation: Literal["duplicate", "correction", "supersession"]
    ordinal: int = Field(gt=0)


class CaseMemoryLineageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corrects_case_memory_id: str | None = None
    supersedes_case_memory_id: str | None = None
    links: list[CaseMemoryLineageLinkItem] = Field(default_factory=list)


class MemoryPendingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: MemoryReviewType
    memory_id: str
    scope_type: str
    scope_id: str
    scope: MemoryScopeItem | None = None
    review_status: str
    pii_classification: str
    source_type: str
    content: str | None = None
    summary: str | None = None
    excerpt: str | None = None
    created_by_run_id: str | None = None
    created_at: datetime | None = None
    memory_authority_class: Literal["contextual_only"] | None = None
    identity_algorithm_version: str | None = None
    identity_profile: str | None = None
    identity_resolution_status: Literal["canonical", "legacy_resolved"] | None = None
    candidate_hash: str | None = None
    lifecycle_version: int | None = Field(default=None, gt=0)
    review_decision: Literal["approved", "rejected"] | None = None
    source_authorities: list[MemorySourceAuthorityItem] = Field(default_factory=list)
    lineage: CaseMemoryLineageItem | None = None


class MemoryPendingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MemoryPendingItem]
    total: int


class CaseMemoryDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: Literal["case"] = "case"
    memory_id: str
    scope: MemoryScopeItem
    review_status: str
    pii_classification: str
    summary: str
    excerpt: str
    created_by_run_id: str | None = None
    created_at: datetime | None = None
    memory_authority_class: Literal["contextual_only"]
    identity_algorithm_version: Literal["memory_identity.v1"]
    identity_profile: Literal["nfkc_casefold_legacy", "nfc_selective_v2"]
    identity_resolution_status: Literal["canonical", "legacy_resolved"]
    candidate_hash: str
    lifecycle_version: int = Field(gt=0)
    review_decision: Literal["approved", "rejected"] | None = None
    reviewer_user_id: str | None = None
    reviewed_at: datetime | None = None
    review_reason: str | None = None
    source_authorities: list[MemorySourceAuthorityItem] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    business_fact_refs: list[dict[str, Any]] = Field(default_factory=list)
    lineage: CaseMemoryLineageItem


class LongTermPreferenceSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    scope_type: Literal["tenant", "merchant"]
    scope_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=4000)
    reason_code: str | None = Field(default=None, min_length=1, max_length=64)


class LongTermPreferenceSaveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: Literal["long_term"]
    memory_id: str | None
    event_id: str | None
    decision: str
    reason_code: str
    review_status: str | None
    source_type: Literal["explicit_admin_preference"]
