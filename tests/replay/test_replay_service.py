from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.db.models import AgentRun, AgentTraceEvent
from src.replay.pairing import OperationPairingError
from src.replay.schemas import (
    ReplayEventProvenance,
    ReplayEventV3,
    ReplayResponseV3,
    ReplayRetention,
)
from src.replay.service import ReplayService
from src.replay.validators import REPLAY_EVENT_TYPES, retention_for_event_type, validate_event_type


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
    deferred_external_execution_event = "action" + "_execution_completed"
    with pytest.raises(ValueError):
        validate_event_type(deferred_external_execution_event)


async def _create_run(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id="thread-replay-service",
        tenant_id=str(tenant_id),
        user_id=str(uuid.uuid4()),
        input_query="订单退款为什么超时？",
        final_status="running",
        final_response=None,
        started_at=now,
        completed_at=None,
        total_latency_ms=None,
    )
    return run_id, tenant_id


async def _create_manual_run(
    session: AsyncSession,
    *,
    final_status: str = "completed",
) -> tuple[uuid.UUID, uuid.UUID, str]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    thread_id = f"thread-replay-read-{run_id}"
    now = datetime.now(UTC)
    session.add(
        AgentRun(
            id=run_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            user_id=uuid.uuid4(),
            input_query="redacted replay read fixture",
            final_status=final_status,
            final_response=None,
            started_at=now,
            completed_at=now,
            total_latency_ms=10,
        )
    )
    await session.flush()
    return run_id, tenant_id, thread_id


@pytest.mark.asyncio
async def test_get_replay_reads_event_store_rows_in_sequence_order(session: AsyncSession):
    run_id, tenant_id, thread_id = await _create_manual_run(session)
    now = datetime.now(UTC)
    session.add_all(
        [
            AgentTraceEvent(
                event_id=uuid.uuid4(),
                run_id=run_id,
                sequence=2,
                tenant_id=tenant_id,
                thread_id=thread_id,
                event_type="approval_requested",
                schema_version="replay_event.v3",
                occurred_at=now,
                actor={"type": "approver", "id": "approval-service"},
                resource_refs={"approval_id": str(uuid.uuid4())},
                redaction_policy_version="redaction.v1",
                redacted_payload={"status": "pending"},
            ),
            AgentTraceEvent(
                event_id=uuid.uuid4(),
                run_id=run_id,
                sequence=1,
                tenant_id=tenant_id,
                thread_id=thread_id,
                event_type="run_status_changed",
                schema_version="replay_event.v3",
                occurred_at=now,
                actor={"type": "system", "id": "run_lifecycle"},
                resource_refs={"run_id": str(run_id)},
                redaction_policy_version="redaction.v1",
                redacted_payload={"from_status": "pending", "to_status": "running"},
            ),
        ]
    )
    await session.flush()

    replay = await ReplayService(session).get_replay(run_id)

    validated = ReplayResponseV3(**replay).model_dump(mode="json")
    assert validated["schema_version"] == "replay_response.v3"
    assert validated["run_id"] == str(run_id)
    assert validated["thread_id"] == thread_id
    assert validated["final_status"] == "completed"
    assert [event["sequence"] for event in validated["timeline"]] == [1, 2]
    assert {event["schema_version"] for event in validated["timeline"]} == {"replay_event.v3"}


@pytest.mark.asyncio
async def test_get_replay_projects_minimal_rows_with_source_provenance(session: AsyncSession):
    run_id, tenant_id, thread_id = await _create_manual_run(session, final_status="interrupted")
    session.add(
        AgentTraceEvent(
            event_id=uuid.uuid4(),
            run_id=run_id,
            sequence=1,
            tenant_id=tenant_id,
            thread_id=thread_id,
            event_type="approval_requested",
            schema_version="minimal_event_envelope.v1",
            occurred_at=datetime.now(UTC),
            actor={"type": "approver", "id": "approval-service"},
            resource_refs={"approval_id": str(uuid.uuid4())},
            redaction_policy_version="redaction.v1",
            redacted_payload={"status": "pending"},
        )
    )
    await session.flush()

    replay = await ReplayService(session).get_replay(run_id)

    assert replay["schema_version"] == "replay_response.v3"
    assert replay["final_status"] == "interrupted"
    assert replay["timeline"][0]["schema_version"] == "replay_event.v3"
    assert replay["timeline"][0]["provenance"] == {
        "source_schema_version": "minimal_event_envelope.v1",
        "pairing_status": "unresolved",
    }


@pytest.mark.asyncio
async def test_get_replay_projects_legacy_minimal_operation_row_without_operation_id(
    session: AsyncSession,
):
    run_id, tenant_id, thread_id = await _create_manual_run(session, final_status="completed")
    session.add(
        AgentTraceEvent(
            event_id=uuid.uuid4(),
            run_id=run_id,
            sequence=1,
            operation_id=None,
            tenant_id=tenant_id,
            thread_id=thread_id,
            event_type="node_started",
            schema_version="minimal_event_envelope.v1",
            occurred_at=datetime.now(UTC),
            actor={"type": "agent", "id": "moca"},
            resource_refs={"node": "investigate"},
            redaction_policy_version="redaction.v1",
            redacted_payload={"status": "started"},
        )
    )
    await session.flush()

    replay = await ReplayService(session).get_replay(run_id)

    event = replay["timeline"][0]
    assert event["schema_version"] == "replay_event.v3"
    assert event["event_type"] == "node_started"
    assert event["operation_id"] is None
    assert event["provenance"] == {
        "source_schema_version": "minimal_event_envelope.v1",
        "pairing_status": "unresolved",
    }


@pytest.mark.asyncio
async def test_get_replay_projects_persisted_operation_pair_as_paired(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)
    service = ReplayService(session)
    operation_id = uuid.uuid4()

    await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="thread-replay-service",
        event_type="tool_call_started",
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool": "get_order"},
        redacted_payload={"status": "started"},
        operation_id=operation_id,
        attempt=1,
    )
    await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="thread-replay-service",
        event_type="tool_call_completed",
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool": "get_order"},
        redacted_payload={"status": "completed"},
        operation_id=operation_id,
        attempt=1,
    )

    replay = await service.get_replay(run_id)

    terminal = replay["timeline"][-1]
    assert terminal["event_type"] == "tool_call_completed"
    assert terminal["provenance"] == {
        "source_schema_version": "replay_event.v3",
        "pairing_status": "paired",
    }


@pytest.mark.asyncio
async def test_replay_service_appends_v3_event_with_retention_metadata(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)
    service = ReplayService(session)

    event = await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="thread-replay-service",
        event_type="approval_requested",
        actor={"type": "approver", "id": "approval-service"},
        resource_refs={"approval_id": str(uuid.uuid4())},
        redacted_payload={"status": "pending", "risk_level": "high"},
        schema_version="replay_event.v3",
    )

    assert event["schema_version"] == "replay_event.v3"
    assert event["event_type"] == "approval_requested"
    assert event["sequence"] == 2
    assert event["retention"]["retention_class"] == retention_for_event_type("approval_requested")
    assert event["provenance"] == {
        "source_schema_version": "replay_event.v3",
        "pairing_status": "not_applicable",
    }

    row = (
        await session.execute(select(AgentTraceEvent).where(AgentTraceEvent.event_id == event["event_id"]))
    ).scalar_one()
    assert row.schema_version == "replay_event.v3"
    assert row.redacted_payload["retention_class"] == retention_for_event_type("approval_requested")


@pytest.mark.asyncio
async def test_replay_service_rejects_unregistered_event_type(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)
    service = ReplayService(session)

    deferred_external_execution_event = "action" + "_execution_completed"
    with pytest.raises(ValueError, match="not registered"):
        await service.append_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id="thread-replay-service",
            event_type=deferred_external_execution_event,
            actor={"type": "agent", "id": "moca"},
            resource_refs={},
            redacted_payload={"status": "completed"},
            schema_version="replay_event.v3",
        )


@pytest.mark.asyncio
async def test_replay_service_validates_pairing_before_append(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)
    service = ReplayService(session)
    operation_id = uuid.uuid4()

    await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="thread-replay-service",
        event_type="tool_call_started",
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool": "get_order"},
        redacted_payload={"status": "started"},
        operation_id=operation_id,
        attempt=1,
    )
    completed = await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="thread-replay-service",
        event_type="tool_call_completed",
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool": "get_order"},
        redacted_payload={"status": "completed"},
        operation_id=operation_id,
        attempt=1,
    )

    assert completed["provenance"]["pairing_status"] == "paired"

    with pytest.raises(OperationPairingError, match="duplicate terminal"):
        await service.append_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id="thread-replay-service",
            event_type="tool_call_failed",
            actor={"type": "agent", "id": "moca"},
            resource_refs={"tool": "get_order"},
            redacted_payload={"status": "failed"},
            operation_id=operation_id,
            attempt=1,
        )


@pytest.mark.asyncio
async def test_replay_service_projects_minimal_row_as_unresolved_without_backwrite(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)
    row = AgentTraceEvent(
        event_id=uuid.uuid4(),
        run_id=run_id,
        sequence=2,
        tenant_id=tenant_id,
        thread_id="thread-replay-service",
        event_type="approval_requested",
        schema_version="minimal_event_envelope.v1",
        occurred_at=datetime.now(UTC),
        actor={"type": "approver", "id": "approval-service"},
        resource_refs={"approval_id": str(uuid.uuid4())},
        redaction_policy_version="redaction.v1",
        redacted_payload={"status": "pending"},
    )
    session.add(row)
    await session.flush()

    projected = ReplayService(session).project_event(row)

    assert projected["schema_version"] == "replay_event.v3"
    assert projected["provenance"] == {
        "source_schema_version": "minimal_event_envelope.v1",
        "pairing_status": "unresolved",
    }
    assert row.schema_version == "minimal_event_envelope.v1"
