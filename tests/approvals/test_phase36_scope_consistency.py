from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.repository import ApprovalRepository
from src.approvals.snapshot_service import (
    ActionSafetySnapshotPersistenceError,
    compute_action_payload_hash,
    persist_action_safety_snapshot,
)
from src.approvals.snapshots import (
    build_action_safety_snapshot,
    snapshot_hash_projection,
)
from src.db.models import ActionSafetySnapshot as ActionSafetySnapshotRow
from tests.approvals.test_service_transitions import (
    _create_command,
    _create_run,
    _evidence_ref,
    _phase34_binding_overrides,
)


def _hashable_binding_payload(value: dict) -> dict:
    normalized = dict(value)
    business_fact_ref = dict(normalized["business_fact_ref"])
    for key in ("data_freshness_at", "retrieved_at"):
        if isinstance(business_fact_ref.get(key), str) and business_fact_ref[key].endswith("Z"):
            parsed = datetime.fromisoformat(business_fact_ref[key].replace("Z", "+00:00"))
            business_fact_ref[key] = parsed.strftime("%Y-%m-%dT%H:%M:%S.") + f"{parsed.microsecond // 1000:03d}Z"
    normalized["business_fact_ref"] = business_fact_ref
    return normalized


def _hashable_business_fact_refs(values: list[dict]) -> list[dict]:
    normalized_refs = []
    for value in values:
        normalized = dict(value)
        for key in ("data_freshness_at", "retrieved_at"):
            if isinstance(normalized.get(key), str) and normalized[key].endswith("Z"):
                parsed = datetime.fromisoformat(normalized[key].replace("Z", "+00:00"))
                normalized[key] = parsed.strftime("%Y-%m-%dT%H:%M:%S.") + f"{parsed.microsecond // 1000:03d}Z"
        normalized_refs.append(normalized)
    return normalized_refs


def test_action_safety_snapshot_contract_accepts_target_merchant_proof() -> None:
    tenant_id = "11111111-1111-1111-1111-111111111111"
    run_id = "22222222-2222-2222-2222-222222222222"
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)

    snapshot = build_action_safety_snapshot(
        tenant_id=tenant_id,
        run_id=run_id,
        snapshot_id="snapshot-1",
        snapshot_ref="snapshot:snapshot-1",
        policy_config_version="approval-policy.v1",
        risk_config_version="risk-rules.v1",
        retrieval_config_version="retrieval.v1",
        evidence=[_evidence_ref(tenant_id=tenant_id)],
        action_payload_hash="sha256:" + "1" * 64,
        target_merchant_id=binding["target_merchant_id"],
        target_merchant_ref=binding["target_merchant_ref"],
        business_fact_refs=binding["business_fact_refs"],
        created_at=datetime(2026, 6, 30, 0, 0, tzinfo=UTC),
    )

    assert snapshot.target_merchant_id == "merchant-1"
    assert snapshot.target_merchant_ref.model_dump(mode="json") == binding["target_merchant_ref"]
    assert [ref.model_dump(mode="json") for ref in snapshot.business_fact_refs] == binding["business_fact_refs"]


def test_snapshot_hash_projection_includes_target_merchant_binding_material() -> None:
    tenant_id = "11111111-1111-1111-1111-111111111111"
    run_id = "22222222-2222-2222-2222-222222222222"
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)
    snapshot = build_action_safety_snapshot(
        tenant_id=tenant_id,
        run_id=run_id,
        snapshot_id="snapshot-1",
        snapshot_ref="snapshot:snapshot-1",
        policy_config_version="approval-policy.v1",
        risk_config_version="risk-rules.v1",
        retrieval_config_version="retrieval.v1",
        evidence=[_evidence_ref(tenant_id=tenant_id)],
        action_payload_hash="sha256:" + "1" * 64,
        target_merchant_id=binding["target_merchant_id"],
        target_merchant_ref=binding["target_merchant_ref"],
        business_fact_refs=binding["business_fact_refs"],
        created_at=datetime(2026, 6, 30, 0, 0, tzinfo=UTC),
    )

    projection = snapshot_hash_projection(snapshot)

    assert projection["target_merchant_id"] == "merchant-1"
    assert projection["target_merchant_ref"] == _hashable_binding_payload(binding["target_merchant_ref"])
    assert projection["business_fact_refs"] == _hashable_business_fact_refs(binding["business_fact_refs"])


def test_action_safety_snapshot_row_declares_target_merchant_columns_and_index() -> None:
    columns = ActionSafetySnapshotRow.__table__.c
    index_names = {index.name for index in ActionSafetySnapshotRow.__table__.indexes}

    assert "target_merchant_id" in columns
    assert "target_merchant_ref" in columns
    assert "business_fact_refs" in columns
    assert "ix_action_safety_snapshots_tenant_target_merchant" in index_names


@pytest.mark.asyncio
async def test_persist_action_safety_snapshot_stores_and_reloads_target_merchant_proof(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)
    command = _create_command(tenant_id=tenant_id, run_id=run_id, requested_by=requested_by, **binding)
    action_payload_hash = compute_action_payload_hash(command.proposed_action)

    persisted = await persist_action_safety_snapshot(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        proposed_action=command.proposed_action,
        action_payload_hash=action_payload_hash,
        policy_config_version=command.policy_config_version,
        risk_config_version=command.risk_config_version,
        retrieval_config_version=command.retrieval_config_version,
        evidence_refs=command.evidence_refs,
        target_merchant_id=binding["target_merchant_id"],
        target_merchant_ref=binding["target_merchant_ref"],
        business_fact_refs=binding["business_fact_refs"],
        created_at=command.created_at,
        created_by=requested_by,
    )

    row = (
        await session.execute(select(ActionSafetySnapshotRow).where(ActionSafetySnapshotRow.run_id == run_id))
    ).scalar_one()
    assert row.target_merchant_id == binding["target_merchant_id"]
    assert row.target_merchant_ref == binding["target_merchant_ref"]
    assert row.business_fact_refs == binding["business_fact_refs"]

    reloaded = await ApprovalRepository(session).get_snapshot_by_ref_or_hash(
        tenant_id=tenant_id,
        safety_snapshot_ref=persisted.safety_snapshot_ref,
        safety_snapshot_hash=persisted.safety_snapshot_hash,
    )
    assert reloaded is not None
    assert reloaded.target_merchant_id == binding["target_merchant_id"]
    assert reloaded.target_merchant_ref == binding["target_merchant_ref"]
    assert reloaded.business_fact_refs == binding["business_fact_refs"]


@pytest.mark.asyncio
async def test_persist_action_safety_snapshot_rejects_action_bound_snapshot_without_target_binding(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)
    command = _create_command(tenant_id=tenant_id, run_id=run_id, requested_by=requested_by, **binding)

    with pytest.raises(ActionSafetySnapshotPersistenceError, match="target merchant binding"):
        await persist_action_safety_snapshot(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            proposed_action=command.proposed_action,
            action_payload_hash=compute_action_payload_hash(command.proposed_action),
            policy_config_version=command.policy_config_version,
            risk_config_version=command.risk_config_version,
            retrieval_config_version=command.retrieval_config_version,
            evidence_refs=command.evidence_refs,
            created_at=command.created_at,
            created_by=requested_by,
        )

    assert (
        await session.execute(select(ActionSafetySnapshotRow).where(ActionSafetySnapshotRow.run_id == run_id))
    ).scalars().all() == []
