from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
import re
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.schema import ColumnCollectionConstraint

from src.db.models import Base


MIGRATION_PATH = Path("src/db/migrations/versions/008_approval_state_machine.py")
PHASE34_MIGRATION_PATH = Path("src/db/migrations/versions/018_phase34_approval_action_bindings.py")
PHASE34_APPROVAL_BINDING_COLUMNS = {
    "target_merchant_id",
    "target_merchant_ref",
    "business_fact_refs",
    "verified_evidence_refs",
    "claim_verification_ref",
    "claim_verification_summary",
    "risk_decision_ref",
    "risk_decision",
    "approval_idempotency_key",
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
PHASE36_AGENT_RUN_SCOPE_COLUMNS = {
    "target_merchant_id",
    "target_merchant_ref",
    "scope_classification",
    "scope_source",
    "scope_reason_codes",
}
PHASE17_EXTERNAL_SURFACES = (
    "action_executions",
    "action_outbox_events",
    "action_reconciliation_jobs",
    "action_compensation_records",
)
REPORT_PATHS = (
    Path(".planning/phases/13-approval-state-machine/13-MIGRATION-REPORT.md"),
    Path(".planning/milestones/v1.1-phases/13-approval-state-machine/13-MIGRATION-REPORT.md"),
)


def _table(name: str):
    assert name in Base.metadata.tables
    return Base.metadata.tables[name]


def _column_names(table_name: str) -> set[str]:
    return set(_table(table_name).c.keys())


def _named_schema_items(table_name: str) -> dict[str, UniqueConstraint | CheckConstraint | ForeignKeyConstraint | Index]:
    table = _table(table_name)
    named_items: dict[str, UniqueConstraint | CheckConstraint | ForeignKeyConstraint | Index] = {}
    for item in [*table.constraints, *table.indexes]:
        if item.name:
            named_items[item.name] = item
    return named_items


def _item_columns(item: UniqueConstraint | CheckConstraint | ForeignKeyConstraint | Index) -> set[str]:
    if isinstance(item, ColumnCollectionConstraint | Index):
        return {column.name for column in item.columns}
    return set()


def _fk_targets(item: ForeignKeyConstraint) -> set[str]:
    return {f"{element.column.table.name}.{element.column.name}" for element in item.elements}


def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), "migration 008 must exist"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _phase34_migration_source() -> str:
    assert PHASE34_MIGRATION_PATH.exists(), "migration 018 must exist"
    return PHASE34_MIGRATION_PATH.read_text(encoding="utf-8")


def _migration_report_source() -> str:
    for report_path in REPORT_PATHS:
        if report_path.exists():
            return report_path.read_text(encoding="utf-8")
    raise AssertionError("Phase 13 migration report must exist in active or archived planning artifacts")


def test_action_safety_snapshots_has_unique_immutable_hash_contract():
    table = _table("action_safety_snapshots")

    assert {
        "schema_version",
        "tenant_id",
        "run_id",
        "snapshot_ref",
        "snapshot_json",
        "immutable_hash",
        "action_payload_hash",
        "policy_config_version",
        "risk_config_version",
        "retrieval_config_version",
        "created_by",
        "archived_at",
        "retention_until",
        "deleted_at",
    }.issubset(_column_names("action_safety_snapshots"))

    unique_item = _named_schema_items("action_safety_snapshots")["uq_action_safety_snapshots_tenant_hash"]
    assert isinstance(unique_item, UniqueConstraint | Index)
    assert _item_columns(unique_item) == {"tenant_id", "immutable_hash"}
    assert "uq_action_safety_snapshots_tenant_hash" in _migration_source()
    assert table.c["action_payload_hash"].nullable


def test_approval_request_v2_columns_and_named_constraints_are_declared():
    assert {
        "schema_version",
        "approval_policy_id",
        "policy_version",
        "risk_level",
        "risk_rule_ref",
        "revision",
        "version",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
        "legacy_non_executable",
        "superseded_by_request_id",
        "clarification_request_id",
    }.issubset(_column_names("approval_requests"))

    items = _named_schema_items("approval_requests")
    assert _item_columns(items["uq_approval_requests_tenant_run_revision"]) == {
        "tenant_id",
        "run_id",
        "revision",
    }
    assert _item_columns(items["uq_approval_requests_active_revision"]) == {
        "tenant_id",
        "run_id",
    }
    assert isinstance(items["ck_approval_requests_status"], CheckConstraint)
    source = _migration_source()
    assert "uq_approval_requests_tenant_run_revision" in source
    assert "uq_approval_requests_active_revision" in source
    assert "ck_approval_requests_status" in source


def test_phase34_approval_and_action_binding_columns_are_declared():
    assert PHASE34_APPROVAL_BINDING_COLUMNS.issubset(_column_names("approval_requests"))
    assert PHASE34_ACTION_DRAFT_BINDING_COLUMNS.issubset(_column_names("action_drafts"))

    source = _phase34_migration_source()
    assert 'revision: str = "018_phase34_approval_action_bindings"' in source
    assert 'down_revision: str | None = "017_tool_policy_events"' in source
    for column in sorted(PHASE34_APPROVAL_BINDING_COLUMNS | PHASE34_ACTION_DRAFT_BINDING_COLUMNS):
        assert f'"{column}"' in source


def test_phase34_migration_does_not_create_external_execution_surfaces():
    source = _phase34_migration_source()

    for forbidden in PHASE17_EXTERNAL_SURFACES:
        assert forbidden not in source


def test_phase36_user_username_identity_metadata_is_tenant_scoped():
    user_table = _table("users")
    items = _named_schema_items("users")

    username_constraint = items["uq_users_tenant_username"]
    assert isinstance(username_constraint, UniqueConstraint)
    assert _item_columns(username_constraint) == {"tenant_id", "username"}
    assert user_table.c["username"].unique is not True


def test_phase36_user_merchant_binding_metadata_is_tenant_consistent():
    merchant_constraint = _named_schema_items("merchants")["uq_merchants_id_tenant"]
    assert isinstance(merchant_constraint, UniqueConstraint)
    assert _item_columns(merchant_constraint) == {"id", "tenant_id"}

    user_table = _table("users")
    user_items = _named_schema_items("users")
    merchant_fk = user_items["fk_users_merchant_tenant"]
    assert isinstance(merchant_fk, ForeignKeyConstraint)
    assert _item_columns(merchant_fk) == {"merchant_id", "tenant_id"}
    assert _fk_targets(merchant_fk) == {"merchants.id", "merchants.tenant_id"}
    assert user_table.c["merchant_id"].nullable
    merchant_fk_constraints = [
        constraint
        for constraint in user_table.foreign_key_constraints
        if {element.parent.name for element in constraint.elements} & {"merchant_id"}
    ]
    assert [constraint.name for constraint in merchant_fk_constraints] == ["fk_users_merchant_tenant"]


def test_phase36_agent_run_scope_columns_and_constraints_are_declared():
    agent_runs = _table("agent_runs")
    items = _named_schema_items("agent_runs")

    assert PHASE36_AGENT_RUN_SCOPE_COLUMNS.issubset(_column_names("agent_runs"))
    assert agent_runs.c["target_merchant_id"].nullable
    assert agent_runs.c["target_merchant_ref"].nullable
    assert agent_runs.c["scope_classification"].nullable is False
    assert agent_runs.c["scope_source"].nullable
    assert agent_runs.c["scope_reason_codes"].nullable

    scope_check = items["ck_agent_runs_scope_classification"]
    target_check = items["ck_agent_runs_scope_target_consistency"]
    assert isinstance(scope_check, CheckConstraint)
    assert isinstance(target_check, CheckConstraint)

    scope_sql = str(scope_check.sqltext)
    target_sql = str(target_check.sqltext)
    for classification in ("business_merchant", "policy_only", "merchant_not_required", "unknown_legacy"):
        assert classification in scope_sql
    assert "scope_classification = 'business_merchant'" in target_sql
    assert "target_merchant_id IS NOT NULL" in target_sql
    assert "target_merchant_ref IS NOT NULL" in target_sql
    assert "target_merchant_id IS NULL" in target_sql
    assert "target_merchant_ref IS NULL" in target_sql


def test_phase36_agent_run_scope_indexes_are_declared():
    items = _named_schema_items("agent_runs")

    assert isinstance(items["ix_agent_runs_tenant_target_merchant"], Index)
    assert _item_columns(items["ix_agent_runs_tenant_target_merchant"]) == {"tenant_id", "target_merchant_id"}
    assert isinstance(items["ix_agent_runs_tenant_scope_classification"], Index)
    assert _item_columns(items["ix_agent_runs_tenant_scope_classification"]) == {
        "tenant_id",
        "scope_classification",
    }


def test_phase36_db_check_does_not_overclaim_malformed_target_merchant_ref_validation():
    target_check = _named_schema_items("agent_runs")["ck_agent_runs_scope_target_consistency"]
    target_sql = str(target_check.sqltext)

    assert "target_merchant_ref IS NOT NULL" in target_sql
    assert "target_merchant_binding.v1" not in target_sql
    assert "business_fact_ref" not in target_sql
    assert "TargetMerchantBindingV1" not in target_sql


def test_level_assignment_decision_event_tables_and_constraints_are_declared():
    for table_name in (
        "approval_levels",
        "approval_assignments",
        "approval_decisions",
        "approval_events",
    ):
        _table(table_name)

    level_items = _named_schema_items("approval_levels")
    assert _item_columns(level_items["uq_approval_levels_request_level"]) == {
        "approval_request_id",
        "level_number",
    }
    assert isinstance(level_items["ck_approval_levels_status"], CheckConstraint)
    assert isinstance(_named_schema_items("approval_assignments")["ck_approval_assignments_status"], CheckConstraint)
    assert isinstance(_named_schema_items("approval_decisions")["ck_approval_decisions_type"], CheckConstraint)

    decision_items = _named_schema_items("approval_decisions")
    assert _item_columns(decision_items["uq_approval_decisions_active_assignment"]) == {
        "approval_assignment_id",
    }
    assert _item_columns(decision_items["uq_approval_decisions_winning_accept_level"]) == {
        "approval_level_id",
    }

    source = _migration_source()
    for name in (
        "approval_levels",
        "approval_assignments",
        "approval_decisions",
        "approval_events",
        "uq_approval_levels_request_level",
        "uq_approval_decisions_active_assignment",
        "uq_approval_decisions_winning_accept_level",
        "ck_approval_levels_status",
        "ck_approval_assignments_status",
        "ck_approval_decisions_type",
    ):
        assert name in source


def test_decision_and_event_rows_expose_redundant_bindings_and_payload_fields():
    assert {
        "approval_request_id",
        "approval_level_id",
        "approval_assignment_id",
        "tenant_id",
        "run_id",
        "thread_id",
        "request_revision",
        "request_version",
        "level_version",
        "assignment_version",
        "decision_type",
        "actor_id",
        "response_text",
        "edited_action_json",
    }.issubset(_column_names("approval_decisions"))

    event_columns = _column_names("approval_events")
    assert {
        "approval_request_id",
        "approval_decision_id",
        "replay_event_id",
        "tenant_id",
        "run_id",
        "thread_id",
        "request_revision",
        "request_version",
        "level_version",
        "assignment_version",
        "actor_id",
        "metadata_json",
        "resource_refs_json",
        "redacted_payload_json",
    }.issubset(event_columns)
    assert _table("approval_events").c["replay_event_id"].nullable

    source = _migration_source()
    for name in (
        "thread_id",
        "request_revision",
        "actor_id",
        "response_text",
        "edited_action_json",
        "replay_event_id",
        "metadata_json",
        "resource_refs_json",
        "redacted_payload_json",
    ):
        assert name in source


def test_legacy_duplicate_run_backfill_uses_deterministic_row_number():
    source = _migration_source()
    normalized_source = re.sub(r"\s+", " ", source.lower())

    assert "legacy_non_executable" in source
    assert "row_number()" in normalized_source
    assert "partition by tenant_id, run_id" in normalized_source
    assert "order by created_at, id" in normalized_source
    assert "uq_approval_requests_tenant_run_revision" in source
    assert not re.search(r"set\s+revision\s*=\s*1\b", normalized_source)

    legacy_duplicate_run = [
        {
            "id": UUID("00000000-0000-0000-0000-000000000002"),
            "tenant_id": UUID("11111111-1111-1111-1111-111111111111"),
            "run_id": UUID("22222222-2222-2222-2222-222222222222"),
            "created_at": datetime(2026, 6, 15, 0, 0, 2, tzinfo=UTC),
        },
        {
            "id": UUID("00000000-0000-0000-0000-000000000001"),
            "tenant_id": UUID("11111111-1111-1111-1111-111111111111"),
            "run_id": UUID("22222222-2222-2222-2222-222222222222"),
            "created_at": datetime(2026, 6, 15, 0, 0, 1, tzinfo=UTC),
        },
    ]

    grouped: dict[tuple[UUID, UUID], list[dict[str, object]]] = defaultdict(list)
    for row in legacy_duplicate_run:
        grouped[(row["tenant_id"], row["run_id"])].append(row)

    migrated = []
    for group in grouped.values():
        for revision, row in enumerate(sorted(group, key=lambda item: (item["created_at"], item["id"])), start=1):
            migrated.append(
                {
                    **row,
                    "revision": revision,
                    "legacy_non_executable": True,
                }
            )

    assert [row["revision"] for row in sorted(migrated, key=lambda item: item["revision"])] == [1, 2]
    assert all(row["legacy_non_executable"] for row in migrated)
    unique_keys = {(row["tenant_id"], row["run_id"], row["revision"]) for row in migrated}
    assert len(unique_keys) == len(migrated)


def test_migration_report_names_read_switch_fallback_rollback_and_verification_commands():
    report = _migration_report_source()

    for required in (
        "alembic_current_before",
        "alembic_head_before",
        "legacy_v1_count",
        "legacy_non_executable_count",
        "read_switch_owner",
        "fallback_behavior",
        "rollback_command",
        "verification_commands",
        "uv run alembic upgrade head",
    ):
        assert required in report
