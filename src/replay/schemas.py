"""Strict ReplayEventV3 contract schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.knowledge.schemas import EvidenceRefV1
from src.replay.validators import validate_event_type


ReplayEvidenceLifecycleStatus = Literal[
    "current",
    "superseded",
    "corrected",
    "archived",
    "expired",
    "tombstoned",
]


class ReplayEvidenceCompatibilityProvenanceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution_status: Literal["canonical", "legacy_resolved", "legacy_unresolved"]
    source: Literal["canonical_ref_append", "persisted_legacy_event", "existing_event_migration"]


class ReplayEvidenceSnapshotV1(BaseModel):
    """Exact append-time binding to retained immutable evidence material."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["replay_evidence_snapshot.v1"] = "replay_evidence_snapshot.v1"
    canonical_evidence_ref: EvidenceRefV1
    scope_type: Literal["tenant_policy"]
    scope_id: str
    document_version_id: str
    chunk_version_id: str
    document_version: int = Field(gt=0)
    chunk_version: int = Field(gt=0)
    canonical_identity_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    captured_lifecycle_status: ReplayEvidenceLifecycleStatus
    retained_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    retained_content_locator: dict[str, Any]
    compatibility_provenance: ReplayEvidenceCompatibilityProvenanceV1
    retention_until: datetime
    retained_content: str | None = Field(default=None, exclude_if=lambda value: value is None)
    current_lifecycle_status: ReplayEvidenceLifecycleStatus | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @model_validator(mode="after")
    def _validate_exact_binding(self) -> ReplayEvidenceSnapshotV1:
        identity = self.canonical_evidence_ref.to_canonical_identity()
        if identity is None:
            raise ValueError("replay evidence snapshots require a canonical immutable ref")
        expected = {
            "scope_type": identity.scope_type,
            "scope_id": identity.scope_id,
            "document_version_id": identity.document_version_id,
            "chunk_version_id": identity.chunk_version_id,
            "document_version": identity.document_version,
            "chunk_version": identity.chunk_version,
            "canonical_identity_hash": identity.evidence_id,
            "retained_content_hash": identity.text_hash,
        }
        actual = {field_name: getattr(self, field_name) for field_name in expected}
        if actual != expected:
            raise ValueError("replay evidence snapshot fields must match the canonical ref")
        allowed_locator_keys = {
            "source_type",
            "source_checksum",
            "source_uri",
            "page_number",
            "source_block_refs",
        }
        if not self.retained_content_locator or set(self.retained_content_locator) - allowed_locator_keys:
            raise ValueError("retained content locator contains non-allowlisted fields")
        return self


class ReplayEventProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_schema_version: str
    pairing_status: Literal["paired", "unresolved", "not_applicable"]
    evidence_resolution_status: Literal["canonical", "legacy_resolved", "legacy_unresolved"] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )


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
    evidence_snapshot_refs: list[ReplayEvidenceSnapshotV1] = Field(default_factory=list)
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
    rag_claim_summary: dict[str, Any] | None = None
