"""Service boundary for replay event append, allocation, and projection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentTraceEvent
from src.replay.pairing import OperationPairingStatus, validate_operation_pairing
from src.replay.schemas import ReplayEventV3
from src.replay.validators import guard_redacted_payload, retention_for_event_type, validate_event_type


class ReplayService:
    """Own ReplayEventV3 append/projection and the shared per-run allocator."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def allocate_sequence(self, run_id: uuid.UUID | str) -> int:
        """Allocate the next strictly monotonic event sequence for a run."""
        run_uuid = _as_uuid(run_id)
        await self.session.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtext(:run_id_text))"),
            {"run_id_text": str(run_uuid)},
        )
        result = await self.session.execute(
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

    async def append_event(
        self,
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
        parent_operation_id: uuid.UUID | str | None = None,
        attempt: int | None = None,
        version: int | None = 1,
        node_name: str | None = None,
        approval_id: uuid.UUID | str | None = None,
        draft_id: uuid.UUID | str | None = None,
        tool_call_id: str | None = None,
        evidence_refs_json: list[dict[str, Any]] | None = None,
        error_json: dict[str, Any] | None = None,
        archived_at: datetime | None = None,
        retention_until: datetime | None = None,
        deleted_at: datetime | None = None,
        schema_version: str = "replay_event.v3",
        occurred_at: datetime | None = None,
        redaction_policy_version: str = "redaction.v1",
        iteration: int | None = None,
    ) -> dict[str, Any]:
        """Persist one event row and return its V3 projection."""
        validate_event_type(event_type)
        retention_class = retention_for_event_type(event_type)
        guard_redacted_payload(redacted_payload)

        safe_payload = dict(redacted_payload)
        if iteration is not None:
            safe_payload["iteration"] = iteration
        if schema_version == "replay_event.v3":
            safe_payload.setdefault("retention_class", retention_class)

        run_uuid = _as_uuid(run_id)
        existing_events = await self._events_for_run(run_uuid)
        pairing_status: OperationPairingStatus | None = None
        if schema_version == "replay_event.v3":
            pairing_result = validate_operation_pairing(
                existing_events,
                {
                    "event_type": event_type,
                    "operation_id": operation_id,
                    "parent_operation_id": parent_operation_id,
                    "attempt": attempt,
                    "redacted_payload": safe_payload,
                },
            )
            pairing_status = pairing_result.pairing_status

        sequence = await self.allocate_sequence(run_uuid)
        event_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{run_uuid}:{sequence}")
        row = AgentTraceEvent(
            event_id=event_id,
            run_id=run_uuid,
            sequence=sequence,
            operation_id=_as_uuid(operation_id) if operation_id is not None else None,
            parent_operation_id=_as_uuid(parent_operation_id) if parent_operation_id is not None else None,
            attempt=attempt,
            version=version,
            node_name=node_name,
            approval_id=_as_uuid(approval_id) if approval_id is not None else None,
            draft_id=_as_uuid(draft_id) if draft_id is not None else None,
            tool_call_id=tool_call_id,
            evidence_refs_json=evidence_refs_json,
            error_json=error_json,
            tenant_id=_as_uuid(tenant_id),
            thread_id=thread_id,
            trace_id=trace_id,
            event_type=event_type,
            schema_version=schema_version,
            occurred_at=occurred_at or datetime.now(UTC),
            actor=actor,
            resource_refs=resource_refs,
            redaction_policy_version=redaction_policy_version,
            redacted_payload=safe_payload,
            archived_at=archived_at,
            retention_until=retention_until,
            deleted_at=deleted_at,
        )
        self.session.add(row)
        await self.session.flush()
        if schema_version == "minimal_event_envelope.v1":
            return self.project_minimal_event(row)
        return self.project_event(row, pairing_status=pairing_status)

    async def _events_for_run(self, run_id: uuid.UUID) -> list[AgentTraceEvent]:
        result = await self.session.execute(
            sa.select(AgentTraceEvent)
            .where(AgentTraceEvent.run_id == run_id)
            .order_by(AgentTraceEvent.sequence)
        )
        return list(result.scalars().all())

    def project_minimal_event(self, event: AgentTraceEvent) -> dict[str, Any]:
        """Project stored rows into the Phase 10-14 minimal envelope shape."""
        return {
            "schema_version": event.schema_version,
            "event_id": event.event_id,
            "sequence": event.sequence,
            "operation_id": event.operation_id,
            "run_id": event.run_id,
            "tenant_id": event.tenant_id,
            "thread_id": event.thread_id,
            "trace_id": event.trace_id,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at,
            "actor": event.actor,
            "resource_refs": event.resource_refs,
            "redaction_policy_version": event.redaction_policy_version,
            "redacted_payload": event.redacted_payload,
        }

    def project_event(
        self,
        event: AgentTraceEvent,
        *,
        pairing_status: OperationPairingStatus | None = None,
    ) -> dict[str, Any]:
        """Project stored minimal or V3 rows into the strict ReplayEventV3 shape."""
        retention_class = retention_for_event_type(event.event_type)
        payload = dict(event.redacted_payload or {})
        guard_redacted_payload(payload)
        source_schema_version = event.schema_version
        projection = {
            "schema_version": "replay_event.v3",
            "event_id": event.event_id,
            "run_id": event.run_id,
            "tenant_id": event.tenant_id,
            "thread_id": event.thread_id,
            "trace_id": event.trace_id,
            "sequence": event.sequence,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at,
            "operation_id": event.operation_id,
            "parent_operation_id": event.parent_operation_id,
            "attempt": event.attempt,
            "node_name": event.node_name,
            "actor": event.actor,
            "resource_refs": event.resource_refs,
            "redacted_payload": payload,
            "redaction_policy_version": event.redaction_policy_version,
            "provenance": {
                "source_schema_version": source_schema_version,
                "pairing_status": _projected_pairing_status(source_schema_version, pairing_status),
            },
            "retention": {
                "archived_at": event.archived_at,
                "retention_until": event.retention_until,
                "deleted_at": event.deleted_at,
            },
            "error": event.error_json,
        }
        event_dict = ReplayEventV3(**projection).model_dump(mode="python")
        event_dict["retention"]["retention_class"] = retention_class
        return event_dict


def _as_uuid(value: uuid.UUID | str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _projected_pairing_status(
    source_schema_version: str,
    pairing_status: OperationPairingStatus | None,
) -> str:
    if source_schema_version == "minimal_event_envelope.v1":
        return OperationPairingStatus.UNRESOLVED.value
    if pairing_status is None:
        return OperationPairingStatus.UNRESOLVED.value
    return pairing_status.value
