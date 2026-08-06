"""Service boundary for replay event append, allocation, and projection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.rag_claim_summary import build_rag_claim_summary_from_sources, sanitize_rag_claim_payload
from src.db.models import (
    AgentRun,
    AgentTraceEvent,
    EvidenceSnapshotDependency,
    PolicyChunkVersion,
    PolicyDocumentVersion,
)
from src.knowledge.evidence_identity import EvidenceIdentityResolutionStatus
from src.knowledge.schemas import EvidenceRefV1
from src.repositories.evidence_version_repo import EvidenceVersionRepository
from src.replay.pairing import OperationPairingStatus, validate_operation_pairing
from src.replay.schemas import ReplayEvidenceSnapshotV1, ReplayEventV3, ReplayResponseV3
from src.replay.validators import (
    guard_redacted_payload,
    guard_resource_refs,
    retention_for_event_type,
    validate_event_type,
)


class ReplayService:
    """Own ReplayEventV3 append/projection and the shared per-run allocator."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def allocate_sequence(self, run_id: uuid.UUID | str) -> int:
        """Allocate the next strictly monotonic event sequence for a run."""
        run_uuid = _as_uuid(run_id)
        await self._lock_run(run_uuid)
        return await self._next_sequence_for_run(run_uuid)

    async def _lock_run(self, run_id: uuid.UUID) -> None:
        await self.session.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtext(:run_id_text))"),
            {"run_id_text": str(run_id)},
        )

    async def _next_sequence_for_run(self, run_id: uuid.UUID) -> int:
        result = await self.session.execute(
            sa.text(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1
                FROM agent_trace_events
                WHERE run_id = :run_id
                """
            ),
            {"run_id": run_id},
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
        canonical_evidence_refs: list[EvidenceRefV1] | None = None,
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
        guard_resource_refs(resource_refs)

        snapshots = await self._build_replay_evidence_snapshots(
            tenant_id=tenant_id,
            canonical_evidence_refs=canonical_evidence_refs,
            retention_until=retention_until,
        )

        safe_payload = dict(redacted_payload)
        safe_error = _safe_error_json(error_json)
        if iteration is not None:
            safe_payload["iteration"] = iteration
        if schema_version == "replay_event.v3":
            safe_payload.setdefault("retention_class", retention_class)

        run_uuid = _as_uuid(run_id)
        await self._lock_run(run_uuid)
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

        sequence = await self._next_sequence_for_run(run_uuid)
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
            evidence_refs_json=None,
            evidence_snapshot_refs_json=[snapshot.model_dump(mode="json") for snapshot in snapshots],
            error_json=safe_error,
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
        if schema_version == "minimal_event_envelope.v1":
            projected = self.project_minimal_event(row)
            self.session.add(row)
            await self.session.flush()
            await self._insert_snapshot_dependencies(row, snapshots)
            return projected
        self.session.add(row)
        await self.session.flush()
        await self._insert_snapshot_dependencies(row, snapshots)
        return self.project_event(row, pairing_status=pairing_status)

    async def _build_replay_evidence_snapshots(
        self,
        *,
        tenant_id: uuid.UUID | str,
        canonical_evidence_refs: list[EvidenceRefV1] | None,
        retention_until: datetime | None,
    ) -> list[ReplayEvidenceSnapshotV1]:
        """Validate typed refs and construct the sole persisted snapshot representation."""

        if canonical_evidence_refs is None:
            refs: list[EvidenceRefV1] = []
        elif not isinstance(canonical_evidence_refs, list) or any(
            not isinstance(ref, EvidenceRefV1) for ref in canonical_evidence_refs
        ):
            raise ValueError("canonical_evidence_refs must be a list[EvidenceRefV1]")
        else:
            refs = canonical_evidence_refs

        tenant_uuid = _as_uuid(tenant_id)
        expected_scope_id = str(tenant_uuid)
        repository = EvidenceVersionRepository(self.session)
        snapshots: list[ReplayEvidenceSnapshotV1] = []
        for ref in refs:
            try:
                candidate = ref.to_canonical_identity()
            except ValueError as exc:
                raise ValueError("evidence unavailable") from exc
            if candidate is None:
                raise ValueError("evidence unavailable")
            resolution = await repository.resolve_exact(
                candidate,
                expected_tenant_id=tenant_uuid,
                expected_scope_type="tenant_policy",
                expected_scope_id=expected_scope_id,
            )
            if resolution.status is not EvidenceIdentityResolutionStatus.CANONICAL or resolution.identity is None:
                raise ValueError("evidence unavailable")
            identity = resolution.identity
            document = (
                await self.session.execute(
                    sa.select(PolicyDocumentVersion).where(
                        PolicyDocumentVersion.id == _as_uuid(identity.document_version_id),
                        PolicyDocumentVersion.tenant_id == tenant_uuid,
                        PolicyDocumentVersion.scope_type == "tenant_policy",
                        PolicyDocumentVersion.scope_id == expected_scope_id,
                    )
                )
            ).scalar_one_or_none()
            chunk = (
                await self.session.execute(
                    sa.select(PolicyChunkVersion).where(
                        PolicyChunkVersion.id == _as_uuid(identity.chunk_version_id),
                        PolicyChunkVersion.tenant_id == tenant_uuid,
                        PolicyChunkVersion.policy_document_version_id == _as_uuid(identity.document_version_id),
                        PolicyChunkVersion.scope_type == "tenant_policy",
                        PolicyChunkVersion.scope_id == expected_scope_id,
                    )
                )
            ).scalar_one_or_none()
            if document is None or chunk is None:
                raise ValueError("evidence unavailable")
            canonical_ref = EvidenceRefV1.from_canonical_identity(
                identity,
                retrieved_at=ref.retrieved_at,
                retrieval_config_version=ref.retrieval_config_version,
                score=ref.score,
                rank=ref.rank,
            )
            snapshot_retention = retention_until or min(document.retention_until, chunk.retention_until)
            snapshots.append(
                ReplayEvidenceSnapshotV1(
                    canonical_evidence_ref=canonical_ref,
                    scope_type=identity.scope_type,
                    scope_id=identity.scope_id,
                    document_version_id=identity.document_version_id,
                    chunk_version_id=identity.chunk_version_id,
                    document_version=identity.document_version,
                    chunk_version=identity.chunk_version,
                    canonical_identity_hash=identity.evidence_id,
                    captured_lifecycle_status=_project_evidence_lifecycle(chunk.lifecycle_status),
                    retained_content_hash=chunk.text_hash,
                    retained_content_locator=dict(chunk.source_locator_json),
                    compatibility_provenance={
                        "resolution_status": "canonical",
                        "source": "canonical_ref_append",
                    },
                    retention_until=snapshot_retention,
                )
            )
        return snapshots

    async def _insert_snapshot_dependencies(
        self,
        event: AgentTraceEvent,
        snapshots: list[ReplayEvidenceSnapshotV1],
    ) -> None:
        if not snapshots:
            return
        self.session.add_all(
            [
                EvidenceSnapshotDependency(
                    tenant_id=event.tenant_id,
                    event_id=event.event_id,
                    document_version_id=_as_uuid(snapshot.document_version_id),
                    chunk_version_id=_as_uuid(snapshot.chunk_version_id),
                    retention_until=snapshot.retention_until,
                )
                for snapshot in snapshots
            ]
        )
        await self.session.flush()

    async def get_replay(self, run_id: uuid.UUID | str) -> dict[str, Any]:
        """Return a ReplayResponseV3 from event-store rows ordered by sequence."""
        run_uuid = _as_uuid(run_id)
        run_result = await self.session.execute(sa.select(AgentRun).where(AgentRun.id == run_uuid))
        run = run_result.scalar_one_or_none()
        if run is None:
            raise LookupError(f"AgentRun {run_uuid} not found")

        events = await self._events_for_run(run_uuid)
        timeline: list[dict[str, Any]] = []
        prior_events: list[AgentTraceEvent] = []
        rag_claim_summary = build_rag_claim_summary_from_sources([event.redacted_payload for event in events])
        for event in events:
            if event.tenant_id != run.tenant_id:
                raise LookupError("evidence unavailable")
            pairing_status: OperationPairingStatus | None = None
            if event.schema_version == "replay_event.v3":
                pairing_status = validate_operation_pairing(prior_events, event).pairing_status
            try:
                evidence_snapshots, evidence_resolution_status = await self._resolve_event_evidence_snapshots(
                    event,
                    trusted_tenant_id=run.tenant_id,
                )
            except (TypeError, ValueError) as exc:
                raise LookupError("evidence unavailable") from exc
            timeline.append(
                self.project_event(
                    event,
                    pairing_status=pairing_status,
                    include_retention_class=False,
                    evidence_snapshot_refs=evidence_snapshots,
                    evidence_resolution_status=evidence_resolution_status,
                )
            )
            prior_events.append(event)
        response = ReplayResponseV3(
            run_id=run.id,
            thread_id=run.thread_id,
            final_status=run.final_status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            timeline=timeline,
            rag_claim_summary=rag_claim_summary,
        )
        payload = response.model_dump(mode="python")
        if payload.get("rag_claim_summary") is None:
            payload.pop("rag_claim_summary", None)
        return payload

    async def _events_for_run(self, run_id: uuid.UUID) -> list[AgentTraceEvent]:
        result = await self.session.execute(
            sa.select(AgentTraceEvent).where(AgentTraceEvent.run_id == run_id).order_by(AgentTraceEvent.sequence)
        )
        return list(result.scalars().all())

    def project_minimal_event(self, event: AgentTraceEvent) -> dict[str, Any]:
        """Project stored rows into the Phase 10-14 minimal envelope shape."""
        payload = sanitize_rag_claim_payload(dict(event.redacted_payload or {}))
        refs = dict(event.resource_refs or {})
        guard_redacted_payload(payload)
        guard_resource_refs(refs)

        projection = {
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
            "resource_refs": refs,
            "evidence_snapshot_refs": _stored_evidence_snapshots(event) or None,
            "redaction_policy_version": event.redaction_policy_version,
            "redacted_payload": payload,
        }
        from src.replay.decision_events import DecisionEventEnvelopeV1

        return DecisionEventEnvelopeV1.model_validate(projection).model_dump(mode="python")

    def project_event(
        self,
        event: AgentTraceEvent,
        *,
        pairing_status: OperationPairingStatus | None = None,
        include_retention_class: bool = True,
        evidence_snapshot_refs: list[ReplayEvidenceSnapshotV1] | None = None,
        evidence_resolution_status: str | None = None,
    ) -> dict[str, Any]:
        """Project stored minimal or V3 rows into the strict ReplayEventV3 shape."""
        retention_class = retention_for_event_type(event.event_type)
        payload = sanitize_rag_claim_payload(dict(event.redacted_payload or {}))
        refs = dict(event.resource_refs or {})
        guard_redacted_payload(payload)
        guard_resource_refs(refs)
        source_schema_version = event.schema_version
        projected_snapshots = (
            _stored_evidence_snapshots(event) if evidence_snapshot_refs is None else evidence_snapshot_refs
        )
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
            "resource_refs": refs,
            "evidence_snapshot_refs": projected_snapshots,
            "redacted_payload": payload,
            "redaction_policy_version": event.redaction_policy_version,
            "provenance": {
                "source_schema_version": source_schema_version,
                "pairing_status": _projected_pairing_status(source_schema_version, pairing_status),
                "evidence_resolution_status": evidence_resolution_status,
            },
            "retention": {
                "archived_at": event.archived_at,
                "retention_until": event.retention_until,
                "deleted_at": event.deleted_at,
            },
            "error": _safe_error_json(event.error_json),
        }
        event_dict = ReplayEventV3(**projection).model_dump(mode="python")
        if include_retention_class:
            event_dict["retention"]["retention_class"] = retention_class
        return event_dict

    async def _resolve_event_evidence_snapshots(
        self,
        event: AgentTraceEvent,
        *,
        trusted_tenant_id: uuid.UUID,
    ) -> tuple[list[ReplayEvidenceSnapshotV1], str | None]:
        stored = _stored_evidence_snapshots(event)
        if stored:
            resolved = [
                await self._resolve_stored_evidence_snapshot(
                    snapshot,
                    trusted_tenant_id=trusted_tenant_id,
                )
                for snapshot in stored
            ]
            return resolved, "canonical"
        if event.evidence_refs_json:
            return await self.resolve_persisted_legacy_event_evidence(
                event.event_id,
                trusted_tenant_id=trusted_tenant_id,
            )
        return [], None

    async def _resolve_stored_evidence_snapshot(
        self,
        snapshot: ReplayEvidenceSnapshotV1,
        *,
        trusted_tenant_id: uuid.UUID,
    ) -> ReplayEvidenceSnapshotV1:
        identity = snapshot.canonical_evidence_ref.to_canonical_identity()
        if identity is None:
            raise ValueError("evidence unavailable")
        resolution = await EvidenceVersionRepository(self.session).resolve_exact(
            identity,
            expected_tenant_id=trusted_tenant_id,
            expected_scope_type="tenant_policy",
            expected_scope_id=str(trusted_tenant_id),
        )
        if (
            resolution.status is not EvidenceIdentityResolutionStatus.CANONICAL
            or resolution.identity is None
            or resolution.identity != identity
        ):
            raise ValueError("evidence unavailable")
        document, chunk = await self._retained_evidence_material(
            resolution.identity,
            trusted_tenant_id=trusted_tenant_id,
        )
        if snapshot.retained_content_hash != chunk.text_hash or snapshot.retained_content_locator != dict(
            chunk.source_locator_json
        ):
            raise ValueError("evidence unavailable")
        lifecycle = await self._current_evidence_lifecycle(document, chunk)
        return snapshot.model_copy(
            update={
                "retained_content": chunk.content,
                "current_lifecycle_status": lifecycle,
            }
        )

    async def resolve_persisted_legacy_event_evidence(
        self,
        event_id: uuid.UUID | str,
        *,
        trusted_tenant_id: uuid.UUID | str,
    ) -> tuple[list[ReplayEvidenceSnapshotV1], str]:
        """Read-only adapter for evidence JSON that was persisted before Phase 64.2."""

        tenant_uuid = _as_uuid(trusted_tenant_id)
        event = (
            await self.session.execute(
                sa.select(AgentTraceEvent).where(
                    AgentTraceEvent.event_id == _as_uuid(event_id),
                    AgentTraceEvent.tenant_id == tenant_uuid,
                )
            )
        ).scalar_one_or_none()
        if event is None or not event.evidence_refs_json or event.evidence_snapshot_refs_json:
            return [], "legacy_unresolved"

        repository = EvidenceVersionRepository(self.session)
        snapshots: list[ReplayEvidenceSnapshotV1] = []
        for raw_ref in event.evidence_refs_json:
            if not isinstance(raw_ref, dict):
                return [], "legacy_unresolved"
            try:
                legacy_ref = EvidenceRefV1.model_validate(raw_ref)
            except ValueError:
                return [], "legacy_unresolved"
            if legacy_ref.to_canonical_identity() is not None:
                return [], "legacy_unresolved"
            resolution = await repository.resolve_legacy_alias(
                legacy_ref.evidence_id,
                expected_tenant_id=tenant_uuid,
                expected_scope_type="tenant_policy",
                expected_scope_id=str(tenant_uuid),
            )
            identity = resolution.identity
            if (
                resolution.status is not EvidenceIdentityResolutionStatus.LEGACY_RESOLVED
                or identity is None
                or legacy_ref.tenant_id != str(tenant_uuid)
                or legacy_ref.doc_key != identity.doc_key
                or legacy_ref.chunk_id != identity.chunk_id
                or legacy_ref.policy_version != f"v{identity.document_version}"
                or legacy_ref.text_hash != identity.text_hash
            ):
                return [], "legacy_unresolved"
            document, chunk = await self._retained_evidence_material(
                identity,
                trusted_tenant_id=tenant_uuid,
            )
            canonical_ref = EvidenceRefV1.from_canonical_identity(
                identity,
                retrieved_at=legacy_ref.retrieved_at,
                retrieval_config_version=legacy_ref.retrieval_config_version,
                score=legacy_ref.score,
                rank=legacy_ref.rank,
            )
            lifecycle = await self._current_evidence_lifecycle(document, chunk)
            snapshots.append(
                ReplayEvidenceSnapshotV1(
                    canonical_evidence_ref=canonical_ref,
                    scope_type=identity.scope_type,
                    scope_id=identity.scope_id,
                    document_version_id=identity.document_version_id,
                    chunk_version_id=identity.chunk_version_id,
                    document_version=identity.document_version,
                    chunk_version=identity.chunk_version,
                    canonical_identity_hash=identity.evidence_id,
                    captured_lifecycle_status=lifecycle,
                    retained_content_hash=chunk.text_hash,
                    retained_content_locator=dict(chunk.source_locator_json),
                    compatibility_provenance={
                        "resolution_status": "legacy_resolved",
                        "source": "persisted_legacy_event",
                    },
                    retention_until=min(document.retention_until, chunk.retention_until),
                    retained_content=chunk.content,
                    current_lifecycle_status=lifecycle,
                )
            )
        return snapshots, "legacy_resolved"

    async def _retained_evidence_material(
        self,
        identity: Any,
        *,
        trusted_tenant_id: uuid.UUID,
    ) -> tuple[PolicyDocumentVersion, PolicyChunkVersion]:
        expected_scope_id = str(trusted_tenant_id)
        document = (
            await self.session.execute(
                sa.select(PolicyDocumentVersion).where(
                    PolicyDocumentVersion.id == _as_uuid(identity.document_version_id),
                    PolicyDocumentVersion.tenant_id == trusted_tenant_id,
                    PolicyDocumentVersion.scope_type == "tenant_policy",
                    PolicyDocumentVersion.scope_id == expected_scope_id,
                )
            )
        ).scalar_one_or_none()
        chunk = (
            await self.session.execute(
                sa.select(PolicyChunkVersion).where(
                    PolicyChunkVersion.id == _as_uuid(identity.chunk_version_id),
                    PolicyChunkVersion.tenant_id == trusted_tenant_id,
                    PolicyChunkVersion.policy_document_version_id == _as_uuid(identity.document_version_id),
                    PolicyChunkVersion.scope_type == "tenant_policy",
                    PolicyChunkVersion.scope_id == expected_scope_id,
                )
            )
        ).scalar_one_or_none()
        if document is None or chunk is None:
            raise ValueError("evidence unavailable")
        return document, chunk

    async def _current_evidence_lifecycle(
        self,
        document: PolicyDocumentVersion,
        chunk: PolicyChunkVersion,
    ) -> str:
        explicit = [
            _project_evidence_lifecycle(document.lifecycle_status),
            _project_evidence_lifecycle(chunk.lifecycle_status),
        ]
        for status in ("tombstoned", "expired", "archived", "corrected", "superseded"):
            if status in explicit:
                return status
        corrected = await self.session.scalar(
            sa.select(
                sa.exists().where(
                    PolicyChunkVersion.tenant_id == chunk.tenant_id,
                    PolicyChunkVersion.corrects_version_id == chunk.id,
                )
            )
        )
        if corrected:
            return "corrected"
        superseded = await self.session.scalar(
            sa.select(
                sa.exists().where(
                    PolicyChunkVersion.tenant_id == chunk.tenant_id,
                    PolicyChunkVersion.supersedes_version_id == chunk.id,
                )
            )
        )
        return "superseded" if superseded else "current"


def _as_uuid(value: uuid.UUID | str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _safe_error_json(error_json: dict[str, Any] | None) -> dict[str, Any] | None:
    if error_json is None:
        return None
    guard_redacted_payload({"error": error_json})
    code = str(error_json.get("code") or "REPLAY_EVENT_ERROR")[:64]
    safe_message = str(error_json.get("safe_message") or code)[:256]
    return {
        "code": code,
        "message": safe_message,
        "retryable": error_json.get("retryable") is True,
    }


def _projected_pairing_status(
    source_schema_version: str,
    pairing_status: OperationPairingStatus | None,
) -> str:
    if source_schema_version == "minimal_event_envelope.v1":
        return OperationPairingStatus.UNRESOLVED.value
    if pairing_status is None:
        return OperationPairingStatus.UNRESOLVED.value
    return pairing_status.value


def _project_evidence_lifecycle(value: str) -> str:
    if value == "active":
        return "current"
    if value in {"superseded", "corrected", "archived", "expired", "tombstoned"}:
        return value
    raise ValueError("evidence unavailable")


def _stored_evidence_snapshots(event: AgentTraceEvent) -> list[ReplayEvidenceSnapshotV1]:
    return [ReplayEvidenceSnapshotV1.model_validate(snapshot) for snapshot in (event.evidence_snapshot_refs_json or [])]
