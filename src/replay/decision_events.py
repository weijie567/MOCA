"""Replay-owned decision event envelope and emitter facade."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import re
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.replay.validators import guard_redacted_payload, guard_resource_refs, validate_event_type

if TYPE_CHECKING:
    from src.platform.context_projections import ReplayContext


SCHEMA_VERSION = "minimal_event_envelope.v1"
REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$")
OPERATION_EVENT_PREFIXES = ("node_", "tool_call_", "rag_retrieval_", "llm_call_", "memory_write_")
VERSION_KEYS = ("policy_version", "model_version", "tool_version")


class DecisionEventEnvelopeV1(BaseModel):
    """Strict schema for the existing minimal event envelope projection."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["minimal_event_envelope.v1"] = SCHEMA_VERSION
    event_id: UUID
    sequence: int = Field(gt=0)
    operation_id: UUID | None = None
    run_id: UUID
    tenant_id: UUID
    thread_id: str = Field(min_length=1)
    trace_id: str | None = None
    event_type: str
    occurred_at: datetime
    actor: dict[str, Any]
    resource_refs: dict[str, Any]
    redaction_policy_version: str = Field(min_length=1)
    redacted_payload: dict[str, Any]

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, event_type: str) -> str:
        validate_event_type(event_type)
        return event_type

    @model_validator(mode="after")
    def _validate_operation_id_condition(self) -> DecisionEventEnvelopeV1:
        if _requires_operation_id(self.event_type) and self.operation_id is None:
            raise ValueError(f"operation_id is required for event_type {self.event_type!r}")
        return self


async def emit_decision_event(
    session: AsyncSession,
    *,
    replay_context: ReplayContext | None = None,
    run_id: UUID | str | None = None,
    tenant_id: UUID | str | None = None,
    thread_id: str | None = None,
    event_type: str,
    actor: dict[str, Any],
    resource_refs: dict[str, Any],
    redacted_payload: dict[str, Any],
    trace_id: str | None = None,
    operation_id: UUID | str | None = None,
    iteration: int | None = None,
    redaction_policy_version: str = "redaction.v1",
    reason_code: str | None = None,
    reason_codes: list[str] | None = None,
    versions: Mapping[str, str | None] | None = None,
) -> dict[str, Any]:
    """Persist one replay-owned minimal decision event and return a validated envelope."""

    identity = _resolve_identity(
        replay_context=replay_context,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        trace_id=trace_id,
    )
    payload = _normalize_redacted_payload(
        redacted_payload,
        replay_context=replay_context,
        reason_code=reason_code,
        reason_codes=reason_codes,
        versions=versions,
    )
    refs = dict(resource_refs)

    guard_redacted_payload(payload)
    guard_resource_refs(refs)

    from src.replay.service import ReplayService

    raw_event = await ReplayService(session).append_event(
        run_id=identity["run_id"],
        tenant_id=identity["tenant_id"],
        thread_id=identity["thread_id"],
        trace_id=identity["trace_id"],
        event_type=event_type,
        actor=actor,
        resource_refs=refs,
        redacted_payload=payload,
        operation_id=operation_id,
        iteration=iteration,
        redaction_policy_version=redaction_policy_version,
        schema_version=SCHEMA_VERSION,
    )
    return DecisionEventEnvelopeV1.model_validate(raw_event).model_dump(mode="python")


def normalize_reason_codes(
    *,
    reason_code: str | None = None,
    reason_codes: list[str] | None = None,
) -> list[str] | None:
    """Return first-seen de-duplicated reason codes, or None when none were provided."""

    if reason_codes is not None and not isinstance(reason_codes, list):
        raise ValueError("reason_codes must be a list[str]")

    ordered: list[str] = []
    for code in [reason_code, *(reason_codes or [])]:
        if code is None:
            continue
        if not isinstance(code, str) or not REASON_CODE_PATTERN.fullmatch(code):
            raise ValueError("reason_code values must be non-empty snake_case strings")
        if code not in ordered:
            ordered.append(code)
    return ordered or None


def _requires_operation_id(event_type: str) -> bool:
    return event_type.startswith(OPERATION_EVENT_PREFIXES)


def _resolve_identity(
    *,
    replay_context: ReplayContext | None,
    run_id: UUID | str | None,
    tenant_id: UUID | str | None,
    thread_id: str | None,
    trace_id: str | None,
) -> dict[str, UUID | str | None]:
    if replay_context is not None:
        resolved = {
            "run_id": replay_context.run_id,
            "tenant_id": replay_context.tenant_id,
            "thread_id": replay_context.thread_id,
            "trace_id": replay_context.trace_id,
        }
    else:
        resolved = {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "thread_id": thread_id,
            "trace_id": trace_id,
        }

    missing = [
        field_name
        for field_name in ("run_id", "tenant_id", "thread_id")
        if resolved[field_name] in (None, "")
    ]
    if missing:
        raise ValueError(f"missing required decision event identity: {', '.join(missing)}")
    return resolved


def _normalize_redacted_payload(
    redacted_payload: dict[str, Any],
    *,
    replay_context: ReplayContext | None,
    reason_code: str | None,
    reason_codes: list[str] | None,
    versions: Mapping[str, str | None] | None,
) -> dict[str, Any]:
    payload = dict(redacted_payload)
    payload_reason_codes = payload.get("reason_codes")
    if payload_reason_codes is not None:
        payload["reason_codes"] = normalize_reason_codes(reason_codes=payload_reason_codes) or []

    normalized_reasons = normalize_reason_codes(reason_code=reason_code, reason_codes=reason_codes)
    if normalized_reasons is not None:
        payload["reason_codes"] = normalized_reasons

    normalized_versions = _normalize_versions(replay_context=replay_context, versions=versions)
    if normalized_versions:
        payload["versions"] = normalized_versions
    return payload


def _normalize_versions(
    *,
    replay_context: ReplayContext | None,
    versions: Mapping[str, str | None] | None,
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    if replay_context is not None:
        for key in VERSION_KEYS:
            value = getattr(replay_context, key)
            if value:
                normalized[key] = str(value)

    if versions is not None:
        for key in VERSION_KEYS:
            value = versions.get(key)
            if value:
                normalized[key] = str(value)
    return normalized
