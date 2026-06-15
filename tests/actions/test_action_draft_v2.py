from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.schema import ColumnCollectionConstraint

from src.actions.schemas import ActionDraftV2Data, DraftOutcomeV1


MIGRATION_PATH = Path("src/db/migrations/versions/009_action_draft_v2.py")
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
PHASE17_EXTERNAL_SURFACES = (
    "action_executions",
    "action_outbox_events",
    "reconciliation",
    "compensation",
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


def test_action_drafts_orm_uses_tenant_scoped_idempotency_uniqueness():
    items = _named_schema_items("action_drafts")

    assert _item_columns(items["uq_action_drafts_tenant_idempotency_key"]) == {"tenant_id", "idempotency_key"}
    assert "uq_action_drafts_idempotency_key" not in items
    assert not _table("action_drafts").c["idempotency_key"].unique


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
