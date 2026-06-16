"""Replay event registry validation."""

from __future__ import annotations


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


def validate_event_type(event_type: str) -> None:
    if event_type not in REPLAY_EVENT_TYPES:
        raise ValueError(f"event_type {event_type!r} is not registered for ReplayEventV3")
