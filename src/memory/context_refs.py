from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from src.memory.schemas import SessionContextMemory


class SessionContextRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["session_context_ref.v1"] = "session_context_ref.v1"
    authority_class: Literal["contextual_only"] = "contextual_only"
    tenant_id: str
    user_id: str
    thread_id: str
    run_id: str
    source: Literal["conversation_log", "session_continuity_store", "tool_summary", "session_context_load"]
    ref_id: str
    created_at: datetime | None = None


class ReviewedMemoryRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["reviewed_memory_ref.v1"] = "reviewed_memory_ref.v1"
    authority_class: Literal["contextual_only"] = "contextual_only"
    tenant_id: str
    memory_type: Literal["long_term", "case"]
    scope_type: str
    scope_id: str
    memory_id: str
    review_status: str
    source_identity_hash: str | None = None
    prompt_safe: bool = True


class SessionContextLoadStatusV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["session_context_load_status.v1"] = "session_context_load_status.v1"
    status: str
    source: str
    authority_class: Literal["contextual_only"] = "contextual_only"
    tenant_id: str
    user_id: str
    thread_id: str
    run_id: str
    loaded_refs: list[SessionContextRef] = Field(default_factory=list)
    fallback_reason: str | None = None
    slot_count: int = 0
    recent_message_count: int = 0
    tool_summary_count: int = 0
    filter_reasons: list[str] = Field(default_factory=list)


class ReviewedMemoryContextRetrieveStatusV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["reviewed_memory_context_retrieve_status.v1"] = (
        "reviewed_memory_context_retrieve_status.v1"
    )
    status: str
    authority_class: Literal["contextual_only"] = "contextual_only"
    trusted_scope_inputs: dict[str, Any] = Field(default_factory=dict)
    effective_scopes: list[dict[str, Any]] = Field(default_factory=list)
    filter_reasons: list[str] = Field(default_factory=list)
    retrieved_refs: list[ReviewedMemoryRef] = Field(default_factory=list)
    fallback_reason: str | None = None


class ReviewedMemoryContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["reviewed_memory_context_bundle.v1"] = "reviewed_memory_context_bundle.v1"
    authority_class: Literal["contextual_only"] = "contextual_only"
    long_term_items: list[dict[str, Any]] = Field(default_factory=list)
    case_items: list[dict[str, Any]] = Field(default_factory=list)
    status_ref: ReviewedMemoryContextRetrieveStatusV1 = Field(
        validation_alias=AliasChoices("status_ref", "retrieve_status")
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_legacy_non_semantic_fields(cls, value: Any) -> Any:
        if isinstance(value, dict) and "tenant_id" in value:
            value = dict(value)
            value.pop("tenant_id", None)
        return value

    @field_validator("long_term_items", "case_items", mode="before")
    @classmethod
    def _coerce_nested_refs(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value

        normalized: list[Any] = []
        for item in value:
            if not isinstance(item, dict):
                normalized.append(item)
                continue
            item_copy = dict(item)
            ref = item_copy.get("ref")
            if isinstance(ref, dict):
                item_copy["ref"] = ReviewedMemoryRef.model_validate(ref)
            normalized.append(item_copy)
        return normalized

    @property
    def retrieve_status(self) -> ReviewedMemoryContextRetrieveStatusV1:
        return self.status_ref


class MemoryContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["memory_context_bundle.v1"] = "memory_context_bundle.v1"
    authority_class: Literal["contextual_only"] = "contextual_only"
    session_context: SessionContextMemory
    long_term_items: list[dict[str, Any]] = Field(default_factory=list)
    case_items: list[dict[str, Any]] = Field(default_factory=list)
    session_status_ref: SessionContextLoadStatusV1 | None = None
    reviewed_status_ref: ReviewedMemoryContextRetrieveStatusV1 | None = None


class MemoryWriteDecisionV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["memory_write_decision.v2"] = "memory_write_decision.v2"
    status: str
    decision: str
    authority_class: Literal["contextual_only"] = "contextual_only"
    memory_type: str
    memory_id: str | None = None
    candidate_hash: str | None = None
    source_identity_hash: str | None = None
    scope: dict[str, Any] = Field(default_factory=dict)
    pii_classification: str
    review_status: str
    reason_code: str
    policy_version: str = "memory_write_policy.v1"
    blocked_by: list[str] = Field(default_factory=list)
    fallback_reason: str | None = None
