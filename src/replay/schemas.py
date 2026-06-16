"""Strict ReplayEventV3 contract schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.replay.validators import validate_event_type


class ReplayEventProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_schema_version: str
    pairing_status: Literal["paired", "unresolved", "not_applicable"]


class ReplayRetention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    archived_at: datetime | None = None
    retention_until: datetime | None = None
    deleted_at: datetime | None = None


class ReplayError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool


class ReplayEventV3(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["replay_event.v3"] = "replay_event.v3"
    event_id: UUID
    run_id: UUID
    tenant_id: UUID
    thread_id: str = Field(min_length=1)
    trace_id: str | None = None
    sequence: int = Field(gt=0)
    event_type: str
    occurred_at: datetime
    operation_id: UUID | None = None
    parent_operation_id: UUID | None = None
    attempt: int | None = Field(default=None, gt=0)
    node_name: str | None = None
    actor: dict[str, Any]
    resource_refs: dict[str, Any]
    redacted_payload: dict[str, Any]
    redaction_policy_version: str = Field(min_length=1)
    provenance: ReplayEventProvenance
    retention: ReplayRetention
    error: ReplayError | None = None

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, event_type: str) -> str:
        validate_event_type(event_type)
        return event_type


class ReplayResponseV3(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["replay_response.v3"] = "replay_response.v3"
    run_id: UUID
    thread_id: str = Field(min_length=1)
    final_status: str = Field(min_length=1)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    timeline: list[ReplayEventV3]
