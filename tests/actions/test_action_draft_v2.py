from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.schema import ColumnCollectionConstraint

from src.actions.drafts import ActionDraftStore
from src.actions.schemas import ActionDraftV2Data, DraftOutcomeV1
from src.agent.trace import write_agent_run


MIGRATION_PATH = Path("src/db/migrations/versions/009_action_draft_v2.py")
PHASE34_MIGRATION_PATH = Path("src/db/migrations/versions/018_phase34_approval_action_bindings.py")
ACTION_DRAFT_V2_COLUMNS = {
    "schema_version",
    "target_id",
    "approval_revision_ref",
    "action_payload_hash",
    "safety_snapshot_ref",
    "safety_snapshot_hash",
    "draft_outcome",
    "execution_mode",
    "draft_version",
    "lifecycle_status",
    "retention_policy",
}
PHASE34_ACTION_DRAFT_BINDING_COLUMNS = {
    "target_merchant_id",
    "target_merchant_ref",
    "business_fact_refs",
    "verified_evidence_refs",
    "claim_verification_ref",
    "claim_verification_summary",
    "risk_decision_ref",
    "risk_decision",
    "auto_allowed_binding_ref",
}
PHASE17_EXTERNAL_SURFACES = (
    "action_executions",
    "action_outbox_events",
    "action_reconciliation_jobs",
    "action_compensation_records",
)


def _draft_payload() -> dict[str, object]:
    return {
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "draft_id": "draft-1",
        "proposed_action": {
            "schema_version": "proposed_action.v1",
            "action_type": "issue_coupon",
            "target_id": "RF-1001",
        },
        "action_payload_hash": "sha256:" + "a" * 64,
        "approval_ref": "approval_request/approval-1",
        "approval_revision_ref": "approval_request/approval-1@rev1",
        "safety_snapshot_ref": "action_safety_snapshot/snap-1",
        "safety_snapshot_hash": "sha256:" + "b" * 64,
        "target_id": "RF-1001",
        "idempotency_key": "tenant-1:run-1:rev1:issue_coupon:RF-1001:sha256-aaaa",
        "status": "draft_created",
        "execution_mode": "demo",
        "draft_outcome": DraftOutcomeV1().model_dump(mode="json"),
    }


async def _create_run(session: AsyncSession, *, tenant_id: UUID, user_id: UUID | None = None) -> UUID:
    run_id = uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=f"action-draft-v2-{run_id}",
        tenant_id=str(tenant_id),
        user_id=str(user_id or uuid4()),
        input_query="action draft v2 contract",
        final_status="completed",
        final_response="ok",
        started_at=now,
        completed_at=now,
        total_latency_ms=1,
    )
    return run_id


def _draft_outcome(*, tenant_id: UUID, run_id: UUID, draft_id: str | None = None) -> dict[str, object]:
    return DraftOutcomeV1(
        tenant_id=str(tenant_id),
        run_id=str(run_id),
        draft_id=draft_id,
        created_at="2026-06-16T00:00:00.000Z",
    ).model_dump(mode="json")


async def _create_store_draft(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    run_id: UUID | None = None,
    idempotency_key: str = "tenant:run:auto_allowed:issue_coupon:RF-1001:sha256-a",
    target_id: str = "RF-1001",
    action_payload_hash: str = "sha256:" + "a" * 64,
    safety_snapshot_ref: str = "action_safety_snapshot/snap-1",
    safety_snapshot_hash: str = "sha256:" + "b" * 64,
):
    tenant_uuid = tenant_id or uuid4()
    run_uuid = run_id or await _create_run(session, tenant_id=tenant_uuid)
    return await ActionDraftStore(session).create_or_get(
        run_id=run_uuid,
        tenant_id=tenant_uuid,
        approval_request_id=None,
        idempotency_key=idempotency_key,
        action_type="issue_coupon",
        target_id=target_id,
        approval_revision_ref="auto_allowed",
        action_payload_hash=action_payload_hash,
        safety_snapshot_ref=safety_snapshot_ref,
        safety_snapshot_hash=safety_snapshot_hash,
        payload={"target_id": target_id, "amount": "25.00", "currency": "CNY"},
        draft_outcome=_draft_outcome(tenant_id=tenant_uuid, run_id=run_uuid),
        execution_mode="demo",
        draft_version=1,
        lifecycle_status="active",
        retention_policy="phase14_demo_draft",
    )


def _table(name: str):
    from src.db.models import Base

    assert name in Base.metadata.tables
    return Base.metadata.tables[name]


def _column_names(table_name: str) -> set[str]:
    return set(_table(table_name).c.keys())


def _named_schema_items(table_name: str) -> dict[str, UniqueConstraint | Index]:
    table = _table(table_name)
    return {item.name: item for item in [*table.constraints, *table.indexes] if item.name}


def _item_columns(item: UniqueConstraint | Index) -> set[str]:
    if isinstance(item, ColumnCollectionConstraint | Index):
        return {column.name for column in item.columns}
    return set()


def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), "migration 009 must exist"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _phase34_migration_source() -> str:
    assert PHASE34_MIGRATION_PATH.exists(), "migration 018 must exist"
    return PHASE34_MIGRATION_PATH.read_text(encoding="utf-8")


def test_draft_outcome_v1_defaults_to_not_executed_demo():
    outcome = DraftOutcomeV1()

    assert outcome.schema_version == "draft_outcome.v1"
    assert outcome.status == "not_executed_demo"
    assert outcome.external_side_effect is False


@pytest.mark.parametrize(
    "missing_field",
    [
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
        "target_id",
        "approval_revision_ref",
        "draft_outcome",
        "execution_mode",
    ],
)
def test_action_draft_v2_data_requires_phase14_binding_fields(missing_field: str):
    payload = _draft_payload()
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        ActionDraftV2Data.model_validate(payload)


def test_action_draft_v2_data_rejects_unknown_fields():
    payload = _draft_payload()
    payload["unexpected"] = "blocked"

    with pytest.raises(ValidationError):
        ActionDraftV2Data.model_validate(payload)


def test_action_draft_v2_data_exposes_demo_contract_literals():
    draft = ActionDraftV2Data.model_validate(_draft_payload())

    assert draft.schema_version == "action_draft.v2"
    assert draft.execution_mode == "demo"
    assert draft.draft_outcome.schema_version == "draft_outcome.v1"
    assert draft.draft_outcome.status == "not_executed_demo"
    assert draft.draft_outcome.external_side_effect is False


def test_action_drafts_orm_declares_action_draft_v2_columns_and_payload_mapping():
    table = _table("action_drafts")

    assert ACTION_DRAFT_V2_COLUMNS.issubset(_column_names("action_drafts"))
    assert "payload" in table.c, "contract proposed_action is stored in the existing payload JSONB column"
    assert "proposed_action" not in table.c
    assert table.c["draft_outcome"].nullable


def test_action_drafts_orm_declares_phase34_binding_columns():
    table = _table("action_drafts")

    assert PHASE34_ACTION_DRAFT_BINDING_COLUMNS.issubset(_column_names("action_drafts"))
    assert table.c["target_merchant_id"].nullable
    assert table.c["business_fact_refs"].nullable
    assert table.c["verified_evidence_refs"].nullable
    source = _phase34_migration_source()
    for column in PHASE34_ACTION_DRAFT_BINDING_COLUMNS:
        assert f'"{column}"' in source


def test_action_drafts_orm_uses_tenant_scoped_idempotency_uniqueness():
    items = _named_schema_items("action_drafts")

    assert _item_columns(items["uq_action_drafts_tenant_idempotency_key"]) == {"tenant_id", "idempotency_key"}
    assert "uq_action_drafts_idempotency_key" not in items
    assert not _table("action_drafts").c["idempotency_key"].unique


def test_sqlalchemy_metadata_declares_no_phase17_external_execution_tables():
    from src.db.models import Base

    table_names = set(Base.metadata.tables)

    assert table_names.isdisjoint(PHASE17_EXTERNAL_SURFACES)


def test_migration_009_revises_phase13_head_and_adds_matching_action_draft_columns():
    source = _migration_source()

    assert 'revision: str = "009_action_draft_v2"' in source
    assert 'down_revision: str | None = "008_approval_state_machine"' in source
    for column in ACTION_DRAFT_V2_COLUMNS:
        assert f'"{column}"' in source
    assert "uq_action_drafts_tenant_idempotency_key" in source


def test_migration_009_does_not_create_phase17_external_execution_surfaces():
    source = _migration_source()

    for forbidden in PHASE17_EXTERNAL_SURFACES:
        assert forbidden not in source


@pytest.mark.asyncio
async def test_action_draft_store_persists_v2_binding_and_outcome_fields(session: AsyncSession):
    tenant_id = uuid4()
    run_id = await _create_run(session, tenant_id=tenant_id)

    draft, created = await _create_store_draft(session, tenant_id=tenant_id, run_id=run_id)

    assert created is True
    assert draft.schema_version == "action_draft.v2"
    assert draft.target_id == "RF-1001"
    assert draft.action_payload_hash == "sha256:" + "a" * 64
    assert draft.safety_snapshot_ref == "action_safety_snapshot/snap-1"
    assert draft.safety_snapshot_hash == "sha256:" + "b" * 64
    assert draft.approval_revision_ref == "auto_allowed"
    assert draft.execution_mode == "demo"
    assert draft.draft_outcome["status"] == "not_executed_demo"
    assert draft.draft_outcome["external_side_effect"] is False


@pytest.mark.asyncio
async def test_action_draft_store_exact_key_reuse_returns_existing_draft(session: AsyncSession):
    tenant_id = uuid4()
    run_id = await _create_run(session, tenant_id=tenant_id)

    draft, created = await _create_store_draft(session, tenant_id=tenant_id, run_id=run_id)
    reused, reused_created = await _create_store_draft(session, tenant_id=tenant_id, run_id=run_id)

    assert created is True
    assert reused_created is False
    assert reused.id == draft.id


@pytest.mark.asyncio
async def test_action_draft_store_concurrent_exact_key_reuse_returns_existing_draft(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    tenant_id = uuid4()
    async with session_factory() as setup_session:
        run_id = await _create_run(setup_session, tenant_id=tenant_id)
        await setup_session.commit()

    async def create_draft() -> tuple[UUID, bool]:
        async with session_factory() as worker_session:
            draft, created = await _create_store_draft(
                worker_session,
                tenant_id=tenant_id,
                run_id=run_id,
                idempotency_key="concurrent-draft-key",
            )
            await worker_session.commit()
            return draft.id, created

    results = await asyncio.gather(create_draft(), create_draft())

    assert {draft_id for draft_id, _created in results} == {results[0][0]}
    assert sorted(created for _draft_id, created in results) == [False, True]


@pytest.mark.asyncio
async def test_action_draft_store_key_hit_with_mismatched_snapshot_hash_conflicts(session: AsyncSession):
    tenant_id = uuid4()
    run_id = await _create_run(session, tenant_id=tenant_id)
    await _create_store_draft(session, tenant_id=tenant_id, run_id=run_id)

    with pytest.raises(ValueError, match="idempotency_binding_conflict"):
        await _create_store_draft(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            safety_snapshot_hash="sha256:" + "c" * 64,
        )
