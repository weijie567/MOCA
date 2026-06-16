"""Minimal Phase 10 trace event envelope helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentTraceEvent


TOOL_CALL_TOOLS = {"get_order", "get_refund_case", "get_ticket", "get_logistics", "get_merchant_risk"}
RAG_RETRIEVAL_TOOLS = {"search_policy", "search_sop", "search_case_memory"}
MINIMAL_EVENT_TYPES = {
    "node_started",
    "node_completed",
    "node_failed",
    "run_status_changed",
    "tool_call_started",
    "tool_call_completed",
    "tool_call_failed",
    "rag_retrieval_started",
    "rag_retrieval_completed",
    "rag_retrieval_failed",
    "llm_call_started",
    "llm_call_completed",
    "llm_call_failed",
    "memory_write_started",
    "memory_write_completed",
    "memory_write_failed",
    "approval_requested",
    "approval_decided",
    "approval_expired",
    "approval_resumed",
    "action_draft_created",
}
EVENT_RETENTION_CLASSIFICATION = {event_type: "minimal_event" for event_type in MINIMAL_EVENT_TYPES}
SCHEMA_VERSION = "minimal_event_envelope.v1"
FORBIDDEN_REDACTED_PAYLOAD_KEYS = {
    "data",
    "raw",
    "arguments",
    "prompt",
    "raw_prompt",
    "raw_args",
    "raw_payload",
    "raw_tool_output",
    "secret",
    "secrets",
    "credential",
    "credentials",
    "pii",
}


def classify_event_family(tool_name: str) -> str:
    """Classify an allowlisted read call by call nature."""
    if tool_name in TOOL_CALL_TOOLS:
        return "tool_call"
    if tool_name in RAG_RETRIEVAL_TOOLS:
        return "rag_retrieval"
    raise ValueError(f"tool {tool_name!r} is not an allowlisted read tool")


async def allocate_sequence(session: AsyncSession, run_id: uuid.UUID | str) -> int:
    """Allocate the next strictly monotonic sequence number for a run."""
    run_uuid = _as_uuid(run_id)
    await session.execute(
        sa.text("SELECT pg_advisory_xact_lock(hashtext(:run_id_text))"),
        {"run_id_text": str(run_uuid)},
    )
    result = await session.execute(
        sa.text(
            """
            SELECT COALESCE(MAX(sequence), 0) + 1
            FROM agent_trace_events
            WHERE run_id = :run_id
            """
        ),
        {"run_id": run_uuid},
    )
    return int(result.scalar_one())


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

    _guard_redacted_payload(redacted_payload)
    safe_payload = dict(redacted_payload)
    if iteration is not None:
        safe_payload["iteration"] = iteration

    run_uuid = _as_uuid(run_id)
    sequence = await allocate_sequence(session, run_uuid)
    event_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{run_uuid}:{sequence}")
    occurred_at = datetime.now(UTC)
    operation_uuid = _as_uuid(operation_id) if operation_id is not None else None
    tenant_uuid = _as_uuid(tenant_id)

    envelope = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "sequence": sequence,
        "operation_id": operation_uuid,
        "run_id": run_uuid,
        "tenant_id": tenant_uuid,
        "thread_id": thread_id,
        "trace_id": trace_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor": actor,
        "resource_refs": resource_refs,
        "redaction_policy_version": redaction_policy_version,
        "redacted_payload": safe_payload,
    }
    session.add(AgentTraceEvent(**envelope))
    await session.flush()
    return envelope


def _guard_redacted_payload(redacted_payload: dict[str, Any]) -> None:
    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in FORBIDDEN_REDACTED_PAYLOAD_KEYS:
                    raise ValueError(f"{path} must not carry {key}")
                walk(child, f"{path}.{key}")
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(redacted_payload, "redacted_payload")


def _as_uuid(value: uuid.UUID | str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))
