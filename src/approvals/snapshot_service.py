"""Durable ActionSafetySnapshot persistence seam for approvals and risk gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.repository import ApprovalRepository
from src.approvals.schemas import PROPOSED_ACTION_SCHEMA_VERSION
from src.approvals.snapshots import ActionSafetySnapshot, build_action_safety_snapshot
from src.common.canonical_hash import canonical_hash
from src.knowledge.schemas import EvidenceRefV1

PROPOSED_ACTION_HASH_FIELDS = {
    "schema_version",
    "tenant_id",
    "run_id",
    "action_id",
    "action_type",
    "target_type",
    "target_id",
    "amount",
    "currency",
    "args",
    "reason",
    "evidence_refs",
}


class ActionSafetySnapshotPersistenceError(ValueError):
    """Raised when snapshot persistence cannot be verified."""


@dataclass(frozen=True)
class PersistedActionSafetySnapshot:
    action_payload_hash: str
    safety_snapshot_ref: str
    safety_snapshot_hash: str
    snapshot: ActionSafetySnapshot


def compute_action_payload_hash(proposed_action: dict[str, Any]) -> str:
    return canonical_hash(
        proposed_action,
        schema_version=PROPOSED_ACTION_SCHEMA_VERSION,
        allowed_fields=PROPOSED_ACTION_HASH_FIELDS,
        nullable_fields={"amount", "currency"},
    )


async def persist_action_safety_snapshot(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    proposed_action: dict[str, Any],
    action_payload_hash: str | None,
    policy_config_version: str,
    risk_config_version: str,
    retrieval_config_version: str,
    evidence_refs: list[EvidenceRefV1],
    created_at,
    created_by: UUID | None = None,
    repository: ApprovalRepository | None = None,
) -> PersistedActionSafetySnapshot:
    repo = repository or ApprovalRepository(session)
    computed_hash = compute_action_payload_hash(proposed_action)
    if action_payload_hash is not None and action_payload_hash != computed_hash:
        raise ActionSafetySnapshotPersistenceError("action_payload_hash mismatch")

    snapshot_id = str(uuid4())
    snapshot = build_action_safety_snapshot(
        tenant_id=str(tenant_id),
        run_id=str(run_id),
        snapshot_id=snapshot_id,
        snapshot_ref=f"snapshot:{snapshot_id}",
        policy_config_version=policy_config_version,
        risk_config_version=risk_config_version,
        retrieval_config_version=retrieval_config_version,
        evidence=evidence_refs,
        action_payload_hash=computed_hash,
        created_at=created_at,
    )
    row = await repo.create_snapshot_row(snapshot, created_by=created_by)
    if row.action_payload_hash != computed_hash:
        raise ActionSafetySnapshotPersistenceError("persisted snapshot action hash mismatch")

    reloaded = await repo.get_snapshot_by_ref_or_hash(
        tenant_id=tenant_id,
        safety_snapshot_ref=row.snapshot_ref,
        safety_snapshot_hash=row.immutable_hash,
    )
    if reloaded is None:
        raise ActionSafetySnapshotPersistenceError("persisted snapshot could not be reloaded")

    return PersistedActionSafetySnapshot(
        action_payload_hash=computed_hash,
        safety_snapshot_ref=row.snapshot_ref,
        safety_snapshot_hash=row.immutable_hash,
        snapshot=snapshot,
    )
