from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from pydantic import ValidationError

from src.replay.schemas import (
    ReplayEventProvenance,
    ReplayEventV3,
    ReplayResponseV3,
    ReplayRetention,
)
from src.replay.validators import REPLAY_EVENT_TYPES, validate_event_type


def _base_event_payload() -> dict:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    return {
        "event_id": uuid.uuid4(),
        "run_id": run_id,
        "tenant_id": tenant_id,
        "thread_id": "thread-replay-001",
        "trace_id": "trace-replay-001",
        "sequence": 1,
        "event_type": "node_started",
        "occurred_at": datetime(2026, 6, 16, 10, 0, tzinfo=UTC),
        "operation_id": uuid.uuid4(),
        "parent_operation_id": None,
        "attempt": 1,
        "node_name": "investigate",
        "actor": {"type": "agent", "id": "moca"},
        "resource_refs": {"evidence_ids": ["policy_refund_timeout/chunk_001@v3"]},
        "redacted_payload": {"status": "started", "summary": "investigation started"},
        "redaction_policy_version": "redaction.v1",
        "provenance": {
            "source_schema_version": "replay_event.v3",
            "pairing_status": "paired",
        },
        "retention": {
            "archived_at": None,
            "retention_until": None,
            "deleted_at": None,
        },
        "error": None,
    }


def test_replay_event_v3_validates_native_event():
    event = ReplayEventV3(**_base_event_payload())

    dumped = event.model_dump(mode="json")
    assert dumped["schema_version"] == "replay_event.v3"
    assert dumped["event_type"] == "node_started"
    assert dumped["provenance"] == {
        "source_schema_version": "replay_event.v3",
        "pairing_status": "paired",
    }
    assert dumped["retention"] == {
        "archived_at": None,
        "retention_until": None,
        "deleted_at": None,
    }


def test_legacy_minimal_event_projects_to_v3_with_unresolved_provenance():
    payload = _base_event_payload()
    payload.update(
        {
            "sequence": 2,
            "event_type": "approval_requested",
            "operation_id": None,
            "parent_operation_id": None,
            "attempt": None,
            "node_name": None,
            "provenance": {
                "source_schema_version": "minimal_event_envelope.v1",
                "pairing_status": "unresolved",
            },
        }
    )

    event = ReplayEventV3(**payload)
    response = ReplayResponseV3(
        run_id=payload["run_id"],
        thread_id=payload["thread_id"],
        final_status="interrupted",
        started_at=payload["occurred_at"],
        completed_at=None,
        timeline=[event],
    )

    dumped = response.model_dump(mode="json")
    assert dumped["schema_version"] == "replay_response.v3"
    assert dumped["timeline"][0]["schema_version"] == "replay_event.v3"
    assert dumped["timeline"][0]["provenance"] == {
        "source_schema_version": "minimal_event_envelope.v1",
        "pairing_status": "unresolved",
    }


def test_replay_schemas_are_strict():
    payload = _base_event_payload()
    payload["unexpected"] = "not allowed"

    with pytest.raises(ValidationError):
        ReplayEventV3(**payload)

    with pytest.raises(ValidationError):
        ReplayEventProvenance(
            source_schema_version="minimal_event_envelope.v1",
            pairing_status="invented",
        )

    with pytest.raises(ValidationError):
        ReplayRetention(archived_at=None, retention_until=None, deleted_at=None, extra=True)


def test_replay_event_types_include_phase_10_to_15_events():
    expected = {
        "node_started",
        "node_completed",
        "node_failed",
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
        "run_status_changed",
    }

    assert expected <= REPLAY_EVENT_TYPES
    validate_event_type("run_status_changed")
    with pytest.raises(ValueError):
        validate_event_type("action_execution_completed")
