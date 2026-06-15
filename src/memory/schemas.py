from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field


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
    version: int | None = None
    decision: Literal["write", "skip"] = "write"
    reason_code: str
    pii_classification: Literal["none", "low", "sensitive", "prohibited"] = "none"
    conflict_reason: str | None = None
    fallback_reason: str | None = None


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
