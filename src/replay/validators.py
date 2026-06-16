"""Replay event registry, redaction, and retention validation."""

from __future__ import annotations

from typing import Any


REPLAY_EVENT_TYPES: set[str] = {
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

EVENT_RETENTION_CLASSIFICATION: dict[str, str] = {
    "node_started": "trace_event",
    "node_completed": "trace_event",
    "node_failed": "trace_event",
    "run_status_changed": "trace_event",
    "tool_call_started": "tool_event",
    "tool_call_completed": "tool_event",
    "tool_call_failed": "tool_event",
    "rag_retrieval_started": "evidence_event",
    "rag_retrieval_completed": "evidence_event",
    "rag_retrieval_failed": "evidence_event",
    "llm_call_started": "llm_event",
    "llm_call_completed": "llm_event",
    "llm_call_failed": "llm_event",
    "memory_write_started": "memory_event",
    "memory_write_completed": "memory_event",
    "memory_write_failed": "memory_event",
    "approval_requested": "approval_audit_event",
    "approval_decided": "approval_audit_event",
    "approval_expired": "approval_audit_event",
    "approval_resumed": "approval_audit_event",
    "action_draft_created": "action_audit_event",
}

FORBIDDEN_REDACTED_PAYLOAD_KEYS: set[str] = {
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


def validate_event_type(event_type: str) -> None:
    if event_type not in REPLAY_EVENT_TYPES:
        raise ValueError(f"event_type {event_type!r} is not registered for ReplayEventV3")


def guard_redacted_payload(redacted_payload: dict[str, Any]) -> None:
    """Reject unsafe keys before event persistence or projection."""

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


def retention_for_event_type(event_type: str) -> str:
    validate_event_type(event_type)
    try:
        return EVENT_RETENTION_CLASSIFICATION[event_type]
    except KeyError as exc:
        raise ValueError(f"event_type {event_type!r} has no retention classification") from exc
