"""Minimal Phase 10 trace event envelope helpers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.replay import (
    FORBIDDEN_REDACTED_PAYLOAD_KEYS as _REPLAY_FORBIDDEN_REDACTED_PAYLOAD_KEYS,
    REPLAY_EVENT_TYPES,
    ReplayService,
    guard_redacted_payload,
)


TOOL_CALL_TOOLS = {"get_order", "get_refund_case", "get_ticket", "get_logistics", "get_merchant_risk"}
RAG_RETRIEVAL_TOOLS = {"search_policy", "search_sop", "search_case_memory"}
MINIMAL_EVENT_TYPES = set(REPLAY_EVENT_TYPES)
EVENT_RETENTION_CLASSIFICATION = {event_type: "minimal_event" for event_type in MINIMAL_EVENT_TYPES}
SCHEMA_VERSION = "minimal_event_envelope.v1"
FORBIDDEN_REDACTED_PAYLOAD_KEYS = set(_REPLAY_FORBIDDEN_REDACTED_PAYLOAD_KEYS)


def classify_event_family(tool_name: str) -> str:
    """Classify an allowlisted read call by call nature."""
    if tool_name in TOOL_CALL_TOOLS:
        return "tool_call"
    if tool_name in RAG_RETRIEVAL_TOOLS:
        return "rag_retrieval"
    raise ValueError(f"tool {tool_name!r} is not an allowlisted read tool")


async def allocate_sequence(session: AsyncSession, run_id: uuid.UUID | str) -> int:
    """Allocate the next strictly monotonic sequence number for a run."""
    return await ReplayService(session).allocate_sequence(run_id)


async def emit_event(
    session: AsyncSession,
    *,
    run_id: uuid.UUID | str,
    tenant_id: uuid.UUID | str,
    thread_id: str,
    event_type: str,
    actor: dict[str, Any],
    resource_refs: dict[str, Any],
    redacted_payload: dict[str, Any],
    trace_id: str | None = None,
    operation_id: uuid.UUID | str | None = None,
    iteration: int | None = None,
    redaction_policy_version: str = "redaction.v1",
) -> dict[str, Any]:
    """Persist and return one minimal event envelope."""
    if event_type not in MINIMAL_EVENT_TYPES:
        raise ValueError(f"event_type {event_type!r} is not registered for the minimal envelope")

    return await ReplayService(session).append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type=event_type,
        actor=actor,
        resource_refs=resource_refs,
        redacted_payload=redacted_payload,
        trace_id=trace_id,
        operation_id=operation_id,
        iteration=iteration,
        redaction_policy_version=redaction_policy_version,
        schema_version=SCHEMA_VERSION,
    )


def _guard_redacted_payload(redacted_payload: dict[str, Any]) -> None:
    guard_redacted_payload(redacted_payload)


def _as_uuid(value: uuid.UUID | str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))
